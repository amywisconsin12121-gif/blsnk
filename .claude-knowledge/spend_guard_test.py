"""Real native CLI against a fake upstream: no paid model calls or private dump."""
from http.server import ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time

ROOT = Path(__file__).parent
spec = importlib.util.spec_from_file_location('native_stub', ROOT / 'native_mock_test.py')
stub = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stub)


class Upstream(stub.Handler):
    mode = 'success'
    token_count = 300
    mock_usage = {'input_tokens': 300, 'output_tokens': 10,
                  'cache_creation_input_tokens': 0, 'cache_read_input_tokens': 0}
    authorizations = []

    def do_POST(self):
        self.authorizations.append(self.headers.get('Authorization'))
        if self.mode in ('success', 'success_crlf'):
            self.response_text = 'اختبار محلي ناجح. NEXT_REPLY_' + str(len(stub.calls) + 1)
            if self.mode == 'success_crlf':
                original = self.wfile
                class CRLFWriter:
                    def write(self, data):
                        return original.write(data.replace(b'\n', b'\r\n') if data.startswith(b'event: ') else data)
                    def flush(self): original.flush()
                self.wfile = CRLFWriter()
                try: return super().do_POST()
                finally: self.wfile = original
            return super().do_POST()
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        stub.calls.append(body)
        if self.mode == 'http_error':
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'type': 'error', 'error': {'type': 'api_error', 'message': 'Synthetic failure'}}).encode())
            return
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.end_headers()
        if self.mode == 'empty_stream':
            return
        if self.mode == 'thinking_only':
            message = {'id': 'msg_thinking_test', 'type': 'message', 'role': 'assistant',
                       'model': 'anthropic/claude-opus-5-5', 'content': [], 'stop_reason': None,
                       'stop_sequence': None, 'usage': dict(self.mock_usage, output_tokens=0)}
            events = [
                ('message_start', {'type': 'message_start', 'message': message}),
                ('content_block_start', {'type': 'content_block_start', 'index': 0,
                                         'content_block': {'type': 'thinking', 'thinking': '', 'signature': ''}}),
                ('content_block_delta', {'type': 'content_block_delta', 'index': 0,
                                         'delta': {'type': 'signature_delta', 'signature': 'synthetic-not-real'}}),
                ('content_block_stop', {'type': 'content_block_stop', 'index': 0}),
                ('message_delta', {'type': 'message_delta', 'delta': {'stop_reason': 'max_tokens', 'stop_sequence': None},
                                   'usage': {'output_tokens': 64000}}),
                ('message_stop', {'type': 'message_stop'}),
            ]
            for name, event in events:
                self.wfile.write(('event: ' + name + '\ndata: ' + json.dumps(event) + '\n\n').encode())
                self.wfile.flush()


def fixture():
    data = Path(tempfile.mkdtemp(prefix='spend-guard-test-'))
    (data / '.claude/output-styles').mkdir(parents=True)
    shutil.copyfile(ROOT / 'settings.json', data / '.claude/settings.json')
    shutil.copyfile(ROOT / 'Knowledge.md', data / '.claude/output-styles/Knowledge.md')
    source = '# مصدر اختبار محلي\nكل كلمة مطلوبة. لون الملف أزرق.\n'
    (data / 'knowledge.md').write_text(source)
    return data, source


def main():
    import threading
    server = ThreadingHTTPServer(('127.0.0.1', 0), Upstream)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    env = dict(os.environ)
    env.update(CONCENTRATE_API_KEY='localhost-upstream-test-key',
               CLAUDE_KNOWLEDGE_GUARD_TEST_UPSTREAM=f'http://127.0.0.1:{server.server_port}')
    env.pop('CLAUDE_KNOWLEDGE_TEST_ENDPOINT', None)
    env['PATH'] = str(Path.home() / '.local/bin') + ':' + env['PATH']
    reports = []
    try:
        for mode, ceiling, expected_calls in [('success', '3', 1), ('success_crlf', '3', 1), ('success', None, 0),
                                               ('success', '0.01', 0), ('http_error', '3', 1),
                                               ('empty_stream', '3', 1), ('thinking_only', '3', 1)]:
            Upstream.mode = mode
            data, source = fixture()
            trial_env = dict(env, CLAUDE_KNOWLEDGE_DIR=str(data))
            before = len(stub.calls)
            command = ['python3', str(ROOT / 'knowledge.py'), '--print', 'ما لون الملف؟', '--json']
            if ceiling is not None: command += ['--max-cost', ceiling]
            result = subprocess.run(command, env=trial_env, capture_output=True, text=True, timeout=65)
            count = len(stub.calls) - before
            if count != expected_calls:
                raise AssertionError(json.dumps({'mode': mode, 'ceiling': ceiling, 'calls': count,
                                                'stdout': result.stdout[-3500:], 'stderr': result.stderr[-2000:]}))
            if mode in ('success', 'success_crlf') and expected_calls:
                parsed = json.loads(result.stdout)
                assert not parsed.get('is_error'), parsed
                assert 'اختبار محلي ناجح' in parsed['result']
                call = stub.calls[-1]
                assert source in '\n'.join(block.get('text', '') for block in call['system'])
                assert call['max_tokens'] == 128000
                assert call['output_config']['effort'] == 'max'
                assert Upstream.authorizations[-1] == 'Bearer localhost-upstream-test-key'
            if mode == 'thinking_only':
                assert 'No answer text was returned' in result.stdout + result.stderr
            reports.append({'mode': mode, 'ceiling': ceiling, 'upstream_calls': count,
                            'native_exit_code': result.returncode})
            print(json.dumps(reports[-1]), flush=True)
        interactive_checks(env, reports)
        report = {'test': 'native Claude Code cost guard', 'paid_requests': 0,
                          'full_source_preserved': True, 'max_effort_preserved': True,
                          'output_ceiling': 128000, 'cases': reports}
        (ROOT / 'spend-guard-test-results.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report))
    finally:
        server.shutdown()
        server.server_close()


def interactive_checks(env, reports):
    import pexpect
    Upstream.mode = 'success'
    data, source = fixture()
    trial_env = dict(env, CLAUDE_KNOWLEDGE_DIR=str(data), TERM='xterm-256color')
    before = len(stub.calls)

    def normal(text):
        text = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', text)
        text = re.sub(r'\x1b[()][A-Za-z0-9]', '', text)
        return re.sub(r'\s+', '', text).lower()

    def launch():
        return pexpect.spawn('python3', [str(ROOT / 'knowledge.py')], env=trial_env,
                             encoding='utf-8', dimensions=(30,100), timeout=30)

    def wait_text(child, wanted):
        trace = ''
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            try: trace += child.read_nonblocking(65536, timeout=0.5)
            except pexpect.TIMEOUT: pass
            if normal(wanted) in normal(trace): return trace
        raise RuntimeError('Terminal text absent: ' + normal(wanted) + '; ' + normal(trace)[-1500:])

    child = launch()
    trace = ''
    seen = set()
    try:
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline:
            try: trace += child.read_nonblocking(65536, timeout=0.5)
            except pexpect.TIMEOUT: pass
            plain = normal(trace)
            if 'theme' not in seen and ('choosethetextstyle' in plain or 'selectatheme' in plain):
                time.sleep(0.3); child.send('\r'); seen.add('theme'); trace = ''
            elif 'notice' not in seen and 'entertocontinue' in plain:
                time.sleep(0.3); child.send('\r'); seen.add('notice'); trace = ''
            elif 'trust' not in seen and ('doyoutrustthefiles' in plain or 'yes,itrustthisfolder' in plain):
                time.sleep(0.3); child.send('\x1b[B'); time.sleep(0.3); child.send('\r'); seen.add('trust'); trace = ''
            if 'apiusage' in plain and ('opus5.5' in plain or 'opus-5-5' in plain): break
        else: raise RuntimeError('Native prompt absent: ' + normal(trace)[-1500:])
        child.send('مرحبا\r')
        wait_text(child, 'COST REVIEW')
        assert len(stub.calls) == before
        child.send('\r')
        wait_text(child, 'Cost approval was not granted')
        assert len(stub.calls) == before
        for question in ('ما لون الملف؟', 'ما معنى blue؟'):
            child.send(question + '\r')
            wait_text(child, 'COST REVIEW')
            count = len(stub.calls)
            child.send('3.00\r')
            wait_text(child, 'NEXT_REPLY_' + str(count + 1))
            assert len(stub.calls) == count + 1, (count, len(stub.calls))
            time.sleep(0.2)
        child.send('/exit\r')
        child.expect(pexpect.EOF, timeout=30)
        child.close()
        assert child.exitstatus == 0
        resumed = launch()
        wait_text(resumed, 'اختبار محلي ناجح')
        assert len(stub.calls) == before + 2
        resumed.send('/exit\r')
        resumed.expect(pexpect.EOF, timeout=30)
        resumed.close()
        assert resumed.exitstatus == 0
        assert len(stub.calls) == before + 2
        reports.append({'mode': 'interactive', 'cost_review_before_forward': True,
                        'cancel_makes_no_upstream_request': True, 'one_approval_one_request': True,
                        'next_question_needs_new_approval': True, 'resume_makes_no_upstream_request': True,
                        'native_exit_code': 0, 'upstream_calls': 2})
        print(json.dumps(reports[-1]), flush=True)
    finally:
        if child.isalive(): child.close(force=True)


if __name__ == '__main__':
    main()
