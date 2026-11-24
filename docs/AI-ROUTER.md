# AI router: free models do the volume, Claude directs

`tools/ai.py` sends work to free model endpoints the environment already has keys for, so Claude's usage is
spent on direction and verification, not on bulk text or on looking at every frame.

## Jobs
| Command | What it is for | Goes to |
|---|---|---|
| `write "..."` | scenes, monologues, titles, descriptions | Qwen (Cerebras) → Qwen (Groq) → GPT-OSS → Nemotron → Kimi |
| `code "..."` | routine code, scripts, conversions | GPT-OSS (Cerebras) → Qwen → Nemotron |
| `think "..."` | hard reasoning, plans, diagnosis | Nemotron 550B → Kimi K3.1 Pro → GPT-OSS |
| `review <image or frames dir> "question"` | a model LOOKS at a still, a sheet or a whole shot | Nemotron VL → GLM VL |
| `list` | what is reachable right now, and how fast | — |
| `budget` | calls made, tokens, time: Claude usage saved | — |

`review` on a folder samples frames (`--sheet 12`) into one contact sheet, so the model sees the whole shot.
`--model <name>` forces one. `--out file` saves the answer. Paid models (OpenRouter) stay off unless
`AI_ALLOW_PAID=1` and the account has credit.

## Measured here
| Model | Job | Speed |
|---|---|---|
| Qwen 3.8 (Cerebras) | write, code, quick | ~0.6 s |
| GPT-OSS 120B (Cerebras) | code, think | ~0.3 s |
| Nemotron 3 Ultra 550B (NVIDIA) | think, write | ~1.2 s |
| Nemotron 3.5 VL 120B (NVIDIA) | **review images** | ~0.7 s |
| Kimi K3.1 Pro (NVIDIA) | think, write | ~24 s |
| Qwen / GPT-OSS (Groq) | fallback | varies |
| Kimi / GLM (OpenRouter) | paid | needs credit at openrouter.ai |

## Rules
- Claude still decides what is good, what ships and what the owner sees. The free models draft and critique.
- A free model's review is a second opinion, not the verdict: check it against the stills and the audit tool.
- Rendering is not text work: that goes to the free Kaggle GPU (`gpu/kaggle_blender/`), not here.
- No keys in files: the environment's proxy injects them (AGENTS.md rule 7).
