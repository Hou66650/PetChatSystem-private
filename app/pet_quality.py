"""Hash-bound quality decisions. No Flask dependency; also used by the local reviewer.

Only the local operator can record evidence. Public studio checkboxes cannot
write these decisions. Missing, stale and unknown decisions always fail closed.
"""
import hashlib
import json
import time

STAGES = ('inputs', 'geometry', 'rig', 'motion')
LABELS = dict(inputs='参考照片一致性', geometry='身体结构', rig='骨骼与蒙皮', motion='网格动作')
SCHEMA = '''CREATE TABLE IF NOT EXISTS pet_studio_quality(
 task TEXT NOT NULL, stage TEXT NOT NULL, fingerprint TEXT NOT NULL,
 status TEXT NOT NULL, evidence TEXT NOT NULL, updated REAL NOT NULL,
 PRIMARY KEY(task,stage));'''


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def fingerprints(db, task):
    assets = {slot: digest(raw) for slot, raw in db.execute(
        "SELECT slot,data FROM pet_studio_assets WHERE task=? AND slot IN ('front','left','right','back','detail','model','adapted')", (task,))}
    refs = {k: v for k, v in assets.items() if k in ('front', 'left', 'right', 'back', 'detail')}
    def stamp(value):
        return digest(json.dumps(value, sort_keys=True).encode())
    inputs = stamp({'schema': 1, 'references': refs})
    geometry = stamp([inputs, assets['model']]) if 'model' in assets else None
    row = db.execute('SELECT id,source_hash,report FROM pet_studio_adaptations WHERE task=?', (task,)).fetchone()
    rig = stamp([geometry, assets['adapted'], list(row)]) if geometry and 'adapted' in assets and row and row[1] == assets['model'] else None
    return dict(inputs=inputs, geometry=geometry, rig=rig, motion=rig)


def state(db, task):
    marks = fingerprints(db, task)
    records = {r[0]: r for r in db.execute(
        'SELECT stage,fingerprint,status,evidence FROM pet_studio_quality WHERE task=?', (task,))}
    result = {}
    for stage in STAGES:
        row = records.get(stage)
        valid = row and marks[stage] and row[1] == marks[stage]
        result[stage] = {'status': row[2] if valid else 'unknown',
                         'reason': json.loads(row[3]).get('notes', '') if valid else '尚未审核或素材已变化'}
    return result


def require(db, task, through):
    result = state(db, task)
    for stage in STAGES[:STAGES.index(through)+1]:
        if result[stage]['status'] != 'pass':
            raise ValueError(LABELS[stage] + '未通过质量审核：' + result[stage]['reason'])


def record(db, task, stage, fingerprint, status, evidence):
    """Caller holds BEGIN IMMEDIATE; never approve a stale inspection bundle."""
    if stage not in STAGES or status not in ('pass', 'fail', 'unknown'):
        raise ValueError('无效审核阶段或结论')
    if not db.execute('SELECT 1 FROM pet_studio_tasks WHERE id=?', (task,)).fetchone():
        raise ValueError('档案不存在')
    current = fingerprints(db, task)[stage]
    if not current or current != fingerprint:
        raise ValueError('审核素材已变化，请重新导出并检查')
    if not evidence.get('notes', '').strip() or not evidence.get('files'):
        raise ValueError('审核必须包含说明与截图/录像等证据')
    index = STAGES.index(stage)
    if status == 'pass' and index:
        require(db, task, STAGES[index-1])
    db.execute('INSERT OR REPLACE INTO pet_studio_quality VALUES (?,?,?,?,?,?)',
               (task, stage, current, status, json.dumps(evidence, ensure_ascii=False), time.time()))
    # A changed upstream decision requires fresh downstream review, even when
    # the same assets are retained. Revocation also removes the equip pointer.
    for downstream in STAGES[index+1:]:
        db.execute('DELETE FROM pet_studio_quality WHERE task=? AND stage=?', (task, downstream))
    db.execute('DELETE FROM pet_studio_equipped WHERE task=?', (task,))
