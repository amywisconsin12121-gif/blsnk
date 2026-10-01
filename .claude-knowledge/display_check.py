#!/usr/bin/env python3
"""Check the real Claude Code Arabic terminal UI using a localhost mock only."""
from http.server import ThreadingHTTPServer
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading

from native_mock_test import Handler

ROOT = Path(__file__).resolve().parent


class DisplayHandler(Handler):
    response_text = (
        'اختبار محلي فقط. لم يُرسل أي طلب إلى Opus.\n\n'
        'العربية متصلة من اليمين إلى اليسار. هذا نص طويل لاختبار التفاف السطر '
        'وعرض الكلمات بصورة صحيحة داخل شاشة Claude Code.\n\n'
        'السؤال: ما لون الملف؟ الإجابة: أزرق. الرقم: 123. السعر: 7 دولارات.'
    )
    token_count = 300
    mock_usage = {'input_tokens': 300, 'output_tokens': 60,
                  'cache_creation_input_tokens': 0, 'cache_read_input_tokens': 0}


def main():
    # A separate tiny fixture and conversation: never open the private dump.
    base = Path(os.environ.get('CLAUDE_KNOWLEDGE_DIR', '/workspaces/claude-knowledge-data'))
    data = base / 'display-check'
    config = data / '.claude'
    (config / 'output-styles').mkdir(parents=True, mode=0o700, exist_ok=True)
    template = ROOT if (ROOT / 'settings.json').exists() else ROOT / '.claude'
    shutil.copyfile(template / 'settings.json', config / 'settings.json')
    style = template / 'Knowledge.md' if template == ROOT else template / 'output-styles/Knowledge.md'
    shutil.copyfile(style, config / 'output-styles/Knowledge.md')
    (data / 'knowledge.md').write_text('# اختبار العرض\nلون الملف أزرق.\n', encoding='utf-8')
    (data / 'secret-name.txt').write_text('CONCENTRATE_API_KEY\n')
    server = ThreadingHTTPServer(('127.0.0.1', 0), DisplayHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    env = dict(os.environ)
    env.update(CLAUDE_KNOWLEDGE_DIR=str(data),
               CONCENTRATE_API_KEY='localhost-display-check-not-a-provider-key',
               CLAUDE_KNOWLEDGE_TEST_ENDPOINT=f'http://127.0.0.1:{server.server_port}',
               CLAUDE_CODE_MAX_RETRIES='0')
    env.pop('CLAUDE_KNOWLEDGE_TEST_OUTPUT_LIMIT', None)
    env.pop('CLAUDE_KNOWLEDGE_TEST_DEBUG', None)
    if not sys.argv[1:]:
        print('FREE LOCAL DISPLAY CHECK. Type an Arabic question; use /exit to finish.', flush=True)
    try:
        result = subprocess.run([sys.executable, str(ROOT / 'knowledge.py'), *sys.argv[1:]], env=env)
        return result.returncode
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    sys.exit(main())
