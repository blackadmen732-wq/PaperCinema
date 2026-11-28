#!/usr/bin/env python3
"""BENCH: grade VYRN's external (video) perception against the native ground truth of the same scene.

  python3 -m vyrn.bench.synth --out output/vyrn-bench/duel      # once: the test scene
  python3 -m vyrn.bench.run output/vyrn-bench/duel               # ingest both, measure, write results.json

Each ingest runs in a fresh process so time and peak memory belong to that ingest alone.
Measured: cuts, sound onsets (timing, decoy rejection), the planted sync fault, impacts (motion freeze vs the
engine's blade contacts), tracking (box IoU per actor, coverage, identity fragmentation), footsteps; then the
results are written into the calibration table of the video store so later answers can quote their own error.
"""
import json, os, subprocess, sys, time
import numpy as np

from vyrn.store import resolve
from vyrn.video import iou
from vyrn import query


def ingest_fresh(path):
    t = time.time()
    p = subprocess.run([sys.executable, '-c', 'import json,sys,resource\nfrom vyrn.ingest import ingest\n'
                        'mid,res=ingest(sys.argv[1],force=True)\n'
                        'res["peak_rss_mb"]=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,1)\n'
                        'print(json.dumps({"media":mid,**res}))', path], capture_output=True, text=True, check=True)
    r = json.loads(p.stdout.strip().splitlines()[-1])
    r['wall_s'] = round(time.time() - t, 2)
    return r


def match_times(truth, found, tol):
    """greedy one-to-one matching of time lists; returns pairs, misses, extras"""
    pairs, used = [], set()
    for t in sorted(truth):
        c = [(abs(f - t), i) for i, f in enumerate(found) if i not in used and abs(f - t) <= tol]
        if c:
            d, i = min(c); used.add(i); pairs.append((t, found[i]))
    return pairs, [t for t in truth if t not in [p[0] for p in pairs]], [f for i, f in enumerate(found) if i not in used]


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else 'output/vyrn-bench/duel'
    tl_path, mp4 = base + '.timeline.json', base + '.mp4'
    tl = json.load(open(tl_path))
    fps = tl['film']['fps']
    R = {'scene': {'frames': tl['film']['frames'], 'fps': fps, 'size': [tl['film']['width'], tl['film']['height']]}}
    R['ingest_native'] = ingest_fresh(tl_path)
    R['ingest_video'] = ingest_fresh(mp4)
    nat, vid = resolve(R['ingest_native']['media']), resolve(R['ingest_video']['media'])
    # second call: the cache must answer without processing
    t = time.time(); subprocess.run([sys.executable, '-m', 'vyrn', 'ingest', mp4], capture_output=True, check=True)
    R['cached_reingest_s'] = round(time.time() - t, 3)

    # ---- cuts ----
    tc = [c / fps for c in tl['cuts'] if c > 0]
    fc = [e['t0'] for e in vid.events(types=['cut'])]
    pairs, miss, extra = match_times(tc, fc, 1.01 / fps)
    R['cuts'] = {'truth': len(tc), 'found': len(fc), 'hit': len(pairs), 'missed': len(miss), 'false': len(extra),
                 'frame_error': [round((f - t) * fps, 2) for t, f in pairs]}

    # ---- sound onsets vs the cues actually placed in the mix ----
    cues = sorted({e['t'] for e in tl['events'] if e['type'] == 'cue'})
    ons = [e['t0'] for e in vid.events(types=['sound.onset'])]
    swells = [e['t0'] for e in vid.events(types=['sound.swell'])]
    pairs, miss, extra = match_times(cues, ons, 0.05)
    err = [abs(f - t) * 1000 for t, f in pairs]
    decoys = tl.get('truth', {}).get('decoys', [])
    R['sound'] = {'cues': len(cues), 'onsets': len(ons), 'hit': len(pairs), 'missed': [round(m, 3) for m in miss],
                  'false_hits': [round(x, 3) for x in extra], 'mae_ms': round(float(np.mean(err)), 2) if err else None,
                  'max_ms': round(float(np.max(err)), 2) if err else None,
                  'decoys': len(decoys), 'decoys_labelled_swell': sum(1 for d in decoys if any(-0.05 <= s - d <= 0.25 for s in swells)),
                  'decoys_counted_as_hits': sum(1 for d in decoys if any(-0.05 <= o - d <= 0.25 for o in extra))}

    # ---- the planted sync fault (synthetic scene only) and the independent check against the picture ----
    late = tl.get('truth', {}).get('sound_late')
    if late:
        txt, data = query.sync(vid, tl_path, tol=0.15, visual=True)
        flagged = [r for r in data['rows'] if r.get('offset_ms') is not None and abs(r['offset_ms']) > 1000 / (2 * fps)]
        hit = [r for r in flagged if r.get('why') == late['event']]
        R['sync_fault'] = {'planted': f"{late['event']} +{late['seconds'] * 1000:.0f} ms",
                           'found': [f"{r['why']} {r['offset_ms']:+.0f} ms" for r in flagged],
                           'correct': bool(hit) and len(flagged) == 1,
                           'measured_ms': hit[0]['offset_ms'] if hit else None}
    vt, vd = query.verify(vid, tl_path, tol=0.1)
    R['verify'] = vt.splitlines()
    # ---- what kind of sound: thuds vs footstep sounds, ringing vs clashes ----
    oev = vid.events(types=['sound.onset'])
    thud = [e['t0'] for e in oev if str(e['data'].get('guess', '')).startswith('thud')]
    ring = [e['t0'] for e in oev if str(e['data'].get('guess', '')).startswith('ringing')]
    fs_t = [e['t'] for e in tl['events'] if e['type'] == 'footstep']
    cl_t = [e['t'] for e in tl['events'] if e['type'] in ('blade-contact', 'impact')]
    p1, m1, x1 = match_times(fs_t, thud, 0.1)
    p2, m2, x2 = match_times(cl_t, ring, 0.1)
    R['sound_kinds'] = {'footsteps_heard_as_thud': f'{len(p1)}/{len(fs_t)}', 'thuds_not_footsteps': len(x1),
                        'clashes_heard_as_ringing': f'{len(p2)}/{len(cl_t)}', 'ringing_not_clash': len(x2)}
    vtxt, vdata = query.sync(vid, tol=0.15)
    R['sync_visual_only'] = vtxt.splitlines()[:6]

    # ---- impacts: the engine's contact frame vs the video's motion freeze ----
    ti = [e['t'] for e in tl['events'] if e['type'] in ('blade-contact', 'impact')]
    fi = [e['data'].get('impact_t', e['t0']) for e in vid.events(types=['motion.freeze'])]
    pairs, miss, extra = match_times(ti, fi, 1.01 / fps)
    R['impacts'] = {'truth': len(ti), 'found': len(fi), 'hit': len(pairs), 'missed': [round(m, 3) for m in miss],
                    'false': [round(x, 3) for x in extra],
                    'note': 'blade contacts with a hit-stop freeze the picture; the final impact has no hit-stop'}

    fa = [e['t0'] for e in vid.events(types=['av.impact'])]
    pairs, miss, extra = match_times(ti, fa, 1.01 / fps)
    R['impacts_av'] = {'truth': len(ti), 'found': len(fa), 'hit': len(pairs), 'missed': [round(m, 3) for m in miss],
                       'false': [round(x, 3) for x in extra], 'note': 'picture freeze + sound hit, fused'}

    # ---- tracking: each actor's projected box vs the best video track box, per frame ----
    W, H = tl['film']['width'], tl['film']['height']
    ents = [e['id'] for e in vid.entities()]
    vs = {e: {r['f']: r for r in vid.samples(e)} for e in ents}
    trk = {}
    for actor in [a['id'] for a in tl['actors']]:
        ns = {r['f']: r for r in nat.samples(actor)}
        ious, ids, switches, last = [], [], 0, None
        for f, r in ns.items():
            if r['x'] is None or not r['visible']:
                continue        # only grade frames where the actor is actually on screen
            nb = (r['x'], r['y'], r['w'], r['h'])
            best, bid = 0.0, None
            for e in ents:
                v = vs[e].get(f)
                if v:
                    u = iou(nb, (v['x'], v['y'], v['w'], v['h']))
                    if u > best:
                        best, bid = u, e
            ious.append(best)
            if best >= 0.3:
                if last and bid != last:
                    switches += 1
                last = bid; ids.append(bid)
        trk[actor] = {'mean_iou': round(float(np.mean(ious)), 3), 'frames_iou_0.5': round(float(np.mean(np.array(ious) >= 0.5)), 3),
                      'distinct_ids': len(set(ids)), 'id_changes': switches}
    R['tracking'] = trk
    R['entities_found'] = len(ents)

    # ---- footsteps ----
    fsteps = [e['t'] for e in tl['events'] if e['type'] == 'footstep']
    vfoot = [e['t0'] for e in vid.events(types=['contact.foot-ground'])]
    pairs, miss, extra = match_times(fsteps, vfoot, 2.01 / fps)
    fav = [e['t0'] for e in vid.events(types=['av.footstep'])]
    pa, ma, xa = match_times(fsteps, fav, 2.01 / fps)
    R['footsteps_av'] = {'found': len(fav), 'hit_within_2_frames': len(pa), 'false': len(xa)}
    R['footsteps'] = {'truth': len(fsteps), 'found': len(vfoot), 'hit_within_2_frames': len(pairs),
                      'false': len(extra), 'mean_abs_frames': round(float(np.mean([abs(f - t) * fps for t, f in pairs])), 2) if pairs else None}

    # ---- calibration: what each method's answers can claim ----
    if R['sound']['mae_ms'] is not None:
        vid.put_calibration('spectral-flux', 'onset_time', R['sound']['mae_ms'], 'ms', R['sound']['hit'])
    vid.put_calibration('hist32x3', 'cut_recall', R['cuts']['hit'] / max(1, R['cuts']['truth']), 'share', R['cuts']['truth'])
    vid.put_calibration('framediff', 'impact_recall', R['impacts']['hit'] / max(1, R['impacts']['truth']), 'share', R['impacts']['truth'])
    vid.commit()
    out = base + '.results.json'
    json.dump(R, open(out, 'w'), indent=1)
    print(json.dumps(R, indent=1))


if __name__ == '__main__':
    main()
