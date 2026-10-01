#!/usr/bin/env python3
"""Bounded live Opus test. Run inside the fresh Codespace after setup."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request

ROOT = Path(__file__).parent
MAX_REQUESTS = 4
MAX_TOTAL_BODY_BYTES = 40000
MAX_OUTPUT_PER_REQUEST = 2048
ledger = {'requests': [], 'reserved_request_bytes': 0}
lock = threading.Lock()
budget_path = None

def save_budget():
    temporary = budget_path.with_suffix('.tmp')
    temporary.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + '\n')
    temporary.chmod(0o600)
    temporary.replace(budget_path)

def redact(value, secret):
    if isinstance(value, str):
        return value.replace(secret, '[REDACTED]')
    if isinstance(value, list):
        return [redact(item, secret) for item in value]
    if isinstance(value, dict):
        return {name: redact(item, secret) for name, item in value.items()}
    return value

def main():
    global budget_path, ledger
    secret_name = sys.argv[1] if len(sys.argv) > 1 else 'CONCENTRATE_API_KEY'
    key = os.environ.get(secret_name, '')
    if not key:
        sys.exit('The configured secret is missing. No live request was made.')
    # One persistent budget covers every invocation, including interrupted tests
    # and unsuccessful upstream attempts. A rerun never resets the allowance.
    budget_path = Path(os.environ.get('CLAUDE_LIVE_TEST_BUDGET_FILE',
                                     '/workspaces/claude-knowledge-data/live-test-budget.json'))
    budget_path.parent.mkdir(parents=True, exist_ok=True)
    budget_lock = budget_path.with_suffix('.lock').open('a')
    try:
        fcntl.flock(budget_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit('Another bounded live test is running. No request was made.')
    if budget_path.exists():
        ledger = json.loads(budget_path.read_text())
    if len(ledger['requests']) >= MAX_REQUESTS or ledger['reserved_request_bytes'] >= MAX_TOTAL_BODY_BYTES:
        sys.exit('The shared live-test budget is exhausted. No request was made.')
    data = Path(tempfile.mkdtemp(prefix='claude-live-small-test-'))
    (data / '.claude/output-styles').mkdir(parents=True)
    shutil.copy(ROOT / 'settings.json', data / '.claude/settings.json')
    shutil.copy(ROOT / 'Knowledge.md', data / '.claude/output-styles/Knowledge.md')
    (data / 'secret-name.txt').write_text(secret_name)
    source = '''# معرفة مصطنعة صغيرة للاختبار فقط
المشروع اسمه اللوتس. تكلفته الأساسية سبعة دنانير.
كل المشاريع تحصل على تخفيض دينارين إذا سجلت قبل الخميس.
## استثناء
مشروع اللوتس لا يحصل على التخفيض، مهما كان تاريخ التسجيل.
## معلومة منفصلة
لون ملف اللوتس هو الأزرق. لا توجد قواعد أخرى في هذا المصدر.
'''
    (data / 'knowledge.md').write_bytes(source.encode())

    class Relay(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def error(self, message):
            body = json.dumps({'type': 'error', 'error': {'type': 'invalid_request_error', 'message': message}}).encode()
            self.send_response(400)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def do_GET(self):
            self.forward(None, None)
        def do_POST(self):
            entry = None
            raw = self.rfile.read(int(self.headers.get('Content-Length', 0)))
            try:
                body = json.loads(raw)
            except ValueError:
                return self.error('Live test refused non-JSON request.')
            if 'count_tokens' not in self.path:
                if body.get('model') != 'anthropic/claude-opus-5-5':
                    return self.error('Live test permits only the pinned Opus 5.5 model.')
                if body.get('max_tokens', 0) > MAX_OUTPUT_PER_REQUEST:
                    return self.error('Live test output ceiling exceeded; request was not forwarded.')
                with lock:
                    if len(ledger['requests']) >= MAX_REQUESTS or ledger['reserved_request_bytes'] + len(raw) > MAX_TOTAL_BODY_BYTES:
                        return self.error('Live test input budget reached; request was not forwarded.')
                    # Raw JSON bytes include all system, source, history, tools and overhead.
                    # Reserving before forwarding also counts failed upstream attempts.
                    ledger['reserved_request_bytes'] += len(raw)
                    system = body.get('system', [])
                    system_text = system if isinstance(system, str) else '\n'.join(x.get('text', '') for x in system)
                    entry = {'request_bytes': len(raw), 'model': body['model'],
                             'effort': body.get('output_config', {}).get('effort'),
                             'thinking': body.get('thinking'), 'max_tokens': body.get('max_tokens'),
                             'source_intact': source in system_text, 'tools': len(body.get('tools', [])),
                             'system_cache_controls': [x['cache_control'] for x in system if isinstance(x, dict) and 'cache_control' in x],
                             'message_count': len(body.get('messages', []))}
                    ledger['requests'].append(entry)
                    save_budget()
            self.forward(raw, entry)
        def forward(self, raw, entry):
            url = 'https://api.concentrate.ai' + self.path
            headers = {k: v for k, v in self.headers.items() if k.lower() not in
                       ('host', 'content-length', 'connection', 'authorization', 'x-api-key', 'accept-encoding')}
            headers['Authorization'] = 'Bearer ' + key
            headers['Accept-Encoding'] = 'identity'
            request = urllib.request.Request(url, data=raw, headers=headers, method='POST' if raw is not None else 'GET')
            try:
                response = urllib.request.urlopen(request, timeout=180)
            except urllib.error.HTTPError as error:
                response = error
            except Exception as error:
                return self.error('Upstream connection failed: ' + type(error).__name__)
            with response:
                if entry is not None:
                    with lock:
                        entry['upstream_status'] = response.status
                        save_budget()
                self.send_response(response.status)
                for name, value in response.headers.items():
                    if name.lower() in ('content-type', 'cache-control', 'x-request-id', 'request-id'):
                        self.send_header(name, value)
                self.send_header('Connection', 'close')
                self.end_headers()
                pending = b''
                while True:
                    chunk = response.read1(16384)
                    if not chunk:
                        break
                    if entry is not None and 'event-stream' in response.headers.get('Content-Type', ''):
                        pending += chunk
                        while b'\n' in pending:
                            line, pending = pending.split(b'\n', 1)
                            if line.startswith(b'data: '):
                                try:
                                    event = json.loads(line[6:])
                                except ValueError:
                                    continue
                                usage = event.get('usage') or event.get('message', {}).get('usage')
                                if usage:
                                    with lock:
                                        entry.setdefault('upstream_usage', {}).update(usage)
                                        save_budget()
                                if event.get('message', {}).get('model'):
                                    with lock:
                                        entry['upstream_model'] = event['message']['model']
                                        save_budget()
                    self.wfile.write(chunk)
                    self.wfile.flush()
                self.close_connection = True

    server = ThreadingHTTPServer(('127.0.0.1', 0), Relay)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    env = dict(os.environ)
    env.update(CLAUDE_KNOWLEDGE_DIR=str(data),
               CLAUDE_KNOWLEDGE_TEST_ENDPOINT=f'http://127.0.0.1:{server.server_port}',
               CLAUDE_KNOWLEDGE_TEST_OUTPUT_LIMIT=str(MAX_OUTPUT_PER_REQUEST),
               CLAUDE_CODE_MAX_RETRIES='0', PATH=str(Path.home() / '.local/bin') + ':' + env['PATH'])
    results = []
    try:
        questions = ('ما تكلفة اللوتس إذا سجل يوم الأربعاء؟ أجب بجملة عربية قصيرة واحدة مع السبب من المصدر.',
                     'ما لون الملف وما التكلفة الصحيحة؟ أجب بجملة عربية قصيرة واحدة مستندا إلى المصدر والسؤال السابق.')
        for question in questions:
            run = subprocess.run([str(ROOT / 'knowledge.py'), '--print', question, '--json'], env=env,
                                 capture_output=True, text=True, timeout=240)
            if run.returncode:
                results.append({'exit_code': run.returncode, 'stdout': run.stdout[-4000:], 'stderr': run.stderr[-2000:]})
                break
            result = json.loads(run.stdout)
            results.append(result)
            if result.get('is_error'):
                break
    finally:
        server.shutdown()
    report = {'live': True, 'input_guard': {'max_total_raw_request_bytes': MAX_TOTAL_BODY_BYTES,
                                           'max_inference_requests': MAX_REQUESTS,
                                           'max_total_output_tokens': MAX_REQUESTS * MAX_OUTPUT_PER_REQUEST},
              'ledger': ledger, 'results': results, 'test_data_dir': str(data)}
    # Upstream error text is untrusted; ensure the credential cannot enter logs.
    report = redact(report, key)
    report_path = ROOT / 'live-test-results.json'
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if len(results) != 2 or any(x.get('is_error') or x.get('exit_code') for x in results):
        sys.exit(1)

if __name__ == '__main__':
    main()
