# Motion capture sources

## CMU Graphics Lab Motion Capture Database — `cmu/`

Subject 2, trials 07, 08, 09: **swordplay**, 120 fps, 40.0 s in total
(18.8 s + 12.5 s + 8.6 s). Skeleton `02.asf`, motion `02_*.amc`.

Source: https://mocap.cs.cmu.edu/search.php?subjectnumber=%25&motion=sword

**Licence.** CMU states: *"This data is free for use in research projects. You may include this data
in commercially-sold products."* That satisfies AGENTS.md rule 6 (commercial-safe licences only).
The database was created with funding from NSF EIA-0196217.

Fetched over http because the server's https chain is missing an intermediate certificate, so TLS
verification fails. These are public research files with no secrets in them, and nothing is sent to
the server, so plain http is acceptable here. TLS verification was NOT disabled anywhere.

### Converted clips

`tools/mocap_cmu.py` retargets these onto our 23-bone rig via `library/mocap-bonemap.json`:

| Clip | From | Keys | Length |
|---|---|---|---|
| `library/mocap/sword-a.json` | 02_07.amc | 451 | 18.8 s |
| `library/mocap/sword-b.json` | 02_08.amc | 300 | 12.5 s |
| `library/mocap/sword-c.json` | 02_09.amc | 207 | 8.6 s |

All three carry the same 30 channels as the video-captured `iaido-cut.json`, so anything that
consumes one consumes the others.
