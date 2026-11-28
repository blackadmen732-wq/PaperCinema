"""Aethern: a small, stdlib-only toolkit that lets AI agents work on a project cheaply.

Every command answers with a few hundred bytes instead of a file the agent would otherwise read whole:
the project map (`map`), what changed since the agent last looked (`changed`, `impact`), shared notes
(`mem`), a free-model router with a result cache (`ai`), a sandboxed free-model worker (`worker`), a
skills map (`skills`), pinned outside tools (`vendor`) and a promise ledger (`ledger`).

Nothing here knows about any one project. A project describes itself in one `aethern.json`.
"""
__version__ = '0.1.0'
