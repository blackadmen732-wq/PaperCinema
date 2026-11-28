# Interfaces: the contracts any implementation must keep

Aethern is Python and JavaScript today. Rust may later replace a piece where a measurement shows it
is worth it. Callers (agents, `tools/` wrappers, scripts) only ever see the three things below, so a
piece can be swapped without any caller changing:

1. **The command line**: `aethern <command> [args]`, its arguments, stdout and exit code.
2. **The JSON it prints** with `--json`.
3. **The files it reads and writes** in the project.

Anything not written here (Python function names, module layout) is internal and may change.

## Rules every implementation follows

- **Root**: `$AETHERN_ROOT`, else the nearest folder at or above the current directory holding
  `aethern.json`, else the current directory. All project paths are relative to the root.
- **Config**: `aethern.json`, merged over the defaults in `aethern/config.py`. Unknown keys are ignored.
  A replacement reads the same keys and the same defaults.
- **Exit codes**: `0` ok, `1` the check found a problem (missing file, broken promise, unknown id),
  `2` bad usage.
- **Output**: text for people by default; `--json` gives one JSON document on stdout (for `map owner`,
  one JSON object per line, one per file asked). Nothing else goes to stdout in `--json` mode;
  progress and warnings go to stderr.
- **Encoding**: UTF-8, `ensure_ascii` off (names such as 漢字 stay readable).
- **Writes are atomic**: write `<file>.tmp`, then rename over `<file>`, so a crash keeps the old file.
- **Stdlib only**: an implementation may not need a network, a key or a package to answer `map`,
  `changed`, `impact` or `mem`.

## Command contracts (`--json` shapes)

| command | prints |
|---|---|
| `map show ID…` | `[{"id","name","status","does","files":{path: lines \| "dir" \| "glob" \| "missing"},"guide":[...],"command":str\|null,"from":[ids],"to":[ids]}]`; an unknown id is `{"id","error":"unknown id","near":[ids]}` and the exit code is 1 |
| `map find WORDS…` | `[{"id","name","files":[first 3]}]`, best first, at most 8 |
| `map deps ID [--up] [--depth N]` | `[[ids at distance 1], [ids at distance 2], …]` |
| `map owner FILE…` | one line per file: `{"file", "systems":[ids]}` (a system owns a file it lists as code or as guide) |
| `map list` | `[[id, name, status], …]` |
| `map ask Q` | the `show`, `owner` or `find` answer for an id, a path or words |
| `map build` | text; writes the catalogue JSON (below); exit 1 if a listed file is missing |
| `changed [--save] [--as NAME]` | `{"added":[],"modified":[],"removed":[],"files":N,"hashed":N}`; on a first look `{"first_snapshot":true,…}` |
| `impact [--save] [--as NAME]` | `{"changed":{"added","modified","removed"},"systems":{id:[files]},"downstream":[ids]}` |
| `snapshot [--as NAME]` | text |
| `mem get [TOPIC] [--grep W]` | `[{"id","topic","text","at","by"?,"ref"?}]`, newest first |
| `mem add TOPIC TEXT` | text: `added <id>` or `already noted <id>` |
| `events check FILE…` | text; exit 1 if any line is not a valid `aethern-event/2` or `/1` (bad JSON, non-finite numbers, missing ids, duplicate ids and bad evidence are named by line) |
| `events merge FILE… [--out F] [--tol S] [--project P] [--media M]` | `aethern-event/2` JSON Lines, sorted by `t`; one line per project + media + id. Every observation is kept in `evidence`; when they disagree (type, or `t`/`t1` more than S s apart, or different entities) the line has `conflict: true` and `data.conflict_on`, with the most confident observation on top. Exit 1, merging nothing, if any input is malformed. Version-1 lines get P (default: aethern.json `id`, else `name` as a slug) and M; without M, one file's v1 lines get `file:<name>` and v1 lines from several files are refused (exit 1) |
| `events near T FILE… [--window W] [--type X]` | `[event, …]` within ±W s of T, after the same merge |
| `caps [list]` | text: one line per capability, `id  does` |
| `caps find WORDS [--k N]` | `[{"id","does"}]`, best first, at most N (default 5); keyword match on id, tags and description, no AI |
| `caps show ID…` | `[{"id","does","tags","args","out","example"?,"module","run"}]` |
| `call ID [ARGS…]` | `{"cap","ok","exit","ms","out","err"?}`; `out` parsed when the capability says json or jsonl; exit = the capability's exit (0, 1, 2), else 1 |
| `mcp` | MCP over stdio with three tools: `find {task,k?}`, `show {id}`, `call {id,args?}`, same answers as above |
| `ai JOB …` | the answer on stdout, a one-line meta summary on stderr |
| `worker TASK` | progress lines; transcript file in `worker.log_dir` |
| `skills [--check]`, `vendor …`, `ledger …` | text, exit codes as above |

## File contracts

| file | shape |
|---|---|
| catalogue JSON (`catalog.out`, e.g. `systems.json`) | `{"_about", "start_here":[], "golden_path":[], "systems":[{"id","name","does","files":[],"guide":[],"command","status","status_note"}], "connections":[[from,to]]}`, indent 1 |
| `<cache_dir>/snapshot-<name>.json` | `{path: [size_bytes, mtime_ns, sha1_hex]}` |
| `memory_file` (JSON Lines) | a note `{"id": sha1(topic + "\n" + normalised text)[:8], "topic", "text", "at": "YYYY-MM-DD", "by"?, "ref"?}`; a retraction `{"drop": id, "at"}`. Append only. |
| `<cache_dir>/ai/<h[:2]>/<h>.json` | `{"text", "meta"}`, where `h = sha1(json([job, model_chain, messages, max_tokens], sorted keys))`; stale after `cache_ttl_days` by file time |
| `ai.log` (JSON Lines) | `{"model","secs","tokens","total","job","ok","at","cached"?}` |
| job state (`js/state.mjs`) | `{"<parts key>": {id: {"status":"done"\|"failed","hash", …}}}`; `hash` = first 12 hex chars of sha1 of the part's inputs as JSON |
| shared events (JSON Lines) | `aethern-event/2` (`schema/event-2.schema.json`): `{"v":2,"project","media","id","type","t","t1"?,"f"?,"source","method"?,"conf"?,"entities"?,"data"?,"evidence"?:[{"source","t","method"?,"conf"?,"t1"?,"type"?,"entities"?,"data"?,"file"?}],"conflict"?}`; no other top-level fields; unique by project + media + id. Media ids: `film:<name>` (engine, Sonic), VYRN's `v<hash>`/`t<hash>`. Written by Sonic (in Paper Cinema) and VYRN. Version 1 (`schema/event-1.schema.json`, no project/media/evidence/conflict) is still read |
| capability manifest | `aethern-caps/1` (`schema/caps-1.schema.json`): `{"format","module","about"?,"run":[argv],"cwd"?,"caps":[{"id","does","tags"?,"args"?,"out"?,"example"?,"prefix"?}]}`. One per module (`packages/aethern/`, `vyrn/`, `packages/sonic/capabilities.json`); listed in aethern.json `capabilities` as a path or `{"file","args"}` |
| vendor manifest | `{"tools":[{"id","url","commit","licence","size","what","why_here","skill","needs_gpu"?,"needs_gui"?}],"rejected":[{"name","why"}]}` |
| promise ledger | `{"promises":[{"id","promise","why","status":"kept"\|"OPEN","check"}]}` |

## How a Rust (or any) module replaces one piece

1. Build it as a command that keeps one row of the command table and the files it touches,
   byte for byte. For example `aethern-index` answering `changed` and `impact`.
2. Prove it: it passes a contract test that runs the command and compares its stdout, exit code
   and files with the Python version's (today's tests call Python functions directly, so that
   command-level test is the first thing to write before any swap), and `bench/bench.py` shows the
   gain on a real project. No measured gain, no switch.
3. Switch it on with one dispatch line in `aethern/cli.py`: when `aethern.json` names an
   implementation for that command (planned key: `"impl": {"changed": "path/to/aethern-index"}`),
   run it with the same arguments. Callers do not change, and removing the key switches back.

The dispatch key is not built yet, on purpose: there is no second implementation to switch to.

## Where Rust could pay off (measured 28 Nov, Paper Cinema, 863 files)

Nothing in the core is slow today: a change check takes 7 ms, a first full scan 91 ms, a map query
about 20 ms (mostly Python start-up). So there is no measured case for Rust in the core yet.

The candidates are elsewhere, and need their own measurement before any work:
- the change scan, if a project holds large asset trees (hashing is the cost there, and it grows with bytes);
- the per-frame geometry maths in Paper Cinema's audit, jitter and foot-slide tools, which run over
  every frame of a film.
