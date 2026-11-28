"""VYRN command line. Run from the repo root:  python3 -m vyrn <command> ...

  ingest <video|timeline.json> [--force] [--render final.mp4]   process once (cached by content hash)
  summary <media>                                                  what is in it, in a few lines
  window <media> <t0> <t1>                                         what happened between two times
  when <media> <event-type> [--entity id]                          when does X happen (footstep, cut, sound.onset...)
  track <media> <entity> [--from t] [--to t] [--step n] [--joint name]   how something moved
  relation <media> <a> <b> [--from t] [--to t]                     distance / overlap between two entities
  sync <media> [--expect timeline.json|sonic.json] [--visual] [--tol s]   is the sound in sync
  evidence <media> <t> [--entity id] [--width px]                  one frame or crop as a PNG path (look only if needed)
  list                                                             everything processed so far
  backends                                                         every stage's default and alternatives, with licences

<media> is a store id (from ingest), or the original file path. Add --json for machine output.
"""
import argparse, json, sys
from vyrn import query
from vyrn.store import resolve, load_index


def main(argv=None):
    ap = argparse.ArgumentParser(prog='vyrn', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('cmd'); ap.add_argument('args', nargs='*')
    ap.add_argument('--json', action='store_true'); ap.add_argument('--force', action='store_true')
    ap.add_argument('--render'); ap.add_argument('--entity'); ap.add_argument('--joint')
    ap.add_argument('--from', dest='t0', type=float); ap.add_argument('--to', dest='t1', type=float)
    ap.add_argument('--step', type=int, default=4); ap.add_argument('--expect'); ap.add_argument('--visual', action='store_true')
    ap.add_argument('--tol', type=float, default=0.1); ap.add_argument('--width', type=int, default=320)
    a = ap.parse_args(argv)
    c, x = a.cmd, a.args
    if c == 'ingest':
        from vyrn.ingest import ingest
        mid, res = ingest(x[0], force=a.force, render=a.render)
        print(json.dumps({'media': mid, **res}) if a.json else f'{mid} ' + ' '.join(f'{k}={v}' for k, v in res.items() if k != 'store'))
        return
    if c == 'backends':
        from vyrn.backends import table
        print(table()); return
    if c == 'list':
        idx = load_index()
        print(json.dumps(idx, indent=1) if a.json else '\n'.join(f"{k} {v['kind']} {v['source']}" for k, v in idx.items()))
        return
    st = resolve(x[0])
    if c == 'summary':
        txt, data = query.summary(st)
    elif c == 'window':
        txt, data = query.window(st, float(x[1]), float(x[2]))
    elif c == 'when':
        txt, data = query.when(st, x[1], a.entity)
    elif c == 'track':
        txt, data = query.track(st, x[1], a.t0, a.t1, a.step, a.joint)
    elif c == 'relation':
        txt, data = query.relation(st, x[1], x[2], a.t0, a.t1)
    elif c == 'sync':
        txt, data = query.sync(st, a.expect, a.tol, a.visual)
    elif c == 'evidence':
        txt, data = query.evidence(st, float(x[1]), a.entity, width=a.width)
    else:
        ap.error(f'unknown command {c}')
    print(json.dumps(data, default=str) if a.json else txt)


if __name__ == '__main__':
    main(sys.argv[1:])
