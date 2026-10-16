"""One bounded local Blender worker; private immutable inputs and stale-result guards."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import uuid

from flask import current_app
from ..config import BASE_DIR
from ..db import get_db
from . import pet_quality_service as quality

LOCK = threading.BoundedSemaphore(1)
CHECKS = ['appearance', 'walk', 'run', 'sit', 'sleep', 'eat', 'head', 'paws']


def init_schema():
    get_db().executescript('''CREATE TABLE IF NOT EXISTS pet_studio_adaptations(
        task TEXT PRIMARY KEY, id TEXT NOT NULL, source_hash TEXT NOT NULL,
        status TEXT NOT NULL, report TEXT NOT NULL DEFAULT '{}', updated REAL NOT NULL);
    ''')
    # A process restart cannot resume a Blender subprocess from an old worker.
    with get_db():
        get_db().execute("UPDATE pet_studio_adaptations SET status='failed',report=? WHERE status='running'",
                         (json.dumps({'error':'服务已重启，请重新适配'}, ensure_ascii=False),))


def state(task_id):
    row = get_db().execute('SELECT * FROM pet_studio_adaptations WHERE task=?', (task_id,)).fetchone()
    return {'id':row['id'], 'status':row['status'], 'report':json.loads(row['report']), 'updated':row['updated']} if row else None


def executable():
    return os.getenv('BLENDER_EXECUTABLE', r'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe')


def start(task_id, mode, forward):
    if mode not in ('auto', 'template-skin') or forward not in ('-Y','+Y','+X','-X'):
        raise ValueError('请选择有效的适配方式与正面方向')
    if not Path(executable()).is_file(): raise ValueError('此服务器未配置 Blender，请联系管理员')
    db = get_db()
    row = db.execute("SELECT data FROM pet_studio_assets WHERE task=? AND slot='model'", (task_id,)).fetchone()
    if not row: raise ValueError('请先导入并确认模型外貌')
    quality.require(task_id, 'geometry')
    if not LOCK.acquire(blocking=False): raise ValueError('Blender 正在处理另一个模型，请稍后再试')
    raw = row['data'];digest = hashlib.sha256(raw).hexdigest();job = uuid.uuid4().hex
    try:
        with db:
            db.execute('BEGIN IMMEDIATE')
            current = db.execute("SELECT data FROM pet_studio_assets WHERE task=? AND slot='model'", (task_id,)).fetchone()
            if not current or hashlib.sha256(current['data']).hexdigest() != digest:
                raise ValueError('模型已变化，请刷新后重试')
            quality.require(task_id, 'geometry')
            db.execute('DELETE FROM pet_studio_equipped WHERE task=?', (task_id,))
            db.execute('INSERT OR REPLACE INTO pet_studio_adaptations VALUES (?,?,?,?,?,?)',
                       (task_id, job, digest, 'running', '{}', time.time()))
            db.execute("DELETE FROM pet_studio_assets WHERE task=? AND slot IN ('adapted','blend')", (task_id,))
        app = current_app._get_current_object()
        threading.Thread(target=_worker, args=(app, task_id, job, digest, raw, mode, forward), daemon=True).start()
    except Exception:
        LOCK.release()
        raise


def _worker(app, task_id, job, digest, raw, mode, forward):
    try:
        with tempfile.TemporaryDirectory(prefix='pait-cat-adapt-') as folder:
            directory = Path(folder);source = directory/'source.glb';output = directory/'output'
            source.write_bytes(raw)
            with (directory/'blender.log').open('wb') as log:
                result = subprocess.run([executable(), '--background', '--factory-startup', '--disable-autoexec',
                    '--python', str(Path(BASE_DIR)/'scripts/blender/adapt_cat.py'), '--', str(source), str(output),
                    '--mode', mode, '--forward='+forward], stdout=log, stderr=subprocess.STDOUT,
                    timeout=240, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), check=False)
            # Keep paths/private data out of API reports; preserve known diagnostic codes.
            with (directory/'blender.log').open('rb') as log:
                size = log.seek(0,2)
                log.seek(max(0,size-65536)); diagnostic = log.read().lower()
            if b'bone heat weighting: failed' in diagnostic:
                raise ValueError('自动热权重求解失败：请检查粘连、重叠表面及关节位置，修复后重新绑定')
            report_path = output/'report.json'
            if not report_path.is_file(): raise ValueError('Blender 未生成检查结果，请检查模型后重试')
            report = json.loads(report_path.read_text(encoding='utf-8'))
            status = report.get('status', 'failed')
            artifacts = {}
            if status == 'review_motion' and result.returncode == 0:
                for slot, name, limit in [('adapted','adapted.glb',40), ('blend','review.blend',100)]:
                    p = output/name
                    if not p.is_file() or p.stat().st_size > limit*1024*1024:
                        raise ValueError('适配结果过大或不完整，需要在 Blender 中精简')
                    artifacts[slot] = p.read_bytes()
            elif status == 'review_motion': raise ValueError('Blender 异常退出，请重试')
            _finish(app, task_id, job, digest, status, report, artifacts)
    except Exception as exc:
        message = '适配超过 4 分钟，请简化模型后重试' if isinstance(exc, subprocess.TimeoutExpired) else str(exc)[:300]
        _finish(app, task_id, job, digest, 'failed', {'error':message}, {})
    finally:
        LOCK.release()


def _finish(app, task_id, job, digest, status, report, artifacts):
    with app.app_context():
        db = get_db();db.execute('BEGIN IMMEDIATE')
        current = db.execute("SELECT a.id,s.data FROM pet_studio_adaptations a JOIN pet_studio_assets s ON s.task=a.task AND s.slot='model' JOIN pet_studio_tasks t ON t.id=a.task WHERE a.task=?", (task_id,)).fetchone()
        if not current or current['id'] != job or hashlib.sha256(current['data']).hexdigest() != digest:
            db.rollback();return
        with db:
            for slot, raw in artifacts.items():
                db.execute('INSERT OR REPLACE INTO pet_studio_assets VALUES (?,?,?,?)',
                           (task_id, slot, 'model/gltf-binary' if slot=='adapted' else 'application/octet-stream', raw))
            db.execute('UPDATE pet_studio_adaptations SET status=?,report=?,updated=? WHERE task=? AND id=?',
                       (status, json.dumps(report, ensure_ascii=False), time.time(), task_id, job))


def clear(task_id):
    # Called inside the caller's write transaction. Late workers cannot resurrect it.
    get_db().execute('DELETE FROM pet_studio_adaptations WHERE task=?', (task_id,))
    get_db().execute("DELETE FROM pet_studio_assets WHERE task=? AND slot IN ('adapted','blend')", (task_id,))
