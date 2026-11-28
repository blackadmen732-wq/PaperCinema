"""VYRN perception store: one SQLite file per piece of media, written once, queried many times.

Why SQLite: it is in the Python standard library, needs no server, is a single file that can be copied or
cached, and lets an agent ask narrow questions (one entity, one time window) without loading everything.

Every observation carries:
  * a time (seconds) and a frame number,
  * a confidence in [0, 1] (1 = ground truth from the source environment),
  * the method that produced it (so a neural backend can be swapped in and compared),
  * where it applies, a pointer to evidence (a frame or a crop on disk, made on demand).

Tables
  media      what was processed (content hash, fps, size, which processors and versions)
  entities   things with a persistent identity: actors, weapons, blobs, the camera
  samples    one row per entity per frame: screen box (normalised 0..1), world position when known, velocity
  joints     per-joint positions for skeletons (native sources only, or a pose backend)
  events     anything with a time: cuts, contacts, footsteps, impacts, sound onsets, cues; t0..t1 intervals
  relations  pairwise spatial relations over intervals: contact, near, overlap, occlusion
  signals    dense per-frame or per-hop curves (motion energy, loudness, camera pan) stored as compact arrays
  evidence   frames and crops already extracted, so the same picture is never decoded twice
  calibration measured error of each method (from vyrn/bench), so an answer can state its own uncertainty
"""
import json, os, sqlite3, hashlib, time
from array import array

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS media (
  id TEXT PRIMARY KEY, kind TEXT, source TEXT, sha256 TEXT, fps REAL, duration REAL, frames INTEGER,
  width INTEGER, height INTEGER, processors TEXT, created REAL, stats TEXT);
CREATE TABLE IF NOT EXISTS entities (
  id TEXT PRIMARY KEY, kind TEXT, label TEXT, parent TEXT, source TEXT, method TEXT,
  first_f INTEGER, last_f INTEGER, confidence REAL, info TEXT);
CREATE TABLE IF NOT EXISTS samples (
  entity TEXT, f INTEGER, t REAL, x REAL, y REAL, w REAL, h REAL,
  wx REAL, wy REAL, wz REAL, vx REAL, vy REAL, speed REAL, visible INTEGER, conf REAL,
  PRIMARY KEY (entity, f));
CREATE TABLE IF NOT EXISTS joints (
  entity TEXT, joint TEXT, f INTEGER, sx REAL, sy REAL, wx REAL, wy REAL, wz REAL, conf REAL,
  PRIMARY KEY (entity, joint, f));
CREATE TABLE IF NOT EXISTS events (
  id TEXT PRIMARY KEY, type TEXT, t0 REAL, t1 REAL, f INTEGER, entities TEXT, data TEXT,
  conf REAL, method TEXT, source TEXT);
CREATE INDEX IF NOT EXISTS ev_t ON events (t0);
CREATE INDEX IF NOT EXISTS ev_type ON events (type, t0);
CREATE TABLE IF NOT EXISTS relations (
  a TEXT, b TEXT, kind TEXT, t0 REAL, t1 REAL, f0 INTEGER, f1 INTEGER, value REAL, conf REAL, method TEXT);
CREATE TABLE IF NOT EXISTS signals (
  name TEXT PRIMARY KEY, rate REAL, t0 REAL, unit TEXT, method TEXT, data BLOB);
CREATE TABLE IF NOT EXISTS evidence (
  key TEXT PRIMARY KEY, f INTEGER, t REAL, kind TEXT, box TEXT, path TEXT, bytes INTEGER);
CREATE TABLE IF NOT EXISTS calibration (
  method TEXT, quantity TEXT, error REAL, unit TEXT, n INTEGER, measured TEXT, PRIMARY KEY (method, quantity));
"""


def sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for b in iter(lambda: fh.read(chunk), b''):
            h.update(b)
    return h.hexdigest()


def cache_dir():
    """output/vyrn/ inside the repo (output/ is never committed), overridable with VYRN_CACHE."""
    d = os.environ.get('VYRN_CACHE') or os.path.join(os.getcwd(), 'output', 'vyrn')
    os.makedirs(d, exist_ok=True)
    return d


class Store:
    def __init__(self, path):
        self.path = path
        self.db = sqlite3.connect(path)
        self.db.executescript(SCHEMA)
        self.db.execute('PRAGMA journal_mode=WAL')

    # ---------- writing ----------
    def put_media(self, **m):
        m.setdefault('created', time.time())
        for k in ('processors', 'stats'):
            if isinstance(m.get(k), (dict, list)):
                m[k] = json.dumps(m[k])
        cols = ','.join(m)
        self.db.execute(f'INSERT OR REPLACE INTO media ({cols}) VALUES ({",".join("?" * len(m))})', list(m.values()))

    def put_entity(self, id, kind, label=None, parent=None, source='', method='', first_f=None, last_f=None,
                   confidence=1.0, info=None):
        self.db.execute('INSERT OR REPLACE INTO entities VALUES (?,?,?,?,?,?,?,?,?,?)',
                        (id, kind, label or id, parent, source, method, first_f, last_f, confidence,
                         json.dumps(info) if info is not None else None))

    def put_samples(self, rows):
        self.db.executemany('INSERT OR REPLACE INTO samples VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', rows)

    def put_joints(self, rows):
        self.db.executemany('INSERT OR REPLACE INTO joints VALUES (?,?,?,?,?,?,?,?,?)', rows)

    def put_event(self, id, type, t0, t1=None, f=None, entities=(), data=None, conf=1.0, method='', source=''):
        self.db.execute('INSERT OR REPLACE INTO events VALUES (?,?,?,?,?,?,?,?,?,?)',
                        (id, type, t0, t0 if t1 is None else t1, f, json.dumps(list(entities)),
                         json.dumps(data or {}), conf, method, source))

    def put_relation(self, a, b, kind, t0, t1, f0, f1, value, conf=1.0, method=''):
        self.db.execute('INSERT INTO relations VALUES (?,?,?,?,?,?,?,?,?,?)', (a, b, kind, t0, t1, f0, f1, value, conf, method))

    def put_signal(self, name, rate, values, unit='', method='', t0=0.0):
        self.db.execute('INSERT OR REPLACE INTO signals VALUES (?,?,?,?,?,?)',
                        (name, rate, t0, unit, method, array('f', [float(v) for v in values]).tobytes()))

    def put_calibration(self, method, quantity, error, unit, n):
        self.db.execute('INSERT OR REPLACE INTO calibration VALUES (?,?,?,?,?,?)',
                        (method, quantity, error, unit, n, time.strftime('%Y-%m-%d')))

    def commit(self):
        self.db.commit()

    # ---------- reading ----------
    def q(self, sql, *args):
        return self.db.execute(sql, args).fetchall()

    def media(self):
        r = self.db.execute('SELECT * FROM media').fetchone()
        if not r:
            return None
        cols = [d[0] for d in self.db.execute('SELECT * FROM media').description]
        m = dict(zip(cols, r))
        for k in ('processors', 'stats'):
            m[k] = json.loads(m[k]) if m.get(k) else {}
        return m

    def signal(self, name):
        r = self.db.execute('SELECT rate, t0, unit, data FROM signals WHERE name=?', (name,)).fetchone()
        if not r:
            return None
        a = array('f'); a.frombytes(r[3])
        return {'rate': r[0], 't0': r[1], 'unit': r[2], 'values': a}

    def events(self, t0=None, t1=None, types=None):
        sql, args = 'SELECT id,type,t0,t1,f,entities,data,conf,method,source FROM events WHERE 1=1', []
        if t0 is not None:
            sql += ' AND t1 >= ?'; args.append(t0)
        if t1 is not None:
            sql += ' AND t0 <= ?'; args.append(t1)
        if types:
            sql += ' AND (' + ' OR '.join('type LIKE ?' for _ in types) + ')'
            args += [t.replace('*', '%') for t in types]
        out = []
        for r in self.db.execute(sql + ' ORDER BY t0', args):
            out.append({'id': r[0], 'type': r[1], 't0': r[2], 't1': r[3], 'f': r[4], 'entities': json.loads(r[5]),
                        'data': json.loads(r[6]), 'conf': r[7], 'method': r[8], 'source': r[9]})
        return out

    def entities(self):
        cols = ['id', 'kind', 'label', 'parent', 'source', 'method', 'first_f', 'last_f', 'confidence', 'info']
        return [dict(zip(cols, r)) for r in self.db.execute('SELECT * FROM entities ORDER BY id')]

    def samples(self, entity, f0=None, f1=None):
        sql, args = 'SELECT f,t,x,y,w,h,wx,wy,wz,vx,vy,speed,visible,conf FROM samples WHERE entity=?', [entity]
        if f0 is not None:
            sql += ' AND f >= ?'; args.append(f0)
        if f1 is not None:
            sql += ' AND f <= ?'; args.append(f1)
        cols = ['f', 't', 'x', 'y', 'w', 'h', 'wx', 'wy', 'wz', 'vx', 'vy', 'speed', 'visible', 'conf']
        return [dict(zip(cols, r)) for r in self.db.execute(sql + ' ORDER BY f', args)]

    def calibration(self):
        return {(r[0], r[1]): {'error': r[2], 'unit': r[3], 'n': r[4], 'measured': r[5]}
                for r in self.db.execute('SELECT * FROM calibration')}


def open_store(media_id, create=False):
    path = os.path.join(cache_dir(), f'{media_id}.sqlite')
    if not create and not os.path.exists(path):
        raise FileNotFoundError(f'no VYRN store for {media_id}; run: python3 -m vyrn ingest <file>')
    return Store(path)


def resolve(ref):
    """A media reference is a store id, a path to a .sqlite store, or the original media file (found by hash)."""
    if os.path.isfile(ref) and ref.endswith('.sqlite'):
        return Store(ref)
    if os.path.isfile(ref):
        idx = load_index()
        sha = sha256_file(ref)
        for mid, row in idx.items():
            if row.get('sha256') == sha:
                return open_store(mid)
        raise FileNotFoundError(f'{ref} has not been ingested; run: python3 -m vyrn ingest {ref}')
    return open_store(ref)


def load_index():
    p = os.path.join(cache_dir(), 'index.json')
    return json.load(open(p)) if os.path.exists(p) else {}


def save_index(media_id, row):
    idx = load_index()
    idx[media_id] = row
    p = os.path.join(cache_dir(), 'index.json')
    tmp = p + '.tmp'
    json.dump(idx, open(tmp, 'w'), indent=1)
    os.replace(tmp, p)
