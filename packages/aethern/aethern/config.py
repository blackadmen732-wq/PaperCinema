"""Find the project root and load its aethern.json, filling every gap with a default.

The root is, in order: an explicit `root` argument, $AETHERN_ROOT, or the nearest folder at or above
the current directory that holds an aethern.json. With none of those the current directory is used,
so every command still works (with defaults) in a project that has not described itself yet.
"""
import json
import os

CONFIG_NAME = 'aethern.json'

DEFAULTS = {
    'name': None,                       # the project's name, used in prompts
    'cache_dir': '.aethern/cache',      # machine-local, never committed
    'memory_file': '.aethern/memory.jsonl',   # shared notes, meant to be committed
    'index_ignore': ['.git', 'node_modules', '__pycache__', '.aethern/cache'],
    'ai': {
        'log': '.aethern/cache/ai-usage.jsonl',
        'system': ('Think silently. Output ONLY the deliverable, after a line containing exactly: FINAL:\n'
                   'Never show your reasoning. If the answer is code, output code only.\n'
                   'Be concrete and brief: numbers, file names. No filler, no apologies, no restating the question.'),
        'omni_key_file': '~/.aethern/omniroute-key',
        'cache': False,                 # off unless the project turns it on
        'cache_ttl_days': 7,
        'models': None,                 # None = the built-in table in router.py
        'order': None,
    },
    'worker': {
        'project': 'You are working in this repo.',
        'model': 'nemotron',
        'log_dir': '.aethern/cache/worker',
        'protect': ['.git/', 'aethern.json'],
        'allow_extra': [],
    },
    'catalog': None,                    # see catalog.py; None = no project map
    'skills': None,                     # see skillmap.py; None = no skills map
    'vendor': {'manifest': 'vendor/MANIFEST.json', 'dir': 'vendor'},
    'ledger': {'file': 'promises.json'},
}


def find_root(start=None):
    if os.environ.get('AETHERN_ROOT'):
        return os.path.realpath(os.environ['AETHERN_ROOT'])
    d = os.path.realpath(start or os.getcwd())
    while True:
        if os.path.isfile(os.path.join(d, CONFIG_NAME)):
            return d
        up = os.path.dirname(d)
        if up == d:
            return os.path.realpath(start or os.getcwd())
        d = up


def _merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


class Config(dict):
    """The merged config plus `root`, with `path()` to turn a project-relative path into an absolute one."""

    def __init__(self, root, data):
        super().__init__(data)
        self.root = root

    def path(self, rel):
        rel = os.path.expanduser(rel)
        return rel if os.path.isabs(rel) else os.path.join(self.root, rel)


def load(root=None):
    root = os.path.realpath(root) if root else find_root()
    p = os.path.join(root, CONFIG_NAME)
    data = {}
    if os.path.isfile(p):
        with open(p, encoding='utf-8') as f:
            data = json.load(f)
    return Config(root, _merge(DEFAULTS, data))
