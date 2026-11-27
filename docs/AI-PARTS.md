# Generated parts: a Tripo head on the paper rig (27 Nov 2026)

A generated mesh is one fused shell, so it is never a character. It is a **rigid part**: a head, a hat, a mask,
a plate, a prop on a socket of the one rig. Everything below is data plus two tools; no part code per model.

## The chain (Kojiro's head: 35 credits, ~20 s of Blender)
| step | command | what it does | Kojiro |
|---|---|---|---|
| 1 concept | `python3 tools/tripo.py image --ref <crop> --prompt "..." --out output/tripo/<n>` | Tripo `generate_image` edits a reference crop into the part, alone, front view | 5 credits |
| 2 model | `python3 tools/tripo.py model --image <concept> --version v3.0-20250812 --out ...` | Tripo `image_to_model`, textured | 30 credits, 70 s, 944k faces |
| 3 manifest | an entry in `library/ai-parts.json` | slot, socket, bone, `cut`, `fit`, `faces`, `sheets`, `glow`, `ink` | `kojiro_head_t1` |
| 4 prepare | `$B -b -P tools/ai_part.py -- <id>` | face found from the eye paint and turned to -Y; seams welded; cut under the chin; fitted (chin, height, centred on the eyes and the neck); reduced; paint baked; sheets per facet; ink + glow masks | 944k -> 4,008 facets, 17 s |
| 5 recipe | `library/character-recipes/kojiro-ai.json` | `drop: face, hair`, `add: kojiro_head_t1` | test recipe |
| 6 check | `$B -b -P blender/character/head_compare.py -- --recipe ... --out ... [--light cinematic] [--poses a,b]` | same cameras on any recipe; the head box in metres; a pose sweep | `output/heads/` |
| 7 film | `film.cast.<id>.recipe` in a film file | one actor on the test recipe, production untouched | `film/kojiro-exchange-ai.json` |

Every task's cost is in `output/tripo/ledger.jsonl` (balance before/after). Raw models stay in `output/` (29 MB);
`tools/tripo.py fetch <task>` downloads one again. The prepared part (`assets/models/ai/<id>/`: part.glb, ink.png,
glow.png, report.json; ~230 KB) is committed.

## The look: paper, not a game model
- **Two sheets, chosen by the paint under each facet**: light paint -> `washi_natural`, dark -> `washi_sumi`
  (new: ink-black washi; `card_charcoal`'s lacquer sheen read grey). Colour changes at fold edges, like real origami.
- **Printed ink** for what is too thin for a facet (brows, eye lines, the hairline): `pm.add_paint()` mixes it
  over the washi from `ink.png`. **Glow** from `glow.png`: the eye slits, amber, strength 3.5.
- **Despeckle**: islands under 10 facets join the sheet around them (an ear tip through the hair).

## Size (Mark: "issue the size")
Chin to crown = 0.225 m, the rig's existing head (mask 1.506-1.731). The kept piece (cut just under the chin to
the bun) is 0.284 m; the face is then ~0.15 m wide, a third of the shoulders, eyes at mid-head (~1.61 m).
The old mask was 0.258 m wide: cartoon-wide.

## What went wrong on the way (so nobody repeats it)
| symptom | cause | fix |
|---|---|---|
| HTTP 403 "error code: 1010" | Cloudflare refuses Python's default User-Agent | `tools/tripo.py` sends its own |
| results "NOT DOWNLOADED" | results live on `tripo-data.rg1.data.tripo3d.com`, outside the network list | host added to the environment |
| `v3.5-20260815` "version invalid" | that version is apiv3-only; this key is on the v2 API (`api.tripo3d.ai`) | `v3.0-20250812` |
| head shattered into spikes and holes | 30,724 open edges: the mesh is split along every UV seam; reducing a mesh full of borders fans to them | weld first (UVs per corner survive, the bake reads them) |
| head looked down +X | the service's own frame | turn from the eye paint's direction (0.3 deg off +X), snapped to 90 deg |
| centred 7 cm sideways | the light paint near the cut includes a collar the service added | centre on the eyes |
