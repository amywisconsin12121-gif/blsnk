#!/usr/bin/env bash
set -euo pipefail
setup_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
data_dir="${CLAUDE_KNOWLEDGE_DIR:-/workspaces/claude-knowledge-data}"
secret_name="${1:-CONCENTRATE_API_KEY}"
if [[ ! "$secret_name" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
  echo 'Supply the Codespaces secret name, not its value.' >&2
  exit 1
fi
umask 077
mkdir -p "$data_dir/.claude/output-styles" "$HOME/.local/bin"
export PATH="$HOME/.local/bin:$PATH"
if ! command -v claude >/dev/null 2>&1; then
  curl -fsSL https://claude.ai/install.sh | bash -s latest
fi
claude --version
if ! python3 - "$(claude --version)" <<'PY'
import re, sys
version = re.search(r'(\d+)\.(\d+)\.(\d+)', sys.argv[1])
sys.exit(0 if version and tuple(map(int, version.groups())) >= (2, 1, 280) else 1)
PY
then
  claude update
fi
python3 - "$data_dir" "$setup_dir" "$secret_name" <<'PY'
import json, pathlib, shutil, sys
data, setup, secret_name = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), sys.argv[3]
shutil.copyfile(setup / 'knowledge.py', data / 'knowledge.py')
(data / 'knowledge.py').chmod(0o700)
shutil.copyfile(setup / 'Knowledge.md', data / '.claude/output-styles/Knowledge.md')
shutil.copyfile(setup / 'settings.json', data / '.claude/settings.json')
(data / 'secret-name.txt').write_text(secret_name + '\n')
launcher = pathlib.Path.home() / '.local/bin/knowledge'
if launcher.exists() or launcher.is_symlink():
    launcher.unlink()
launcher.symlink_to(data / 'knowledge.py')
profile = pathlib.Path.home() / '.bashrc'
text = profile.read_text() if profile.exists() else ''
line = 'export PATH="$HOME/.local/bin:$PATH"'
if line not in text:
    with profile.open('a') as f: f.write('\n' + line + '\n')
print('Setup complete. Upload knowledge.md to ' + str(data) + ', then run knowledge.')
PY
if ! command -v tmux >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y -qq tmux
fi
