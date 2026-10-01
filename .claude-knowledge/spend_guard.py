#!/usr/bin/env python3
"""Local cost approval and one-request-per-submission protection for Claude Code."""
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_CEILING
import fcntl
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import select
import signal
import subprocess
import sys
import termios
import threading
import urllib.error
import urllib.parse
import urllib.request
import uuid

MODEL = 'anthropic/claude-opus-5-5'
# Standard published USD/MTok rates, confirmed by the user's billing receipt.
INPUT_RATE = Decimal('4')
CACHE_WRITE_RATE = Decimal('8')
CACHE_READ_RATE = Decimal('0.2')
OUTPUT_RATE = Decimal('20')
MILLION = Decimal('1000000')


def write_json(path, value):
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temporary.chmod(0o600)
    temporary.replace(path)


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def money(value):
    amount = Decimal(str(value))
    if not amount.is_finite() or amount <= 0:
        raise ValueError('The approved USD ceiling must be a positive finite number.')
    return amount


def mark_submission():
    """This hook runs for a human submission, never for an SDK retry."""
    event = json.load(sys.stdin)
    directory = Path(os.environ['CLAUDE_KNOWLEDGE_GUARD_DIR'])
    if event.get('session_id') != os.environ['CLAUDE_KNOWLEDGE_GUARD_SESSION']:
        sys.exit('Cost guard rejected a different conversation.')
    with (directory / 'turn.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        write_json(directory / 'turn.json', {
            'id': str(uuid.uuid4()), 'session_id': event['session_id'],
            'prompt_sha256': hashlib.sha256(event.get('prompt', '').encode()).hexdigest(),
            'created_at': timestamp(), 'used': False,
        })


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        return None


class Gate:
    def __init__(self, data, session_id, source, key, explicit_ceiling=None, upstream=None):
        self.directory = data / 'spending' / session_id
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.source = source.decode('utf-8')
        self.source_sha256 = hashlib.sha256(source).hexdigest()
        self.key = key
        local_auth = self.directory / 'local-auth.txt'
        try:
            descriptor = os.open(local_auth, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            self.local_key = local_auth.read_text().strip()
        else:
            self.local_key = secrets.token_urlsafe(32)
            with os.fdopen(descriptor, 'w') as output:
                output.write(self.local_key + '\n')
        self.ceiling = money(explicit_ceiling) if explicit_ceiling is not None else None
        self.upstream = upstream or 'https://api.concentrate.ai'
        self.child = None
        self.cancelled = threading.Event()
        self.request_lock = threading.Lock()
        self.original_terminal = termios.tcgetattr(0) if os.isatty(0) else None
        self.source_token_ceiling = None
        measurement = data / 'measured-input.json'
        if measurement.exists():
            value = json.loads(measurement.read_text())
            if value.get('source_sha256') == self.source_sha256 and value.get('model') == MODEL:
                ceiling = value.get('input_token_ceiling')
                if isinstance(ceiling, int) and 0 < ceiling <= 1000000:
                    self.source_token_ceiling = ceiling

    def quote(self, body):
        if body.get('model') != MODEL or body.get('tools'):
            raise ValueError('The guard permits only Opus 5.5 with no tools.')
        if body.get('service_tier') not in (None, 'auto', 'standard') or body.get('speed') == 'fast':
            raise ValueError('Fast or premium service tiers are not approved.')
        output = body.get('max_tokens')
        if not isinstance(output, int) or isinstance(output, bool) or not 1 <= output <= 128000:
            raise ValueError('The output ceiling must be between 1 and 128000 tokens.')
        # Prove the whole immutable source is present, not a slice or summary.
        system = body.get('system', [])
        blocks = [{'type': 'text', 'text': system}] if isinstance(system, str) else system
        occurrences = sum(block.get('text', '').count(self.source) for block in blocks)
        if occurrences != 1:
            raise ValueError('The complete source must occur exactly once in the system prompt.')
        # UTF-8 bytes plus structural padding form a conservative token bound.
        # A previous real input count can tighten the bound for this exact file.
        reduced = dict(body)
        reduced_blocks = [dict(block) for block in blocks]
        if self.source_token_ceiling is not None:
            for block in reduced_blocks:
                if self.source in block.get('text', ''):
                    block['text'] = block['text'].replace(self.source, '', 1)
        reduced['system'] = reduced_blocks
        byte_bound = len(json.dumps(reduced, ensure_ascii=False).encode('utf-8')) + 8192
        tokens = min(1000000, byte_bound + (self.source_token_ceiling or 0))
        input_cost = Decimal(tokens) * CACHE_WRITE_RATE / MILLION
        output_cost = Decimal(output) * OUTPUT_RATE / MILLION
        maximum = (input_cost + output_cost).quantize(Decimal('0.01'), rounding=ROUND_CEILING)
        return {'input_token_ceiling': tokens, 'max_output_tokens': output,
                'input_usd_ceiling': str(input_cost), 'output_usd_ceiling': str(output_cost),
                'maximum_usd': str(maximum), 'effort': body.get('output_config', {}).get('effort'),
                'basis': 'Conservative ceiling at standard published rates, assuming a fresh 1h cache write. Thinking counts as output.'}

    def reserve_turn(self, quote):
        with (self.directory / 'turn.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            marker = self.directory / 'turn.json'
            if not marker.exists():
                raise ValueError('No human submission is armed. No paid request was sent.')
            turn = json.loads(marker.read_text())
            if turn.get('used'):
                previous = self.directory / (turn['id'] + '.json')
                if previous.exists() and json.loads(previous.read_text()).get('status') == 'cancelled_without_upstream_request':
                    raise ValueError('Cost approval was not granted. No paid request was sent; an additional automatic attempt was also blocked.')
                raise ValueError('An extra request for this submission was blocked. No automatic retry is allowed.')
            # Consume before approval and before connecting. Errors never rearm a turn.
            turn['used'] = True
            write_json(marker, turn)
        record = {'turn_id': turn['id'], 'created_at': timestamp(), 'quote': quote,
                  'forwarded': False, 'status': 'awaiting_approval'}
        path = self.directory / (turn['id'] + '.json')
        write_json(path, record)
        return path, record

    def approve(self, quote):
        required = money(quote['maximum_usd'])
        if self.ceiling is not None:
            return self.ceiling >= required
        if self.original_terminal is None or self.child is None or self.child.poll() is not None:
            return False
        descriptor = os.open('/dev/tty', os.O_RDWR)
        raw_terminal = termios.tcgetattr(descriptor)
        stopped = False
        try:
            # Keep the genuine Claude Code request pending. Pause its keyboard
            # reader while the launcher owns the financial approval prompt.
            os.kill(self.child.pid, signal.SIGSTOP)
            stopped = True
            termios.tcsetattr(descriptor, termios.TCSANOW, self.original_terminal)
            prompt = (
                '\r\n\r\nCOST REVIEW — NO OPUS REQUEST HAS BEEN SENT\r\n'
                f"Effort: {quote['effort']}. One request only; no automatic retries.\r\n"
                f"Input ceiling: ${Decimal(quote['input_usd_ceiling']):.3f}, allowing for an expired cache.\r\n"
                f"Thinking + answer ceiling: {quote['max_output_tokens']} tokens / ${Decimal(quote['output_usd_ceiling']):.2f}.\r\n"
                f"Maximum at published rates: ${required:.2f}. Actual use may be lower.\r\n"
                'Payment does not guarantee an answer; the model can exhaust its thinking budget.\r\n'
                f'Type {required:.2f} to approve this request, or press Enter to cancel (5-minute expiry): '
            )
            os.write(descriptor, prompt.encode('utf-8'))
            ready, _, _ = select.select([descriptor], [], [], 300)
            if not ready or self.cancelled.is_set():
                return False
            text = os.read(descriptor, 128).decode('utf-8').strip()
            try:
                return bool(text) and money(text) >= required
            except (ValueError, InvalidOperation):
                return False
        finally:
            try:
                termios.tcsetattr(descriptor, termios.TCSANOW, raw_terminal)
            finally:
                os.close(descriptor)
                if stopped:
                    try: os.kill(self.child.pid, signal.SIGCONT)
                    except ProcessLookupError: pass

    @staticmethod
    def usage_cost(usage):
        creations = usage.get('cache_creation', {})
        one_hour = creations.get('ephemeral_1h_input_tokens', 0)
        five_minute = creations.get('ephemeral_5m_input_tokens', 0)
        unknown = max(0, usage.get('cache_creation_input_tokens', 0) - one_hour - five_minute)
        return (Decimal(usage.get('input_tokens', 0)) * INPUT_RATE
                + Decimal(usage.get('cache_read_input_tokens', 0)) * CACHE_READ_RATE
                + Decimal(one_hour + unknown) * CACHE_WRITE_RATE
                + Decimal(five_minute) * Decimal('5')
                + Decimal(usage.get('output_tokens', 0)) * OUTPUT_RATE) / MILLION


def handler_for(gate):
    class Handler(BaseHTTPRequestHandler):
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
            if urllib.parse.urlsplit(self.path).path.rstrip('/') != '/v1/models':
                return self.error('Extra service calls are disabled by the cost guard.')
            body = json.dumps({'data': [{'id': MODEL, 'type': 'model', 'display_name': 'Opus 5.5',
                                        'created_at': '2026-09-22T00:00:00Z'}], 'has_more': False}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if self.headers.get('Authorization') != 'Bearer ' + gate.local_key:
                return self.error('Invalid local guard credential.')
            if urllib.parse.urlsplit(self.path).path.rstrip('/') != '/v1/messages':
                return self.error('Only the main message endpoint is enabled. No paid request was sent.')
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 16000000:
                return self.error('Invalid request size. No paid request was sent.')
            raw = self.rfile.read(size)
            path = record = None
            with gate.request_lock:
                try:
                    body = json.loads(raw)
                    quote = gate.quote(body)
                    path, record = gate.reserve_turn(quote)
                    if not gate.approve(quote):
                        record['status'] = 'cancelled_without_upstream_request'
                        write_json(path, record)
                        return self.error('Cost approval was not granted. No paid request was sent. Submit again only when you want a new cost review.')
                    if gate.cancelled.is_set():
                        return self.error('Session closed before forwarding. No paid request was sent.')
                    record.update(forwarded=True, status='forwarding', forwarded_at=timestamp())
                    write_json(path, record)
                    self.forward(raw, path, record)
                except (ValueError, InvalidOperation) as error:
                    return self.error(str(error))
                except (BrokenPipeError, ConnectionResetError):
                    if record is not None:
                        record['status'] = 'client_disconnected_billing_may_still_apply'
                        write_json(path, record)

        def forward(self, raw, path, record):
            headers = {name: value for name, value in self.headers.items() if name.lower() not in
                       ('host', 'content-length', 'connection', 'authorization', 'x-api-key', 'accept-encoding')}
            headers.update(Authorization='Bearer ' + gate.key, **{'Accept-Encoding': 'identity'})
            request = urllib.request.Request(gate.upstream + self.path, data=raw, headers=headers, method='POST')
            opener = urllib.request.build_opener(NoRedirect)
            try:
                response = opener.open(request, timeout=3600)
            except urllib.error.HTTPError as error:
                response = error
            except Exception as error:
                record.update(status='connection_failed_billing_unknown', error_type=type(error).__name__)
                write_json(path, record)
                return self.error('The connection failed. No automatic retry will be sent; check provider billing before manually retrying.')
            with response:
                record['upstream_status'] = response.status
                self.send_response(response.status)
                for name, value in response.headers.items():
                    if name.lower() in ('content-type', 'cache-control', 'x-request-id', 'request-id'):
                        self.send_header(name, value)
                    if name.lower() in ('x-request-id', 'request-id'):
                        record['request_id'] = value
                self.send_header('Connection', 'close')
                self.end_headers()
                streamed = 'event-stream' in response.headers.get('Content-Type', '')
                pending = b''
                complete = b''
                usage = {}
                text_chars = 0
                stop_reason = None
                saw_stop = False
                while True:
                    chunk = response.read1(16384)
                    if not chunk:
                        break
                    if not streamed:
                        complete += chunk
                        continue
                    pending += chunk
                    while True:
                        delimiter = re.search(rb'\r?\n\r?\n', pending)
                        if delimiter is None:
                            break
                        frame, ending = pending[:delimiter.start()], pending[delimiter.start():delimiter.end()]
                        pending = pending[delimiter.end():]
                        event = None
                        payload = b'\n'.join(line[6:] for line in frame.splitlines() if line.startswith(b'data: '))
                        if payload:
                            try: event = json.loads(payload)
                            except ValueError: pass
                        if event:
                            usage.update(event.get('message', {}).get('usage', {}))
                            usage.update(event.get('usage', {}))
                            delta = event.get('delta', {})
                            if delta.get('type') == 'text_delta': text_chars += len(delta.get('text', ''))
                            if event.get('content_block', {}).get('type') == 'text':
                                text_chars += len(event['content_block'].get('text', ''))
                            stop_reason = delta.get('stop_reason', stop_reason)
                            if event.get('type') == 'message_stop': saw_stop = True
                            if event.get('usage') or event.get('message', {}).get('usage'):
                                record.update(usage=dict(usage), answer_text_chars=text_chars,
                                              stop_reason=stop_reason, estimated_actual_usd=str(gate.usage_cost(usage)))
                                write_json(path, record)
                            if event.get('type') == 'message_stop' and text_chars == 0:
                                message = f'No answer text was returned (stop reason: {stop_reason}; output tokens: {usage.get("output_tokens", "unknown")}). Thinking can still be billed. The cost guard will not retry automatically.'
                                frame = ('event: error\ndata: ' + json.dumps({'type': 'error', 'error': {'type': 'invalid_request_error', 'message': message}})).encode()
                        self.wfile.write(frame + ending)
                        self.wfile.flush()
                if streamed and pending:
                    self.wfile.write(pending)
                if not streamed:
                    try:
                        result = json.loads(complete)
                        usage = result.get('usage', {})
                        stop_reason = result.get('stop_reason')
                        text_chars = sum(len(block.get('text', '')) for block in result.get('content', []) if block.get('type') == 'text')
                    except ValueError:
                        pass
                    self.wfile.write(complete)
                record.update(status='completed' if not streamed or saw_stop else 'incomplete_stream_billing_unknown',
                              usage=usage, answer_text_chars=text_chars, stop_reason=stop_reason,
                              estimated_actual_usd=str(gate.usage_cost(usage)), completed_at=timestamp())
                write_json(path, record)
                self.close_connection = True
    return Handler


def run_cli(command, env, data, session_id, source, key, secret_name, explicit_ceiling=None, upstream=None):
    gate = Gate(data, session_id, source, key, explicit_ceiling, upstream)
    process_lock = (gate.directory / 'process.lock').open('a')
    try:
        fcntl.flock(process_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit('This conversation is already open. Reattach its tmux session.')
    # A previous process's unused marker never authorizes a new process.
    write_json(gate.directory / 'turn.json', {'id': str(uuid.uuid4()), 'used': True, 'created_at': timestamp()})
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(gate))
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    child_env = dict(env)
    child_env.update(ANTHROPIC_BASE_URL=f'http://127.0.0.1:{server.server_port}',
                     ANTHROPIC_AUTH_TOKEN=gate.local_key, ANTHROPIC_API_KEY='',
                     CLAUDE_KNOWLEDGE_GUARD_DIR=str(gate.directory),
                     CLAUDE_KNOWLEDGE_GUARD_SESSION=session_id)
    child_env.pop(secret_name, None)
    try:
        gate.child = subprocess.Popen(command, env=child_env)
        return gate.child.wait()
    except KeyboardInterrupt:
        gate.cancelled.set()
        if gate.child is not None and gate.child.poll() is None:
            os.kill(gate.child.pid, signal.SIGCONT)
            gate.child.terminate()
            try: gate.child.wait(timeout=5)
            except subprocess.TimeoutExpired: gate.child.kill()
        return 130
    finally:
        gate.cancelled.set()
        server.shutdown()
        server.server_close()
        if gate.original_terminal is not None:
            termios.tcsetattr(0, termios.TCSANOW, gate.original_terminal)
        process_lock.close()


if __name__ == '__main__' and sys.argv[1:] == ['mark']:
    mark_submission()
