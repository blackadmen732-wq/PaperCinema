"""Process media ONCE. A file whose bytes (sha256) and processor version are unchanged is never processed again."""
import json, os, resource, time
from vyrn.store import Store, cache_dir, sha256_file, save_index, load_index, project_id

VERSION = {'native': 1, 'video': 2, 'audio': 2, 'fuse': 2}


def _has_cv2():
    try:
        import cv2  # noqa: F401
        return True
    except ImportError:
        return False


def kind_of(path):
    if path.endswith('.json'):
        with open(path) as fh:
            head = fh.read(200)
        if 'paper-cinema-timeline' in head:
            return 'native'
        raise ValueError(f'{path}: not a Paper Cinema timeline (format "paper-cinema-timeline")')
    return 'video'


def ingest(path, force=False, render=None):
    t_start = time.time()
    sha = sha256_file(path)
    kind = kind_of(path)
    media_id = f'{kind[0]}{sha[:11]}'
    spath = os.path.join(cache_dir(), f'{media_id}.sqlite')
    idx = load_index()
    want = dict(VERSION, picture=kind == 'native' or _has_cv2())
    if not force and os.path.exists(spath) and idx.get(media_id, {}).get('version') == want:
        return media_id, {'cached': True, 'store': spath}
    if os.path.exists(spath):
        for ext in ('', '-wal', '-shm'):
            if os.path.exists(spath + ext):
                os.remove(spath + ext)
    st = Store(spath)
    work = os.path.join(cache_dir(), media_id)
    os.makedirs(work, exist_ok=True)
    if kind == 'native':
        from vyrn import native
        res = native.ingest_timeline(path, st, media_id, sha)
    else:
        from vyrn import video, audio
        if video.cv2 is None:
            # no OpenCV: sound only (enough for `sync --expect`); the picture stages need opencv-python-headless
            info = video.probe(path)
            st.put_media(id=media_id, kind='video', source=path, sha256=sha, fps=info['fps'], duration=info['duration'],
                         frames=int(round(info['duration'] * info['fps'])), width=info['width'], height=info['height'],
                         processors={'video': 'none (OpenCV missing)'}, stats={'audio': info['audio']})
            res = {'picture': 'skipped: pip install opencv-python-headless (Apache-2.0) for cuts, camera and subjects'}
        else:
            res = video.ingest(path, st, media_id, sha, work)
        res['audio'] = audio.ingest(path, st, sha)
        res['fused'] = fuse(st)
    if render:
        st.db.execute('UPDATE media SET stats = json_set(coalesce(stats, "{}"), "$.render", ?)', (render,))
    res['seconds'] = round(time.time() - t_start, 2)
    res['peak_rss_mb'] = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)
    st.db.execute('UPDATE media SET stats = json_set(coalesce(stats, "{}"), "$.ingest", json(?))', (json.dumps(res),))
    st.commit()
    export_events(st, os.path.join(cache_dir(), f'{media_id}.events.jsonl'))
    save_index(media_id, {'kind': kind, 'source': path, 'sha256': sha, 'version': want, 'store': spath})
    return media_id, dict(res, store=spath)


def fuse(st, tol=0.15):
    """audio-visual impacts: a motion freeze (picture) and a sharp sound onset within tol seconds are one event,
    an 'av.impact', carrying the measured offset (positive = sound late). A freeze with no sound, or a hit with no
    freeze, stays a single-sense event with its own confidence."""
    ons = st.events(types=['sound.onset'])
    used, n = set(), 0
    for e in st.events(types=['motion.freeze']):
        c = [o for o in ons if abs(o['t0'] - e['t0']) <= tol and o['id'] not in used]
        if not c:
            continue
        o = min(c, key=lambda o: abs(o['t0'] - e['t0']))
        used.add(o['id'])
        st.put_event(f'av.impact.{n:02d}', 'av.impact', e['t0'], e['t1'], e['f'], e['entities'],
                     {'picture': e['id'], 'sound': o['id'], 'sound_t': o['t0'],
                      'offset_ms': round((o['t0'] - e['t0']) * 1000, 1)},
                     round(min(e['conf'], o['conf']), 3), 'freeze+onset', 'vyrn.fuse')
        n += 1
    # footsteps: a foot planting in the picture and a thud in the sound within 0.1 s are one footstep
    m = 0
    thuds = [o for o in ons if o['id'] not in used and str(o['data'].get('guess', '')).startswith('thud')]
    for e in st.events(types=['contact.foot-ground']):
        c = [o for o in thuds if abs(o['t0'] - e['t0']) <= 0.1 and o['id'] not in used]
        if not c:
            continue
        o = min(c, key=lambda o: abs(o['t0'] - e['t0']))
        used.add(o['id'])
        st.put_event(f'av.footstep.{m:02d}', 'av.footstep', e['t0'], None, e['f'], e['entities'],
                     {'picture': e['id'], 'sound': o['id'], 'offset_ms': round((o['t0'] - e['t0']) * 1000, 1)},
                     round(max(e['conf'], o['conf']), 3), 'foot-plant+thud', 'vyrn.fuse')
        m += 1
    st.commit()
    return n + m


def export_events(st, path):
    """the shared event format (aethern-event/2, agreed with Sonic): one JSON object per line, timeline-compatible
    ids, unique by project + media + id. media is VYRN's media id (the file name's stem); project from aethern.json"""
    media_id = os.path.basename(path).split('.')[0]
    project = project_id()
    with open(path + '.tmp', 'w', encoding='utf-8') as fh:
        for e in st.events():
            fh.write(json.dumps({'v': 2, 'project': project, 'media': media_id, 'id': e['id'], 'type': e['type'], 't': e['t0'],
                                 **({'t1': e['t1']} if e['t1'] != e['t0'] else {}),
                                 **({'f': e['f']} if e['f'] is not None else {}),
                                 'source': e['source'], 'method': e['method'], 'conf': e['conf'],
                                 'entities': e['entities'], 'data': e['data']}, ensure_ascii=False) + '\n')
    os.replace(path + '.tmp', path)
