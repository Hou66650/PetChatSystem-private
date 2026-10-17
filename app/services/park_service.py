"""Opt-in public presence, serialized across workers; public assets only."""
import json
import math
import secrets
import time
from ..db import get_db
from . import portal_service, growth_service

clock = time.time
TTL = 12
CAPACITY = 12
ACTIONS = {'idle', 'happy', 'sniff', 'ball', 'sleep'}

class ParkError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status

def init_schema():
    get_db().executescript('''CREATE TABLE IF NOT EXISTS park_presence(
        owner TEXT PRIMARY KEY, id TEXT UNIQUE NOT NULL, token TEXT NOT NULL,
        spec TEXT NOT NULL, x REAL NOT NULL, z REAL NOT NULL, yaw REAL NOT NULL,
        action TEXT NOT NULL, action_at REAL NOT NULL, updated REAL NOT NULL);
    CREATE INDEX IF NOT EXISTS park_updated ON park_presence(updated);''')

def point(data):
    values = []
    for key in ('x', 'z', 'yaw'):
        value = data.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or abs(value)>10000 or not math.isfinite(value):
            raise ParkError('位置无效')
        values.append(float(value))
    x, z, yaw = values
    if (x/8)**2 + (z/6)**2 > 1.001:
        raise ParkError('请在乐园草坪内活动')
    return x, z, math.atan2(math.sin(yaw), math.cos(yaw))

def snapshot(owner):
    now = clock()
    rows = get_db().execute('SELECT * FROM park_presence WHERE updated>? ORDER BY id', (now-TTL,)).fetchall()
    return dict(capacity=CAPACITY, count=len(rows), serverTime=now,
                players=[dict(id=r['id'], mine=r['owner']==owner, spec=json.loads(r['spec']),
                              x=r['x'], z=r['z'], yaw=r['yaw'],
                              action=r['action'] if now-r['action_at']<5 else 'idle',
                              actionAt=r['action_at']) for r in rows])

def join(owner, data):
    pet = data.get('pet')
    if type(pet) is not int or pet not in (1, 2, 3, 4):
        raise ParkError('请选择一位伙伴')
    spec = portal_service.pet_spec(owner, str(pet))
    if spec.get('custom') or not spec['model'].startswith('/static/models/'):
        raise ParkError('私人定制模型暂未开放公共展示，请选择其他标准伙伴。', 409)
    profile = growth_service.get(get_db(), owner, pet)
    public = {k: spec[k] for k in ('model', 'height', 'name', 'id')}
    if profile:
        public['name'] = profile['name']
    now, db = clock(), get_db()
    with db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('DELETE FROM park_presence WHERE updated<=?', (now-TTL,))
        if db.execute('SELECT count(*) FROM park_presence WHERE owner!=?', (owner,)).fetchone()[0] >= CAPACITY:
            raise ParkError('乐园暂时满员，请稍后再来。', 409)
        angle = secrets.randbelow(360)*math.pi/180
        token, identity = secrets.token_hex(24), secrets.token_hex(12)
        db.execute('INSERT OR REPLACE INTO park_presence VALUES (?,?,?,?,?,?,?,?,?,?)',
                   (owner, identity, token, json.dumps(public, ensure_ascii=False),
                    math.cos(angle)*5, math.sin(angle)*3.5, 0, 'idle', now, now))
    return dict(token=token, **snapshot(owner))

def update(owner, data, leave=False):
    now, db = clock(), get_db()
    with db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT * FROM park_presence WHERE owner=?', (owner,)).fetchone()
        token = data.get('token')
        if not row or not isinstance(token, str) or len(token)!=48 or any(c not in '0123456789abcdef' for c in token) or not secrets.compare_digest(token, row['token']) or row['updated']<=now-TTL:
            raise ParkError('游玩已结束或已在另一页面开启，请重新入园。', 409)
        if leave:
            db.execute('DELETE FROM park_presence WHERE owner=?', (owner,))
            return dict(ok=True)
        elapsed = now-row['updated']
        if elapsed < .35:
            raise ParkError('同步过于频繁', 429)
        x, z, yaw = point(data)
        if math.hypot(x-row['x'], z-row['z']) > min(elapsed, 2)*3.5+.4:
            raise ParkError('移动距离过大，请重新同步位置。', 422)
        action = data.get('action', 'idle')
        if not isinstance(action, str) or action not in ACTIONS:
            raise ParkError('互动无效')
        at = now if action != row['action'] else row['action_at']
        db.execute('UPDATE park_presence SET x=?,z=?,yaw=?,action=?,action_at=?,updated=? WHERE owner=?',
                   (x, z, yaw, action, at, now, owner))
    return snapshot(owner)
