"""MCP server (stdio, JSON-RPC 2.0) with three small tools over every capability: find, show and call.

    aethern mcp          (add to an MCP client as: {"command": "python3", "args": ["packages/aethern/bin/aethern", "mcp"]})

An agent sees three tool definitions, whatever the number of capabilities; it asks `find` for the ones its task needs,
reads one contract with `show` only when it is about to use it, and runs it with `call`. Stdlib only.
"""
import json
import sys

from . import caps as C

TOOLS = [
    {'name': 'find', 'description': 'The few capabilities (Aethern, VYRN, Sonic) that fit a task, best first: id and one line each.',
     'inputSchema': {'type': 'object', 'properties': {'task': {'type': 'string'}, 'k': {'type': 'integer'}}, 'required': ['task']}},
    {'name': 'show', 'description': 'The full contract of one capability: arguments, output, example.',
     'inputSchema': {'type': 'object', 'properties': {'id': {'type': 'string'}}, 'required': ['id']}},
    {'name': 'call', 'description': 'Run a capability with command-line style arguments; returns {cap, ok, exit, ms, out}.',
     'inputSchema': {'type': 'object', 'properties': {'id': {'type': 'string'}, 'args': {'type': 'array', 'items': {'type': 'string'}}},
                     'required': ['id']}},
]


def handle(msg, cfg, caps):
    mid, method, params = msg.get('id'), msg.get('method'), msg.get('params') or {}
    ok = lambda result: {'jsonrpc': '2.0', 'id': mid, 'result': result}
    if method == 'initialize':
        return ok({'protocolVersion': params.get('protocolVersion', '2025-06-18'), 'capabilities': {'tools': {}},
                   'serverInfo': {'name': 'aethern', 'version': '1'}})
    if method == 'ping':
        return ok({})
    if method == 'tools/list':
        return ok({'tools': TOOLS})
    if method == 'tools/call':
        name, a = params.get('name'), params.get('arguments') or {}
        if name == 'find':
            res = [C.brief(c) for c in C.find(caps, a.get('task', ''), int(a.get('k') or 5))]
        elif name == 'show':
            res = C.contract(caps[a['id']]) if a.get('id') in caps else {'error': f'unknown capability {a.get("id")!r}'}
        elif name == 'call':
            res = C.call(cfg, caps, a.get('id', ''), [str(x) for x in a.get('args') or []])
        else:
            return {'jsonrpc': '2.0', 'id': mid, 'error': {'code': -32601, 'message': f'unknown tool {name}'}}
        return ok({'content': [{'type': 'text', 'text': json.dumps(res, ensure_ascii=False)}],
                   'isError': name == 'call' and not res.get('ok', True)})
    if mid is None:
        return None                     # a notification needs no answer
    return {'jsonrpc': '2.0', 'id': mid, 'error': {'code': -32601, 'message': f'unknown method {method}'}}


def main(cfg, inp=sys.stdin, out=sys.stdout):
    caps = C.load(cfg)
    for line in inp:
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            r = {'jsonrpc': '2.0', 'id': None, 'error': {'code': -32700, 'message': 'parse error'}}
        else:
            r = handle(msg, cfg, caps)
        if r is not None:
            out.write(json.dumps(r, ensure_ascii=False) + '\n')
            out.flush()
    return 0
