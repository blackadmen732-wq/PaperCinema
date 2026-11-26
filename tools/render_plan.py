#!/usr/bin/env python3
"""Which frames does the local Blender render still have to do, and who renders what?

    python3 tools/render_plan.py <frames dir> <first frame> <last frame> <workers>

Line 1: how many frames of first..last have no f####.png in the folder yet (that is why a stopped render can
simply be run again — it picks up where it stopped). Then one line per worker: the contiguous ranges ("a-b",
space separated) that worker renders. Blocks are contiguous so each Blender process keeps the same stretch of
the timeline, and a hole in what is already there just splits a block into two ranges.
Used by tools/film.sh step 5; standalone so the shell needs no nested heredoc.
"""
import os
import sys


def main(argv):
    if len(argv) != 5:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    fr, a, b, w = argv[1], int(argv[2]), int(argv[3]), max(1, int(argv[4]))
    # film_modular.py --frames a-b writes Blender frames a+1..b+1 (1-based): timeline frame f is f%04d.png of f+1.
    # This looked for f itself, so a resumed render never found what it had already made.
    todo = [f for f in range(a, b + 1) if not os.path.exists(os.path.join(fr, 'f%04d.png' % (f + 1)))]
    print(len(todo))
    if not todo:
        return 0
    n = min(w, len(todo))
    for i in range(n):
        chunk = todo[i * len(todo) // n:(i + 1) * len(todo) // n]
        runs, s0 = [], chunk[0]
        for x, y in zip(chunk, chunk[1:] + [None]):
            if y != x + 1:
                runs.append('%d-%d' % (s0, x))
                s0 = y
        print(' '.join(runs))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
