# Where the pilot's 15.2 million cached tokens went

Measured from the session transcript on 28 Nov 2026 (token counts from the API's own usage fields;
the split of the starting context is characters ÷ 4, an estimate).

## The answer in one line

The pilot itself added about **34k tokens** of context. Each of its 33 requests re-read the whole
session, **472k to 507k tokens**, and 261k of that was there before any work started.

## Per request, during the pilot (33 requests, 05:26:48 to 05:40 UTC)

| part of each request's context | tokens | share |
|---|---|---|
| starting context, before the first word of work | ~261,000 | ~53% |
| the extraction work done earlier in the same session | ~211,000 | ~43% |
| the pilot's own steps and tool output (36 results, 36k characters, largest 5.5k) | ~34,000 by the end | ~7% at most |

Sum over the pilot: 16.2M tokens read from cache (the plugin's before/after difference, 15.2M, counts
slightly fewer requests), 15.7k tokens written.

## What the 261k starting context is

| item | size | tokens (est.) |
|---|---|---|
| tool definitions sent with every request | 415k characters | ~104,000 |
| system prompt (harness, app and project instructions) | 359k characters | ~90,000 |
| names of 1,313 deferred tools (MCP connectors and plugins) | 118k characters | ~29,000 |
| skills listing (about 450 skills) | 64k characters | ~16,000 |
| instructions from 22 MCP servers | 33k characters | ~8,000 |

Nothing in Paper Cinema causes this. It comes from what is connected to the account (connectors,
plugins, skills) and from running a long task in one session.

## What it means for the next benchmark

1. **One fresh session per run.** That removes the 211k of earlier work: at the pilot's 33 requests,
   about 7M fewer cached tokens per run.
2. **A controlled context budget.** The benchmark sessions should run with only the tools the test
   needs (shell, files, git), no extra connectors, plugins or skill packs. The starting context then drops
   from ~261k to the harness's own base. That base has not been measured yet; the first fresh run will
   measure it.
3. **Record usage per run** with the token-usage plugin's `session_cost` on each run's own transcript,
   and the starting context with the first request's usage, so the budget is checked, not assumed.
4. **Same budget for all three environments**, so a heavier environment cannot win by reading more.

Inside Paper Cinema, the lever that is ours is how much an agent *reads*: one system lookup is ~120
tokens through `aethern map show` against ~7,600 for SYSTEMS.md whole (`docs/AETHERN-AUDIT.md`). In the
pilot, tool output was only 7% of the context, so that lever matters far less than the session setup.
