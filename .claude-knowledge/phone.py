#!/usr/bin/env python3
"""Connect an Android SSH client to the prepared Codespace through GitHub CLI."""
import argparse
import hashlib
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import threading

SPACE = 'claude-knowledge-wv5gr9v9wq9xhvg4q'
REMOTE_SOURCE = '/workspaces/claude-knowledge-data/knowledge.md'
PORT = 2222


def gh_command(*args):
    executable = shutil.which('gh')
    if not executable:
        sys.exit('GitHub CLI is missing. Run android-setup.sh first.')
    return [executable, *args]


def key_path():
    folder = Path.home() / '.local' / 'share' / 'claude-phone'
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Only the public key is stored here. --stdio does not use a private key.
    return folder / 'connectbot'


def set_key():
    value = input('Paste ConnectBot PUBLIC key (ssh-ed25519 ...), then Enter:\n').strip()
    parts = value.split()
    if len(parts) < 2 or parts[0] not in ('ssh-ed25519', 'ssh-rsa', 'ecdsa-sha2-nistp256',
                                        'ecdsa-sha2-nistp384', 'ecdsa-sha2-nistp521'):
        sys.exit('This is not an SSH public key. Copy the PUBLIC key from ConnectBot.')
    public = Path(str(key_path()) + '.pub')
    temporary = public.with_suffix('.pub.tmp')
    temporary.write_text(parts[0] + ' ' + parts[1] + '\n')
    temporary.chmod(0o600)
    result = subprocess.run(['ssh-keygen', '-l', '-f', str(temporary)], capture_output=True)
    if result.returncode:
        temporary.unlink()
        sys.exit('SSH public key validation failed. No connection was made.')
    temporary.replace(public)
    print('Public key saved. The private key stays inside ConnectBot.')


def connect():
    identity = key_path()
    if not Path(str(identity) + '.pub').is_file():
        sys.exit('Run cs key first and paste the PUBLIC key generated in ConnectBot.')
    try:
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('127.0.0.1', PORT))
        server.listen(4)
    except OSError as error:
        sys.exit(f'Cannot open localhost:{PORT}: {error}. Close any earlier cs tunnel.')
    children = set()
    lock = threading.Lock()

    def handle(connection):
        child = None
        try:
            # GitHub supplies the authenticated Codespaces tunnel and installs
            # the public key. ConnectBot performs SSH authentication itself.
            command = gh_command('codespace', 'ssh', '-c', SPACE, '--stdio', '--',
                                 '-i', str(identity))
            child = subprocess.Popen(command, stdin=connection, stdout=connection,
                                     stderr=sys.stderr)
            with lock:
                children.add(child)
            child.wait()
        except OSError as error:
            print(f'Tunnel error: {error}', file=sys.stderr)
        finally:
            connection.close()
            if child:
                with lock:
                    children.discard(child)

    print('Open ConnectBot: codespace@127.0.0.1:2222', flush=True)
    print('Keep Termux running. Ctrl+C closes this phone tunnel; it does not stop the Codespace.', flush=True)
    try:
        while True:
            connection, _ = server.accept()
            threading.Thread(target=handle, args=(connection,), daemon=True).start()
    except KeyboardInterrupt:
        pass
    finally:
        server.close()
        with lock:
            for child in list(children):
                child.terminate()


def upload(filename):
    source = Path(filename).expanduser()
    if not source.is_file():
        sys.exit(f'File missing: {source}. Put your original knowledge.md in phone Downloads.')
    content = source.read_bytes()
    if not content.strip():
        sys.exit('knowledge.md is empty. Nothing was uploaded.')
    try:
        content.decode('utf-8')
    except UnicodeDecodeError:
        sys.exit('knowledge.md must be UTF-8. Nothing was uploaded.')
    digest = hashlib.sha256(content).hexdigest()
    subprocess.run(gh_command('codespace', 'cp', '--expand', '-c', SPACE,
                              str(source), 'remote:' + REMOTE_SOURCE), check=True)
    # A fixed script on stdin avoids remote-shell quoting and does not read keys.
    script = f'chmod 600 {REMOTE_SOURCE}\nsha256sum {REMOTE_SOURCE}\n'
    result = subprocess.run(gh_command('codespace', 'ssh', '-c', SPACE, '--', 'sh', '-s'),
                            input=script, text=True, capture_output=True, check=True)
    remote = result.stdout.split()[0] if result.stdout.split() else ''
    if remote != digest:
        sys.exit('Upload hash check failed. Do not ask a question until the upload is verified.')
    print(f'Uploaded all {len(content):,} bytes unchanged; SHA-256 matches. No model request was sent.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', choices=('connect', 'key', 'upload', 'stop'),
                        default='connect')
    parser.add_argument('file', nargs='?', default=str(Path.home() / 'storage' / 'downloads' / 'knowledge.md'))
    args = parser.parse_args()
    if args.action == 'key':
        set_key()
    elif args.action == 'upload':
        upload(args.file)
    elif args.action == 'stop':
        subprocess.run(gh_command('codespace', 'stop', '-c', SPACE), check=True)
    else:
        connect()


if __name__ == '__main__':
    main()
