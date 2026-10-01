#!/data/data/com.termux/files/usr/bin/bash
# Install phone-side transport only. Claude Code remains in Linux Codespaces.
set -euo pipefail
if ! command -v pkg >/dev/null || [ -z "${PREFIX:-}" ]; then
  echo 'Run this script inside the Termux Android app.' >&2
  exit 1
fi
# Termux is a rolling distribution: partial upgrades can leave curl linked to
# OpenSSL symbols absent from the older bootstrap. apt itself uses GnuTLS, so
# it can repair this even when curl (and pkg's curl-based mirror check) fails.
apt update
apt full-upgrade -y
pkg install -y curl gh openssh python
phone_dir="$HOME/.local/share/claude-phone"
mkdir -p "$phone_dir"
chmod 700 "$phone_dir"
curl --fail --silent --show-error --location \
  https://raw.githubusercontent.com/amywisconsin12121-gif/blsnk/main/.claude-knowledge/phone.py \
  -o "$phone_dir/phone.py"
chmod 600 "$phone_dir/phone.py"
cat > "$PREFIX/bin/cs" <<'SCRIPT'
#!/data/data/com.termux/files/usr/bin/sh
exec python "$HOME/.local/share/claude-phone/phone.py" "$@"
SCRIPT
chmod 700 "$PREFIX/bin/cs"
termux-setup-storage
if ! gh auth status --hostname github.com >/dev/null 2>&1; then
  gh auth login --hostname github.com --git-protocol https --web --scopes codespace
fi
echo 'Sign in as amywisconsin12121-gif. Allow Termux storage access and set its battery usage to Unrestricted.'
echo 'Next: generate an Ed25519 key in ConnectBot, copy its PUBLIC key, then run: cs key'
echo 'After that: cs upload  (original knowledge.md in Downloads), then: cs'
