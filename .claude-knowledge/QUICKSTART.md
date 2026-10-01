# Short workflow — Linux and live model verified

These files configure Linux Claude Code in GitHub Codespaces. Your Android app is
only the SSH client. No Anthropic subscription is required for a Concentrate key.

Codespaces SSH, Concentrate authentication, maximum effort, actual one-hour cache
reuse and conversation persistence after stopping/restarting passed tests. The
two small live requests used 5,140 input tokens in total, including system and
cached input, plus 883 output tokens. Your Android app's display remains untested.

Prepared Codespace: `claude-knowledge-wv5gr9v9wq9xhvg4q`.

## Once your fresh Codespace is configured

1. Rename the original phone file to `knowledge.md`. Keep its complete contents.
2. Upload it to `/workspaces/claude-knowledge-data/knowledge.md` in the Codespace.
3. In the remote Linux terminal, run `knowledge` and ask your question in Arabic.

First launch: select a theme, press Enter through the introductory notice, then
select **Yes, I trust this folder** for your own prepared folder. The Concentrate
secret supplies authentication; you do not need an Anthropic login.

At the trust menu, **No, exit** is selected first: press Down, then Enter. Those
first-launch screens and `/exit`/reopening were tested in the Codespace.

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

## Recommended Android 14 setup

Use **Termux for GitHub authentication and transport**, and **ConnectBot for the
Arabic terminal display**. Claude Code and the source remain in Linux Codespaces.
Stock Termux has a reported Arabic shaping/direction bug. The official ConnectBot
development build below includes the merged Arabic shaping and paragraph bidi
implementation for Android 12 and later. Its stable Play Store release predates
that implementation, so use this specific official development build.

1. Install [official Termux 0.118.3](https://github.com/termux/termux-app/releases/download/v0.118.3/termux-app_v0.118.3%2Bgithub-debug_universal.apk)
   and [official ConnectBot Arabic build](https://github.com/connectbot/connectbot/releases/download/git-v1.10.9-161-gbec5c69a/ConnectBot-git-v1.10.9-161-gbec5c69a-oss.apk).
   Allow installation from your browser when Android asks.
2. Open Termux and paste:

   ```sh
   apt update && apt full-upgrade -y &&
   curl -fL https://raw.githubusercontent.com/amywisconsin12121-gif/blsnk/main/.claude-knowledge/android-setup.sh -o ~/android-setup.sh &&
   bash ~/android-setup.sh
   ```

   Allow storage access, sign into GitHub as **amywisconsin12121-gif** using its
   browser code, and set Termux battery usage to **Unrestricted** in Android settings.
   The full package upgrade is required before using curl on a fresh Termux
   bootstrap. If curl reports `CANNOT LINK EXECUTABLE` with a missing OpenSSL
   symbol, these same direct `apt` commands repair the partial upgrade;
   `pkg` checks mirrors using curl and can fail while curl is broken.
3. In ConnectBot: **Manage pubkeys → + → Generate**, name it `claude`, select
   **Ed25519**, and generate. Open that key's menu and select **Copy public key**.
   In Termux run `cs key`, paste that public key, and press Enter. The private
   key stays inside ConnectBot.
4. Put your complete original file in phone **Downloads**, named `knowledge.md`.
   In Termux run `cs upload`, then `cs`. Upload verifies the complete file's hash
   and makes no model request. Keep Termux running while using ConnectBot.
5. Add a ConnectBot SSH host: **`codespace@127.0.0.1:2222`**. In its settings,
   **Use pubkey authentication**, select the `claude` key. Connect and accept the
   initial server fingerprint for your GitHub-authenticated tunnel. In the Linux
   shell run:

   ```sh
   printf '%s\n' 'العربية متصلة من اليمين إلى اليسار'
   ```

   Check that the letters join and the sentence reads correctly. Then run
   `knowledge`. Its first Arabic input and answer also need a visual check on
   your actual device; server-side UTF-8 tests cannot establish pixel-perfect
   phone rendering. If the input cursor misbehaves, compose the question in
   Android's text box and paste it as one block.

The phone helper's SSH tunnel, public-key authentication, repeated connections,
Arabic byte transport, and complete-file upload were tested against your actual
Codespace with **zero model calls**. The ConnectBot download's SHA-256 matched
GitHub's official release digest:
`d1407371489c3995574c8c0e05be3ad801fe1fcee1373bae4943ec67093f4031`.
Physical Android display remains unverified until your phone check.

**Stop:** finish the answer, type `/exit`, then `exit` in the Linux shell. In
Termux press Ctrl+C to close the tunnel, then run `cs stop` to stop Codespaces
compute. **Resume:** in Termux run `cs`, reconnect the same ConnectBot host, then
run `knowledge` in Linux. These steps keep the entire saved conversation.

Your full source reaches the model when you ask a question. Installation,
`cs upload`, the Arabic `printf` check, and `knowledge check` make no model request.
The copy helper uses the tested `gh codespace cp --expand` with fixed remote paths.

Sources: [Termux Arabic issue](https://github.com/termux/termux-app/issues/5252),
[unmerged Termux fix](https://github.com/termux/termux-app/pull/5179),
[merged ConnectBot shaping](https://github.com/connectbot/termlib/pull/278),
[official ConnectBot release](https://github.com/connectbot/connectbot/releases/tag/git-v1.10.9-161-gbec5c69a).
