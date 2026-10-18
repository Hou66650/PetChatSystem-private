"""Owner-confirmed real-pet traits, kept separate from newly lived virtual events."""
import json
import time
import uuid

from ..db import get_db
from . import companion_service as memory, pet_call_service as calls

OPTIONS = {
    'activity': {'lively': '喜欢活动', 'calm': '走动较少'},
    'vocality': {'quiet': '不太爱叫', 'natural': '自然回应'},
    'greeting': {'greet': '走近，摇尾欢迎', 'sit': '走近，坐下等待', 'sniff': '走近，闻一闻'},
    'comfort': {'sit': '坐在身边', 'lie_down': '在身边趴下', 'affection': '亲昵回应'},
    'play': {'play_bow': '前伏邀请玩耍', 'sniff': '好奇闻一闻', 'happy': '开心回应'},
    'memory': {'remember': '只用于理解往事，不驱动动作'},
    'call_greeting': {}, 'call_comfort': {}, 'call_play': {},
}
LABELS = dict(activity='活动习惯', vocality='叫声习惯', greeting='重逢方式', comfort='陪伴方式',
              play='玩耍习惯', memory='一段真实回忆', call_greeting='重逢原声', call_comfort='陪伴原声', call_play='玩耍原声')


class ImprintError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def init_schema():
    get_db().executescript('''
    CREATE TABLE IF NOT EXISTS pet_imprints(
      id TEXT PRIMARY KEY, owner TEXT NOT NULL, pet INTEGER NOT NULL,
      kind TEXT NOT NULL, value TEXT NOT NULL, evidence TEXT NOT NULL,
      confirmed INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL, confirmed_at REAL);
    CREATE INDEX IF NOT EXISTS pet_imprints_owner ON pet_imprints(owner,pet);
    CREATE UNIQUE INDEX IF NOT EXISTS pet_imprints_active ON pet_imprints(owner,pet,kind)
      WHERE confirmed=1 AND kind!='memory';
    ''')


def evidence(data):
    if not isinstance(data, dict) or data.get('type') not in ('owner', 'media'):
        raise ImprintError('请选择主人回忆或影像依据')
    quote = data.get('quote')
    if not isinstance(quote, str) or not 1 <= len(quote.strip()) <= 400:
        raise ImprintError('请用 1–400 字记录真实依据')
    result = dict(type=data['type'], quote=quote.strip())
    if data['type'] == 'media':
        name = data.get('name')
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 160:
            raise ImprintError('请填写参考文件名称')
        start, end = data.get('start'), data.get('end')
        if type(start) not in (int, float) or type(end) not in (int, float) or not 0 <= start < end <= 7200:
            raise ImprintError('请填写有效的片段起止秒数')
        result.update(name=name.strip(), start=start, end=end)
    return result


def rows(owner, pet):
    return [dict(r) for r in get_db().execute(
        'SELECT * FROM pet_imprints WHERE owner=? AND pet=? ORDER BY created DESC,id', (owner, pet))]


def active(owner, pet):
    if not memory.settings(owner)['enabled']:
        return []
    return [r for r in rows(owner, pet) if r['confirmed']]


def policy(owner, pet):
    result = dict(responses={}, calls={}, vocality='natural', sourceIds=[], activity=None)
    for row in active(owner, pet):
        kind, value = row['kind'], row['value']
        result['sourceIds'].append(row['id'])
        if kind in ('activity', 'vocality'):
            result[kind] = value
        elif kind in ('greeting', 'comfort', 'play'):
            # Templates express a confirmed habit. They are not motion capture.
            result['responses'][kind] = dict(id=row['id'], action=value,
                label=OPTIONS[kind][value], evidence=json.loads(row['evidence']))
        elif kind.startswith('call_'):
            clip = get_db().execute('SELECT id,name,kind,duration FROM pet_calls WHERE owner=? AND pet_id=? AND id=?',
                                   (owner, pet, value)).fetchone()
            if clip and clip['kind'] == kind[5:]:
                result['calls'][clip['kind']] = dict(clip)
    return result


def behavior(owner, pet, base):
    data = policy(owner, pet)
    result = dict(base, imprint=data)
    if data['activity'] and not base.get('sourceIds'):
        lively = data['activity'] == 'lively'
        result.update(mode='lively' if lively else 'calm', idleSeconds=[2, 5] if lively else [12, 20],
                      speedScale=1.08 if lively else .85, reaction='happy' if lively else 'subtle',
                      label='按主人确认的活动习惯', method='owner-confirmed-imprint-v1',
                      summary='根据真实回忆调整活动间隔和速度；采用已有动作，不代表复原个体步态')
    return result


def context(owner, pet):
    return [dict(kind=r['kind'], expression=OPTIONS[r['kind']].get(r['value'], '已确认的原声片段'),
                 evidence=json.loads(r['evidence'])) for r in active(owner, pet)]


def state(owner, pet):
    db = get_db()
    if not db.in_transaction:
        with db:
            db.execute('BEGIN')
            return state(owner, pet)
    clips = calls.state(owner, pet)
    cards = []
    for row in rows(owner, pet):
        cards.append({k:row[k] for k in ('id', 'kind', 'value', 'confirmed', 'created', 'confirmed_at')}
                     | dict(evidence=json.loads(row['evidence'])))
    settings = memory.settings(owner)
    return dict(scope=memory.owner_scope(owner), petId=pet, revision=settings['revision'],
                enabled=bool(settings['enabled']), cards=cards, policy=policy(owner, pet),
                labels=LABELS, options=OPTIONS, originalCalls=clips)


def mutate(owner, pet, data, card_id=None, operation='create'):
    if not isinstance(data, dict) or type(data.get('revision')) is not int:
        raise ImprintError('页面状态不完整，请刷新', 409)
    db = get_db()
    with db:
        db.execute('BEGIN IMMEDIATE')
        if data['revision'] != memory.settings(owner)['revision']:
            raise ImprintError('档案已变化，请刷新后再确认', 409)
        row = db.execute('SELECT * FROM pet_imprints WHERE owner=? AND pet=? AND id=?',
                         (owner, pet, card_id)).fetchone() if card_id else None
        if operation != 'create' and not row:
            raise ImprintError('没有找到这条回忆', 404)
        if operation in ('create', 'edit'):
            kind, value = data.get('kind'), data.get('value')
            if not isinstance(kind, str) or kind not in OPTIONS or not isinstance(value, str):
                raise ImprintError('请选择有效的习惯类型')
            if kind.startswith('call_'):
                clip = db.execute('SELECT kind FROM pet_calls WHERE owner=? AND pet_id=? AND id=?',
                                  (owner, pet, value)).fetchone()
                if not clip or clip['kind'] != kind[5:]:
                    raise ImprintError('请先试听保存属于这只宠物、场景匹配的原声')
            elif value not in OPTIONS[kind]:
                raise ImprintError('该表达方式尚不支持')
            proof = json.dumps(evidence(data.get('evidence')), ensure_ascii=False)
            if operation == 'create':
                if db.execute('SELECT count(*) FROM pet_imprints WHERE owner=? AND pet=?', (owner, pet)).fetchone()[0] >= 32:
                    raise ImprintError('每只宠物最多保留 32 条，请先整理旧记录')
                db.execute('INSERT INTO pet_imprints VALUES (?,?,?,?,?,?,0,?,NULL)',
                           (uuid.uuid4().hex, owner, pet, kind, value, proof, time.time()))
            else:
                db.execute('UPDATE pet_imprints SET kind=?,value=?,evidence=?,confirmed=0,confirmed_at=NULL WHERE id=?',
                           (kind, value, proof, card_id))
        elif operation == 'confirm':
            if data.get('confirmed') is not True:
                raise ImprintError('请确认依据真实，并同意使用所选表达方式')
            if row['kind'].startswith('call_') and not db.execute(
                'SELECT 1 FROM pet_calls WHERE owner=? AND pet_id=? AND id=? AND kind=?',
                (owner, pet, row['value'], row['kind'][5:])).fetchone():
                raise ImprintError('原声已删除，请重新选择')
            if row['kind'] != 'memory':
                db.execute('UPDATE pet_imprints SET confirmed=0,confirmed_at=NULL WHERE owner=? AND pet=? AND kind=?',
                           (owner, pet, row['kind']))
            db.execute('UPDATE pet_imprints SET confirmed=1,confirmed_at=? WHERE id=?', (time.time(), card_id))
        elif operation == 'withdraw':
            db.execute('UPDATE pet_imprints SET confirmed=0,confirmed_at=NULL WHERE id=?', (card_id,))
        elif operation == 'delete':
            db.execute('DELETE FROM pet_imprints WHERE id=?', (card_id,))
        else:
            raise ImprintError('操作不支持')
        memory.invalidate_context(db, owner)
    return state(owner, pet)


def call_audio(owner, pet, kind, revision):
    row = get_db().execute('''SELECT c.audio FROM pet_imprints i
        JOIN pet_calls c ON c.id=i.value AND c.owner=i.owner AND c.pet_id=i.pet AND c.kind=?
        JOIN companion_owners o ON o.owner=i.owner AND o.enabled=1 AND o.revision=?
        JOIN pet_call_settings s ON s.owner=i.owner AND s.pet_id=i.pet AND s.enabled=1
        WHERE i.owner=? AND i.pet=? AND i.kind=? AND i.confirmed=1''',
        (kind, revision, owner, pet, 'call_'+kind)).fetchone()
    if not row:
        raise ImprintError('原声未启用或回忆已变化，请刷新', 409)
    return row['audio']


def forget(db, owner):
    db.execute('DELETE FROM pet_imprints WHERE owner=?', (owner,))
