# Sonic (standalone package)

Sonic turns a folder of sound files into a catalog an agent can query ("a heavy steel impact under 0.5 s"),
and picks the right sound for each event in a scene. Nothing in this folder imports a host app: it needs
Node 18+ and ffmpeg, nothing else. Paper Cinema uses it through `engine/sonic.mjs`; CINEVORA can take
this folder as it is.

| File | What it is |
| --- | --- |
| `sonic.mjs` | The library: `scan`, `query`, `pick`, `applyToCues`, `pickForEvents`, `sharedEvents`, `configure` |
| `cli.mjs` | `scan`, `pick EVENTS.jsonl`, `query WORDS` |
| `vocab.json` | Default words, event kinds and event → sound rules (kept equal to Paper Cinema's `library/sonic-vocab.json` by a test) |
| `tests/sonic.test.mjs` | Copies the package to a temp folder and runs it there |

## Use it

```
node sonic/cli.mjs scan                       # reads ./sfx, writes ./sonic.catalog.json
node sonic/cli.mjs pick events.jsonl --out picks.jsonl
node sonic/cli.mjs query material=steel action=impact dur<0.5
```

Paths default to the working directory; change them with `--roots`, `--catalog`, `--vocab`, `--cache`,
or `configure({...})` in code.

## Events in and out (aethern-event/1)

In: one JSON object per line. The kind is `data.kind` or the last part of `type` (`combat.clash` → clash),
the moment is `data.peakAt` or `t`, the other `data` fields (material, intensity, speed) feed the pick,
and the first entity is who made it. Kinds the vocab has no rule for are skipped.

Out: one `sonic.pick` event per event that got a sound, with `data.sound`, `data.start` (when the file
starts, so its peak or onset lands on `t`) and `data.aim`. Check a file with `aethern events check`.

## A host's own cues

`applyToCues(cues, { eventOf })` re-picks a host's cue list. Without `eventOf`, a cue's event is `cue.event`.
Paper Cinema passes its own reader for older cues whose event is only in the cue id.
