# Findings verified on 1 October 2026

## Highest reasoning configuration within Opus 5.5

Use Claude Code **2.1.280 or newer**; the installed and tested version is **2.1.286**.

| Choice | Setting |
|---|---|
| Exact model and provider | `anthropic/claude-opus-5-5[1m]` |
| Reasoning | `CLAUDE_CODE_EFFORT_LEVEL=max`, `--effort max` |
| Thinking | Adaptive; always on for Opus 5.5 |
| Context | 1,000,000 tokens |
| Output headroom | `CLAUDE_CODE_MAX_OUTPUT_TOKENS=128000` |
| Full source | `--append-system-prompt-file`, containing the entire original UTF-8 file |
| Stable resume | `--system-prompt-snapshot on` |
| Cache | `CLAUDE_CODE_PROMPT_CACHE_TTL=1h` |
| Conversation compaction | `DISABLE_COMPACT=1` |
| Task role | Custom non-coding `Knowledge` output style |
| Service speed | Standard; fast mode costs more and does not increase intelligence |

`max` is the highest reasoning setting, not a guarantee of the highest answer
quality on every question. Anthropic recommends measuring effort levels on your
own tasks; higher effort can cost more, take longer, and sometimes overthink.
Its maximum-capability setting matches your preference. A paid **Max subscription**
and **max effort** are different things. No fixed thinking budget, sampling tweak,
or extra CPU makes this model more intelligent. Opus 5.5 rejects non-default
temperature/top-p/top-k values, so omit those parameters.

The output limit includes hidden thinking and visible text. A 128K ceiling is
permission, not an automatic charge or an instruction to write a huge answer.
The launcher requests concise Arabic answers without lowering reasoning effort.

The `[1m]` label makes Claude Code allocate the extended context behind a gateway;
the native client removes that label from the outgoing model ID. This was checked.

## What “every word” can mean

The complete original file can be included in every main request. Caching reuses
its computed prefix, preserving the original source rather than summarizing it.
The source still occupies its full context allocation. The model does not acquire
permanent trained memory from it, and no setting guarantees perfect comprehension,
recall, or that every word influences every answer. An acknowledgment proves none
of those properties. Exact short citations and checks of exceptions help you assess
an answer without removing any source text.

Referencing a file with `@` or asking the model to read it does not prove full
inclusion; tool limits can truncate content. The prepared launcher places the full
file directly in the prompt and verifies its hash on resume. Editing it requires a
new session or restoring the original file. The source, instructions, history,
and output must fit the finite context window; an unlimited unsummarized history
cannot fit. Start another full-source conversation if the window fills.

Your **124,325-token Gemini estimate is not an Opus token count**. Arabic token
counts vary by tokenizer. Use the gateway's token-counting endpoint if supported,
or actual request usage including new input, cache reads, and cache writes.
We have not received or counted your real knowledge file.

## Price and cache expiry

The live Concentrate catalog and Anthropic documentation agree on these standard
Opus 5.5 rates. Concentrate advertises zero platform markup on tokens.

| Input operation | Per million tokens | Source-only cost if it is 124,325 Opus tokens |
|---|---:|---:|
| Uncached input | $4 | $0.4973 |
| First 5-minute cache write | $5 | $0.6216 |
| First 1-hour cache write | $8 | $0.9946 |
| Matching cache read | $0.20 | $0.0249 |

Thinking plus visible output costs **$20 per million tokens**: 10,000 output tokens
cost $0.20. Instructions, conversation history, new cache writes, taxes, and
account-specific prices are additional. The source-only examples are estimates,
not complete question prices. One-hour caching breaks even by the third matching
request; five-minute caching by the second, assuming cache hits.

**Default TTL: 5 minutes. Longest documented TTL: 1 hour.** A matching cache reuse
refreshes its TTL without a separate refresh fee, while the request still pays
cache-read charges. Time is measured from the request's start, so generating the
answer consumes part of the period. There is no documented permanent or 24-hour
TTL for this model. You can keep reusing a prefix within its TTL; background warming
also costs money. Expiry means another cache write, not loss of a saved conversation.
Keep the provider, key, source, effort, and preceding prompt content stable.
Concentrate isolates caches between API keys.

Caching is not the only possible discount generally: Anthropic offers 50%-off
Batch API processing, subscriptions offer included usage subject to limits, and
Concentrate advertises negotiated enterprise rates. Ordinary interactive Claude
Code with your Concentrate key does not automatically receive any of those.
The catalog establishes no cheaper public self-service uncached rate for your
existing setup. We retain Codespaces, Claude Code, Concentrate, and the whole dump.

## Beginner and compatibility facts

Codespaces is the remote Linux computer; SSH connects your phone's keyboard/screen.
Claude Code is the Linux program; Concentrate supplies and bills model access.
GitHub Free personal accounts include 120 core-hours (approximately 60 hours on a
2-core machine) and 15 GB-month storage. A 2-core Codespace is sufficient; the model
runs remotely at the provider. Codespaces compute/storage and model tokens are
separate bills. Use Codespaces secrets, not Actions secrets or committed API keys.

The launcher keeps source and transcripts outside the Git repository, under
`/workspaces/claude-knowledge-data`, and extends Claude transcript retention to
3,650 days. GitHub's own inactive-Codespace deletion is separate. Use **Keep codespace**
or a backup. See QUICKSTART.md for the short stop/resume procedure.

Native UTF-8 source and Arabic questions passed local request checks. That does not
verify Android text shaping, right-to-left ordering, cursor behavior, or your app's
key shortcuts. A Claude Code issue documents a display-only Arabic problem on
macOS; it is not proof of an Android failure. Separately, a Termux 0.118.3 user on
Android 15 reports disconnected Arabic letters and wrong direction in issue 5252;
the native RTL/shaping pull request 5179 is still open and unmerged. This is a
concrete reason not to promise proper Arabic display in stock Termux. It does not
establish how your particular Android 14 app renders text. UTF-8 locale settings
do not fix a terminal's missing shaping/bidirectional support. The Android
terminal/version must be checked separately. No reshaping or reversing of the
stored source is performed.

## Actual test status

**Passed locally, using real Claude Code and a local mock endpoint:** native 2.1.286
installation; byte-for-byte inclusion of a 945,075-byte Arabic source with mixed
line endings; one copy of the entire source in both requests; identical system
prefix after process exit/resume; restored prior question and same session ID;
`max` effort; `thinking: adaptive`; 128K output ceiling; native 1M context allocation;
1-hour cache markers; custom non-coding style; no retrieval tools; missing-key and
changed-source refusal; interactive Arabic input transport; `/exit`.

**Passed in the fresh 2-core Codespace:** old Codespace deletion; installation;
SSH; the selected `CONCENTRATE_API_KEY` secret reaching a login shell; the large
native-client/mock checks above; stopping until GitHub reported `Shutdown` and
reconnecting over SSH; the same source hash, saved session and secret after restart.
The native interactive UI also passed: initial theme/notice/trust screens; Arabic
input transport; full-source inclusion; `/exit`; and reopening the same conversation
with its previous answer displayed and no new request. That UI check used a local
stub and made zero paid calls.
The tested file-copy command requires `gh codespace cp --expand` with the given
constant remote paths. Downloading and uploading the Arabic fixture preserved
all 511 bytes and the same SHA-256 hash. No knowledge or API key is committed to
the public repo.

**Passed with real Concentrate/Opus:** two questions over the entire 511-byte
synthetic Arabic file. Both requests used `max` effort and adaptive thinking,
included the source intact, and exposed no tools. The first answer correctly
applied a distant exception; the second correctly used both the source and the
previous question. They shared the same saved session. Provider usage confirmed
one-hour cache writes and a **2,251-token cache read on the second request**.

**Live totals: 5,140 logical input tokens**, including system, history, cache reads
and writes; **883 output tokens**, including 671 thinking tokens. This is below the
50,000-personal-input allowance even when conservatively counting all input.
The CLI's cumulative list-price estimate is **$0.0412062**; the Concentrate account
dashboard is authoritative for charges. No further paid tests are needed.

The tests reserved 27,929 raw request bytes. Every invocation shares a persistent
guard: at most four inference requests, 40,000 total raw request bytes, and at most
2,048 output tokens per request. Failed attempts count before forwarding. Normal
user sessions retain the full 128K output headroom; the live test's small output
ceiling is isolated from the user's setup.

**Still unverified:** the original file's Opus token count and your Android app's
glyph shaping, direction, cursor and keyboard. Large-file checks used localhost
and establish client inclusion, not perfect large-source comprehension. Real
answers and cache counts above came from the live provider, not the mock.

## Sources

- [Opus 5.5 specification, rates, context, and output](https://platform.claude.com/docs/en/models/opus-5-5/overview)
- [Effort and Opus 5.5 recommendations](https://platform.claude.com/docs/en/build-with-claude/effort)
- [Opus 5.5 prompting and calibration](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5)
- [Claude Code model and gateway context](https://code.claude.com/docs/en/model-config)
- [Environment variables](https://code.claude.com/docs/en/env-vars)
- [Prompt file and snapshot/resume semantics](https://code.claude.com/docs/en/cli-reference)
- [Output styles](https://code.claude.com/docs/en/output-styles)
- [Caching prices, refresh, and lifetime](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [Gateway pass-through, fallback retries, and token counting](https://code.claude.com/docs/en/llm-gateway-protocol)
- [Concentrate model catalog](https://api.concentrate.ai/v1/models/claude-opus-5-5)
- [Concentrate Claude Code setup](https://concentrate.ai/docs/integrations/claude-code)
- [Concentrate cache TTL and key isolation](https://concentrate.ai/docs/api-reference/endpoint/prompt-caching)
- [Concentrate pricing](https://concentrate.ai/pricing)
- [Codespaces SSH](https://docs.github.com/en/codespaces/developing-in-a-codespace/using-github-codespaces-with-github-cli)
- [Codespaces billing](https://docs.github.com/en/billing/concepts/product-billing/github-codespaces)
- [Codespaces retention and Keep codespace](https://docs.github.com/en/codespaces/setting-your-user-preferences/configuring-automatic-deletion-of-your-codespaces)
- [Arabic display-only report, macOS](https://github.com/anthropics/claude-code/issues/95667)
- [Arabic display report, Termux 0.118.3](https://github.com/termux/termux-app/issues/5252)
- [Termux native RTL/shaping proposal, currently unmerged](https://github.com/termux/termux-app/pull/5179)
- [Supplemental user experience on effort](https://www.claudecodeclub.ai/blog/claude-code-effort-levels), anecdotal and not an Arabic full-source evaluation
