"""Inspect real Claude Code requests against a local stub. No paid calls."""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import time

ROOT = Path(__file__).parent
calls = []

class Handler(BaseHTTPRequestHandler):
    response_text = '\u0627\u062e\u062a\u0628\u0627\u0631 \u0645\u062d\u0644\u064a \u0646\u0627\u062c\u062d.'
    token_count = 180000
    mock_usage = {'input_tokens': 100, 'output_tokens': 10, 'cache_creation_input_tokens': 180000,
                  'cache_read_input_tokens': 0,
                  'cache_creation': {'ephemeral_1h_input_tokens': 180000, 'ephemeral_5m_input_tokens': 0}}
    def log_message(self, *args):
        pass
    def do_GET(self):
        data = {'id': 'anthropic/claude-opus-5-5', 'type': 'model', 'display_name': 'Opus 5.5',
                'created_at': '2026-09-22T00:00:00Z'}
        if self.path.rstrip('/') == '/v1/models':
            data = {'data': [data], 'has_more': False, 'first_id': data['id'], 'last_id': data['id']}
        self.respond(data)
    def respond(self, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)
    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get('Content-Length', 0)))
        body = json.loads(raw)
        if 'count_tokens' in self.path:
            self.respond({'input_tokens': self.token_count})
            return
        calls.append(body)
        content = self.response_text
        usage = self.mock_usage.copy()
        msg = {'id': 'msg_mock_' + str(len(calls)), 'type': 'message', 'role': 'assistant',
               'model': 'claude-opus-5-5', 'content': [], 'stop_reason': None,
               'stop_sequence': None, 'usage': usage}
        if not body.get('stream'):
            msg.update(content=[{'type': 'text', 'text': content}], stop_reason='end_turn')
            self.respond(msg)
            return
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        events = [
            ('message_start', {'type': 'message_start', 'message': msg}),
            ('content_block_start', {'type': 'content_block_start', 'index': 0,
                                     'content_block': {'type': 'text', 'text': ''}}),
            ('content_block_delta', {'type': 'content_block_delta', 'index': 0,
                                     'delta': {'type': 'text_delta', 'text': content}}),
            ('content_block_stop', {'type': 'content_block_stop', 'index': 0}),
            ('message_delta', {'type': 'message_delta', 'delta': {'stop_reason': 'end_turn', 'stop_sequence': None},
                               'usage': {'output_tokens': usage['output_tokens']}}),
            ('message_stop', {'type': 'message_stop'}),
        ]
        for name, value in events:
            self.wfile.write(('event: ' + name + '\ndata: ' + json.dumps(value, ensure_ascii=False) + '\n\n').encode())
            self.wfile.flush()

def main():
    data = Path(tempfile.mkdtemp(prefix='claude-full-source-test-'))
    (data / '.claude/output-styles').mkdir(parents=True)
    shutil.copy(ROOT / 'settings.json', data / '.claude/settings.json')
    shutil.copy(ROOT / 'Knowledge.md', data / '.claude/output-styles/Knowledge.md')
    source = ('# \u0645\u0635\u062f \u0639\u0631\u0628\u064a \u0644\u0644\u0627\u062e\u062a\u0628\u0627\u0631\nBEGIN-unique\n' +
              ('\u0627\u0644\u0645\u0639\u0631\u0641\u0629 \u0643\u0627\u0645\u0644\u0629 \u0628\u062f\u0648\u0646 \u062d\u0630\u0641 \u0643\u0644\u0645\u0629\u061b \u0627\u0644\u0631\u0628\u0637 \u0628\u064a\u0646 \u0627\u0644\u0628\u062f\u0627\u064a\u0629 \u0648\u0627\u0644\u0648\u0633\u0637 \u0648\u0627\u0644\u0646\u0647\u0627\u064a\u0629 \u0645\u0637\u0644\u0648\u0628.\r\n' * 4500) +
              '\nMIDDLE-unique\n' +
              ('\u0643\u0644 \u0643\u0644\u0645\u0629 \u0645\u062d\u0641\u0648\u0638\u0629 \u0648\u0643\u0644 \u0633\u0637\u0631 \u0645\u0636\u0645\u0646 \u0643\u0627\u0645\u0644\u0627 \u062f\u0648\u0646 \u062a\u0644\u062e\u064a\u0635.\r\n' * 4500) + '\nEND-unique\n')
    (data / 'knowledge.md').write_bytes(source.encode('utf-8'))
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    env = dict(os.environ)
    env.update(CLAUDE_KNOWLEDGE_DIR=str(data), CONCENTRATE_API_KEY='mock-key-never-an-upstream-key',
               CLAUDE_KNOWLEDGE_TEST_ENDPOINT=f'http://127.0.0.1:{server.server_port}',
               CLAUDE_KNOWLEDGE_TEST_DEBUG=str(data / 'debug.txt'),
               CLAUDE_CODE_MAX_RETRIES='0', PATH=str(Path.home() / '.local/bin') + ':' + env['PATH'])
    outputs = []
    for prompt in ('\u0627\u0644\u0633\u0624\u0627\u0644 \u0627\u0644\u0623\u0648\u0644\u061b \u0627\u062d\u0641\u0638 \u0643\u0644\u0645\u0629 \u0627\u0644\u0644\u0648\u062a\u0633.', '\u0645\u0627 \u0643\u0644\u0645\u0629 \u0627\u0644\u0633\u0624\u0627\u0644 \u0627\u0644\u0633\u0627\u0628\u0642\u061f'):
        result = subprocess.run([str(ROOT / 'knowledge.py'), '--print', prompt, '--json'], env=env,
                                capture_output=True, text=True, timeout=120)
        if result.returncode:
            print(json.dumps({'exit': result.returncode, 'stdout': result.stdout[-6000:], 'stderr': result.stderr[-3000:]}, ensure_ascii=False))
            raise SystemExit(result.returncode)
        outputs.append(json.loads(result.stdout))
    (data / 'requests.json').write_text(json.dumps(calls, ensure_ascii=False))
    (data / 'outputs.json').write_text(json.dumps(outputs, ensure_ascii=False))
    print('Local request inspection directory: ' + str(data), flush=True)
    assert len(calls) == 2, f'Unexpected request count: {len(calls)}'
    for call in calls:
        system = call.get('system', [])
        if isinstance(system, str):
            texts = system
            cache_controls = []
        else:
            texts = '\n'.join(block.get('text', '') for block in system)
            cache_controls = [block['cache_control'] for block in system if 'cache_control' in block]
        assert source in texts, 'Source was truncated or normalized in outgoing request'
        assert texts.count(source) == 1, 'Source is repeated in the request'
        assert call['model'] == 'anthropic/claude-opus-5-5', call['model']
        assert call.get('output_config', {}).get('effort') == 'max', call.get('output_config')
        assert call.get('thinking', {}).get('type') == 'adaptive', call.get('thinking')
        assert call['max_tokens'] == 128000, call['max_tokens']
        assert cache_controls and all(x.get('ttl') == '1h' for x in cache_controls), cache_controls
        assert not call.get('tools'), 'Knowledge session unexpectedly exposes tools'
        assert 'You are a careful analyst' in json.dumps(call, ensure_ascii=False), 'Custom non-coding style missing'
    assert calls[0]['system'] == calls[1]['system'], 'System prompt changed during resume'
    assert '\u0627\u0644\u0644\u0648\u062a\u0633' in json.dumps(calls[1]['messages'], ensure_ascii=False), 'Prior question was not restored'
    assert outputs[0]['session_id'] == outputs[1]['session_id'], 'Resume started a different conversation'
    context_windows = [v.get('contextWindow') for v in outputs[1].get('modelUsage', {}).values()]
    assert 1000000 in context_windows, context_windows
    # Meaningful refusal checks: prevent missing keys or a changed dump sending a request.
    missing = dict(env)
    missing.pop('CONCENTRATE_API_KEY')
    result = subprocess.run([str(ROOT / 'knowledge.py'), '--print', 'unused'], env=missing, capture_output=True, text=True)
    assert result.returncode and 'missing' in result.stderr
    (data / 'knowledge.md').write_text(source + 'changed')
    result = subprocess.run([str(ROOT / 'knowledge.py'), '--print', 'unused'], env=env, capture_output=True, text=True)
    assert result.returncode and 'changed' in result.stderr
    assert len(calls) == 2
    report = {'test': 'real Claude Code against local mock, zero paid tokens',
              'claude_version': subprocess.check_output([str(Path.home() / '.local/bin/claude'), '--version'], text=True).strip(),
              'source_bytes': len(source.encode()), 'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
              'full_source_exact': True, 'source_survives_resume': True, 'system_prefix_stable': True,
              'effort': 'max', 'thinking': 'adaptive', 'max_output_tokens': 128000,
              'context_window': 1000000, 'cache_markers': '1h', 'tools': 0,
              'arabic_transport': True, 'missing_key_blocked': True, 'changed_source_blocked': True,
              'session_id': outputs[0]['session_id'], 'test_data_dir': str(data),
              'live_provider_authentication_and_cache_hits': 'not tested'}
    (ROOT / 'native-test-results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    server.shutdown()

if __name__ == '__main__':
    main()
