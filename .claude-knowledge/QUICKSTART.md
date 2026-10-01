# Short workflow — live deployment is pending repository access

These files configure Linux Claude Code in GitHub Codespaces. Your Android app is
only the SSH client. No Anthropic subscription is required for a Concentrate key.

The launcher has passed local native Claude Code tests. Authentication to
Concentrate, real cache hits, Codespaces SSH, and your phone's display are still
untested. Do not treat this as a completed live deployment.

## Once your fresh Codespace is configured

1. Rename the original phone file to `knowledge.md`. Keep its complete contents.
2. Upload it to `/workspaces/claude-knowledge-data/knowledge.md` in the Codespace.
3. In the remote Linux terminal, run `knowledge` and ask your question in Arabic.

First launch: select a theme, press Enter through the introductory notice, then
select **Yes, I trust this folder** for your own prepared folder. The Concentrate
secret supplies authentication; you do not need an Anthropic login.

The single `knowledge` command always sets Opus 5.5, maximum effort, adaptive
thinking, 1M context, 128K output headroom, and 1-hour caching. It embeds the whole
source and resumes the saved conversation. `knowledge check` checks the local file,
its hash, session ID, and whether the secret is present; it makes no paid request.
Inside Claude Code, `/status` checks the endpoint/model, and `/usage` shows usage.
Your Concentrate dashboard determines the actual bill.

## Stop and resume

- Finish the response, type `/exit`, then **Stop codespace** at
  <https://github.com/codespaces>. This saves the conversation and stops compute.
- Later connect to that same Codespace over SSH and run `knowledge` again.
- To stop a response early, press Esc. Type `/exit` after it stops.
- `knowledge new` starts a separate conversation with the whole file again.
- To leave an answer running through a phone disconnect, start with
  `tmux new -As knowledge`, then run `knowledge`. Reconnect with the same tmux command.
  Detaching from tmux keeps the Linux process running; stopping the Codespace does not.

Closing the SSH app does not stop Codespaces billing. Stopped Codespaces still
consume storage. GitHub can delete an inactive Codespace after 30 days, so select
**Keep codespace** or keep a separate backup of the data directory. Deletion erases
the local source and conversation. Cache expiry only changes the next input bill.

## Optional Android client commands, if you use Termux

Install `gh` and `openssh` in Termux and sign in to the same GitHub account. Only the
SSH client runs on Android; Claude Code and its data stay in the Linux Codespace.
After allowing storage access with `termux-setup-storage`, a file in Downloads can
be copied with:

```sh
gh codespace cp -c YOUR_CODESPACE ~/storage/downloads/knowledge.md remote:/workspaces/claude-knowledge-data/knowledge.md
gh codespace ssh -c YOUR_CODESPACE
```

Arabic shaping and text direction depend on the Android terminal/version. Stock
Termux 0.118.3 has an open report of disconnected Arabic letters and wrong
direction; its native fix proposal is not merged. Do not assume Arabic display
works there. UTF-8 transport passed local tests; your device's visual rendering
still needs a check. UTF-8 locale settings alone do not fix this.
