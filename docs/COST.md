# Paper Cinema — Keeping Claude Usage Low

## Core Rules (AGENTS.md)
- **00**: Use what exists first; search proven tools before building.
- **01**: (Not in excerpt; see AGENTS.md)
- **02a**: Use the cheapest worker tier that can do the job.
- **02**: Send heavy text work to free models (`tools/ai.py`).

## Tier Table

| Tier | Model / Tool | Purpose | When to Use |
|------|--------------|---------|-------------|
| Director | Opus (main session) | Decide quality, verify, assemble, talk to owner | Final judgement, direction |
| Advisor | Fable | Hard design judgement only (folds, fight reads, audits) | Design decisions, not implementation |
| Workers | Haiku (default), Sonnet (if needed) | Installing, testing, wiring, docs, repetitive fixes, clear specs | Any task with a clear brief |
| Free Labour | `tools/ai.py`, `tools/worker.py` | Writing, code drafts, looking at frames, heavy text work | All text/image analysis, code generation |

## Free Labour Commands

**tools/ai.py** (free models for writing, code, vision):
bash
python3 tools/ai.py write "prompt"
python3 tools/ai.py review image.png "question"
python3 tools/ai.py review frames/ --sheet 12 "question"
python3 tools/ai.py think "reasoning task"
python3 tools/ai.py list
python3 tools/ai.py budget


**tools/worker.py** (free models with repo tools):
bash
python3 tools/worker.py "task description"
python3 tools/worker.py --task-file brief.md --steps 40
python3 tools/worker.py --model kimi "task"
python3 tools/worker.py --dry "task"  # preview only


**Rule**: Never spawn Opus/Fable for work a haiku worker or free model can do from a clear brief.
