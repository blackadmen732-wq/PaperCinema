# Aethern core

A small, dependency-free toolkit that lets AI agents work on a project without reading it whole.
Every command answers in a few hundred bytes. Python 3.9+ (standard library only); Node 18+ for
`vendor` and `ledger`. Extracted from Paper Cinema, which still runs on it.

```
python3 bin/aethern help
```

## Commands

| job | command | answers |
|---|---|---|
| orient | `map show ID [ID..]` | one system: what it does, its files with line counts, guide, command, links in and out |
| | `map find WORDS` · `map owner FILE` · `map deps ID [--up] [--depth N]` · `map list` · `map ask Q` | which systems match / own a file / feed or are fed |
| change | `changed [--save]` · `impact [--save]` · `snapshot` | files added, modified, removed since *your* last look, and the systems they touch |
| notes | `mem add TOPIC "fact"` · `mem get TOPIC` · `mem get --grep WORD` · `mem topics` · `mem drop ID` | shared facts, one JSON line each, deduplicated |
| labour | `ai write\|code\|think\|quick "prompt"` · `ai review IMG\|DIR "q"` · `ai list` · `ai budget` | free models with a fallback chain, a usage log and a result cache |
| | `worker "task" [--steps N] [--dry]` | a free model with read, list, search, write, patch, run, look and map tools, sandboxed |
| build | `map build` · `skills [--check]` · `vendor [--check\|--list\|ID]` · `ledger [--open]` | regenerate the map and the skills page, pin outside tools, run promise checks |

`--json` on `map`, `changed`, `impact` and `mem` gives machine-readable output. Exit 0 means ok.

## A project describes itself in `aethern.json`

Put it at the project root. Every section is optional; what is missing falls back to the defaults
in `aethern/config.py`. See `aethern.example.json`.

- `catalog`: where the system table is (`source`, `section_start`, `section_end`), the JSON it builds
  (`out`) and the `connections` between systems. Table rows look like
  ``| `ID` | **Name** | does | `files` | `guides` | `command` | ✅ |``
- `ai`: `system` prompt, `log`, `cache` (on/off) and `cache_ttl_days`, optional `models` / `order`.
- `worker`: the `project` line every step starts with, `protect`ed paths, `log_dir`, `model`.
- `skills`: skills folder, output page, preamble, and `groups` as data (`prefix`, `suffix`, `names`).
- `cache_dir` (machine-local, never commit it) and `memory_file` (meant to be committed).

## For an agent

1. `aethern help` (1.3 KB) instead of the project guide.
2. `aethern map ask <id | file | words>` instead of reading the system catalogue.
3. `aethern changed` at the start of a turn: only what moved since your snapshot; `--save` when done.
4. `aethern mem get <topic>` before deciding something that may already be decided.
5. Hand text and image work to `aethern ai` / `aethern worker` where the free models are reachable.

## Safety

The worker never leaves the project root, only runs allow-listed commands, refuses commands that
delete, reset or publish (`rm`, `find -delete`, `git clean`, `git reset --hard`, `git checkout -- `,
`git push`, `curl | sh`), and never writes protected paths. Keys are never stored in files: the
router sends `proxy-injected` and expects the network proxy to add the real key, or reads the
OmniRoute key from the file named in config.

## Layout

```
bin/aethern        launcher
aethern/           config, catalog (map), index (changes), memory, router (ai), worker, skillmap, cli
js/                state.mjs (hash-keyed resume), vendor.mjs, ledger.mjs, dom-stub.mjs
tests/             python3 -m unittest discover -s tests ; node --test tests/js.test.mjs
bench/bench.py     measures what it saves on a real project
```

## Tests

```
python3 -m unittest discover -s tests
node --test tests/js.test.mjs
```

## Licence

Not chosen yet. See `LICENSE-NOTE.md`.
