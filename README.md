# Claude Code in Codespaces

Setup for complete Arabic source files, Opus 5.5 through Concentrate, maximum
effort, adaptive thinking, 1M context and one-hour cache requests.

**Status: Linux Codespaces, live Opus, caching and stop/resume tested. Android
display still needs a check on your SSH app.**

Your prepared Codespace is `claude-knowledge-wv5gr9v9wq9xhvg4q`.

The fresh Codespace installs Claude Code automatically. Add `CONCENTRATE_API_KEY`
as a **Codespaces** secret before creating it. No paid model requests run during
installation.

1. Upload the complete original file to
   `/workspaces/claude-knowledge-data/knowledge.md`.
2. Connect over SSH and run `knowledge`:

   ```sh
   gh codespace ssh -c claude-knowledge-wv5gr9v9wq9xhvg4q
   knowledge
   ```

3. Stop: `/exit`, then **Stop codespace**. Resume: SSH into that same Codespace
   and run `knowledge` again.

Your source and conversations live outside the repository. Never commit the API
key or private source to this public repository.

Details: [.claude-knowledge/QUICKSTART.md](.claude-knowledge/QUICKSTART.md).
Research and limits:
[.claude-knowledge/RESEARCH-verified.md](.claude-knowledge/RESEARCH-verified.md).

Two small live requests used **5,140 total input tokens** and **883 output tokens**.
Both answered correctly; the second reused **2,251 cached tokens**. Large-file
inclusion was tested separately against localhost, with no paid model call.

## Developer live test

Only the synthetic, tiny source is used by this test:

```sh
python3 .claude-knowledge/live_smoke_test.py
```

All invocations share one persistent budget: at most four paid inference requests,
40,000 total raw request bytes including system/history/source, and 2,048 output
tokens per request. Failed attempts count. Normal user sessions keep full output
headroom. Deleting or changing the budget file to repeat live tests would bypass
the agreed test allowance.
