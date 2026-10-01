# Claude Code in Codespaces

Setup for complete Arabic source files, Opus 5.5 through Concentrate, maximum
effort, adaptive thinking, 1M context and one-hour cache requests.

**Status: local native-client tests passed; live Codespaces/provider tests pending.**

The fresh Codespace installs Claude Code automatically. Add `CONCENTRATE_API_KEY`
as a **Codespaces** secret before creating it. No paid model requests run during
installation.

1. Upload the complete original file to
   `/workspaces/claude-knowledge-data/knowledge.md`.
2. Connect over SSH and run `knowledge`.
3. Stop: `/exit`, then **Stop codespace**. Resume: SSH into that same Codespace
   and run `knowledge` again.

Your source and conversations live outside the repository. Never commit the API
key or private source to this public repository.

Details: [.claude-knowledge/QUICKSTART.md](.claude-knowledge/QUICKSTART.md).
Research and limits:
[.claude-knowledge/RESEARCH-verified.md](.claude-knowledge/RESEARCH-verified.md).

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
