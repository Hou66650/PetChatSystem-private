"""Explicit paid submissions, durable job IDs, and query-only recovery.

The API key stays on the server. A timeout during submit is uncertain, never an
excuse to submit again. Reopening the workspace can only resume known job IDs.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import uuid
from urllib.parse import urlsplit

import requests
from flask import current_app
from ..config import BASE_DIR
from ..db import get_db
from . import pet_adaptation_service as adaptation
from . import pet_quality_service as quality

BASE = 'https://api.ai3d.cloud.tencent.com/v1/ai3d/'
ACTIVE = ('submitting', 'waiting', 'running', 'processing', 'uncertain')
_threads = set()
_guard = threading.Lock()


def init_schema():
    get_db().executescript('''CREATE TABLE IF NOT EXISTS pet_studio_generations(
        task TEXT PRIMARY KEY, id TEXT NOT NULL, job TEXT, status TEXT NOT NULL,
        source_hash TEXT NOT NULL, credits INTEGER, message TEXT NOT NULL DEFAULT '',
        created REAL NOT NULL, updated REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS pet_studio_equipped(owner TEXT PRIMARY KEY, task TEXT NOT NULL);
    ''')


def available():
    return bool(os.getenv('HUNYUAN_3D_API_KEY')) and Path(adaptation.executable()).is_file()


def state(task_id):
    r = get_db().execute('SELECT * FROM pet_studio_generations WHERE task=?', (task_id,)).fetchone()
    return {k:r[k] for k in ('id','status','credits','message','updated')} if r else None


def locked(task_id):
    r = state(task_id)
    return r and r['status'] in (*ACTIVE, 'paused')


def inputs(task_id):
    photos = {r['slot']:r['data'] for r in get_db().execute(
        "SELECT slot,data FROM pet_studio_assets WHERE task=? AND slot IN ('front','left','right','back') ORDER BY slot", (task_id,))}
    if 'front' not in photos:
        raise ValueError('请先上传正面全身照片')
    if sum(len(raw) for raw in photos.values()) > 6*1024*1024:
        raise ValueError('多视角照片总量超过 6 MB，请缩小照片后重试')
    digest = hashlib.sha256()
    for slot, raw in sorted(photos.items()):
        digest.update(slot.encode()); digest.update(raw)
    encode = lambda raw: base64.b64encode(raw).decode('ascii')
    payload = dict(Model='3.1', ImageBase64=encode(photos['front']), EnablePBR=True,
                   FaceCount=100000, GenerateType='Normal')
    extra = [dict(ViewType=k, ViewImageBase64=encode(v)) for k,v in photos.items() if k != 'front']
    if extra: payload['MultiViewImages'] = extra
    return payload, digest.hexdigest(), 50 if extra else 40


def start(task_id, consent):
    if consent is not True: raise ValueError('请先确认照片上传腾讯云及云端计费')
    if not available(): raise ValueError('服务器尚未配置混元 API Key 或 Blender')
    db = get_db(); db.execute('BEGIN IMMEDIATE')
    try:
        prior = state(task_id)
        if prior and prior['status'] != 'failed':
            raise ValueError('已有生成记录，请查询原任务；更换照片后才能再次生成')
        if db.execute("SELECT 1 FROM pet_studio_assets WHERE task=? AND slot='model'", (task_id,)).fetchone():
            raise ValueError('已有模型，请先核对外貌')
        task = db.execute('SELECT owner FROM pet_studio_tasks WHERE id=?', (task_id,)).fetchone()
        if not task: raise ValueError('档案已被删除')
        owner = task['owner']
        if db.execute("SELECT 1 FROM pet_studio_generations g JOIN pet_studio_tasks t ON t.id=g.task WHERE t.owner=? AND g.status IN ('submitting','waiting','running','processing','uncertain','paused')", (owner,)).fetchone():
            raise ValueError('这个账号已有未结束的生成任务，请先处理原任务')
        payload, digest, _ = inputs(task_id)
        quality.require(task_id, 'inputs')
        token = uuid.uuid4().hex; now = time.time()
        db.execute('INSERT OR REPLACE INTO pet_studio_generations VALUES (?,?,?,?,?,?,?,?,?)',
                   (task_id, token, None, 'submitting', digest, None, '正在提交，尚未取得任务编号', now, now))
        db.commit()
    except Exception:
        db.rollback(); raise
    launch(current_app._get_current_object(), task_id, token, payload)


def _call(action, payload):
    with requests.Session() as s:
        s.trust_env = False
        r = s.post(BASE+action, headers={'Authorization':os.environ['HUNYUAN_3D_API_KEY']},
                   json=payload, timeout=(15,120 if action=='submit' else 45), allow_redirects=False)
        value = r.json()
        if not isinstance(value, dict): raise ValueError('服务返回格式无效')
        return r.status_code, value.get('Response', value)


def _update(task_id, token, **fields):
    fields['updated'] = time.time()
    db = get_db()
    with db:
        db.execute('UPDATE pet_studio_generations SET '+','.join(k+'=?' for k in fields)+' WHERE task=? AND id=?',
                   (*fields.values(), task_id, token))


def launch(app, task_id, token, payload=None):
    key = (app.config['DATABASE_PATH'], task_id, token)
    with _guard:
        if key in _threads: return
        _threads.add(key)
    def run():
        try:
            with app.app_context(): _worker(task_id, token, payload)
        finally:
            with _guard: _threads.discard(key)
    try:
        threading.Thread(target=run, daemon=True).start()
    except Exception:
        with _guard: _threads.discard(key)
        # The durable submitting record prevents another paid click.
        _update(task_id,token,status='uncertain',message='后台任务未启动，请管理员核对后恢复。')


def resume(task_id, explicit=False):
    r = get_db().execute('SELECT * FROM pet_studio_generations WHERE task=?', (task_id,)).fetchone()
    if not r: return
    key = (current_app.config['DATABASE_PATH'],task_id,r['id'])
    with _guard:
        if key in _threads: return
    if r['status']=='submitting' and not r['job'] and time.time()-r['updated']>180:
        _update(task_id,r['id'],status='uncertain',message='提交结果未知，禁止重复扣费。请管理员在腾讯云核对任务。')
    elif r['job'] and (r['status'] in ACTIVE or (explicit and r['status']=='paused')):
        launch(current_app._get_current_object(),task_id,r['id'])


def _worker(task_id, token, payload=None):
    try:
        if payload is not None:
            try:
                code, value = _call('submit', payload)
            except Exception:
                _update(task_id,token,status='uncertain',message='提交结果未知，请管理员核对云端任务；不会自动重试或再次扣费。')
                return
            job = value.get('JobId')
            if job:
                _update(task_id,token,job=str(job),status='waiting',message='腾讯云已接收，正在排队')
            else:
                # Tencent can return structured business errors with HTTP 200.
                # 5xx, malformed responses and transport timeouts remain unknown.
                rejected = code < 500 and bool(value.get('Error') or value.get('Code'))
                _update(task_id,token,status='failed' if rejected else 'uncertain',
                        message='腾讯云拒绝请求，请检查额度、后付费与照片参数。' if rejected else '未取得任务编号，请管理员核对，禁止重复提交。')
                return
        deadline = time.monotonic()+1800
        while time.monotonic()<deadline:
            r = get_db().execute('SELECT * FROM pet_studio_generations WHERE task=? AND id=?',(task_id,token)).fetchone()
            if not r or not r['job']: return
            code, value = _call('query', {'JobId':r['job']})
            if code != 200: raise ValueError('query')
            status = value.get('Status')
            credits = value.get('ResultCreditConsumed')
            if not isinstance(credits,int): credits = None
            if status == 'FAIL':
                _update(task_id,token,status='failed',credits=credits,message='云端生成失败。请检查照片和腾讯云任务详情，再决定是否重试。'); return
            if status == 'DONE':
                _update(task_id,token,status='processing',credits=credits,message='生成完成，正在下载并用 Blender 整理网页模型')
                entry = next((f for f in value.get('ResultFile3Ds',[]) if f.get('Type')=='GLB'),None)
                if not entry: raise ValueError('missing GLB')
                raw = _download(entry['Url'])
                raw, diagnostics = _prepare(raw)
                _finish(task_id,token,r['source_hash'],raw,credits,diagnostics)
                return
            if status not in ('WAIT','RUN'): raise ValueError('unknown status')
            _update(task_id,token,status='waiting' if status=='WAIT' else 'running',message='云端排队中' if status=='WAIT' else '正在生成几何与 PBR 材质')
            time.sleep(15)
        raise ValueError('query timeout')
    except Exception:
        # URLs may contain signatures; exceptions are intentionally not persisted.
        _update(task_id,token,status='paused',message='查询、下载或整理暂未完成。可继续查询原任务，不会重新生成或扣费。')


def _download(url):
    parts = urlsplit(url)
    if parts.scheme!='https' or not (parts.hostname or '').endswith(('.myqcloud.com','.tencentcos.cn')) or parts.port not in (None,443) or parts.username:
        raise ValueError('Unexpected download host')
    with requests.Session() as s:
        s.trust_env = False
        with s.get(url,stream=True,timeout=(15,120),allow_redirects=False) as r:
            if r.status_code!=200: raise ValueError('download failed')
            chunks=[]; count=0
            for chunk in r.iter_content(1024*1024):
                count+=len(chunk)
                if count>80*1024*1024: raise ValueError('GLB too large')
                chunks.append(chunk)
    return b''.join(chunks)


def _prepare(raw):
    from ..routes.pet_studio import validate_glb
    validate_glb(raw)
    with adaptation.LOCK:
        with tempfile.TemporaryDirectory(prefix='pait-cloud-cat-') as folder:
            p=Path(folder); (p/'input.glb').write_bytes(raw)
            result=subprocess.run([adaptation.executable(),'--background','--factory-startup','--disable-autoexec',
                '--python',str(Path(BASE_DIR)/'scripts/blender/prepare_generated_pet.py'),'--',str(p/'input.glb'),str(p/'web.glb')],
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=240,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),check=False)
            if result.returncode or not (p/'web.glb').is_file(): raise ValueError('Blender export failed')
            if (p/'web.glb').stat().st_size>30*1024*1024: raise ValueError('Web model too large')
            output=(p/'web.glb').read_bytes(); validate_glb(output)
            diagnostics = json.loads((p/'web.quality.json').read_text(encoding='utf-8'))
            return output, diagnostics


def _finish(task_id, token, digest, raw, credits, diagnostics=None):
    db=get_db(); db.execute('BEGIN IMMEDIATE')
    r=db.execute('SELECT 1 FROM pet_studio_generations g JOIN pet_studio_tasks t ON t.id=g.task WHERE g.task=? AND g.id=?',(task_id,token)).fetchone()
    if not r:
        db.rollback(); return
    if inputs(task_id)[1]!=digest:
        db.rollback(); return
    with db:
        adaptation.clear(task_id)
        db.execute('INSERT OR REPLACE INTO pet_studio_assets VALUES (?,?,?,?)',(task_id,'model','model/gltf-binary',raw))
        if diagnostics:
            from .. import pet_quality
            pet_quality.record(db, task_id, 'geometry', pet_quality.fingerprints(db,task_id)['geometry'], 'unknown',
                               {'notes':diagnostics['reason'], 'files':[{'sha256':hashlib.sha256(raw).hexdigest()}],
                                'method':'automatic-diagnostics-only', 'diagnostics':diagnostics})
        db.execute("UPDATE pet_studio_tasks SET status='review',updated=? WHERE id=?",(time.time(),task_id))
        db.execute("UPDATE pet_studio_generations SET status='done',credits=?,message=?,updated=? WHERE task=? AND id=?",
                   (credits,'模型草稿已生成，身体结构审核通过后才能适配；请检查重复尾巴、多余肢体及粘连',time.time(),task_id,token))


def clear(task_id):
    get_db().execute('DELETE FROM pet_studio_generations WHERE task=?',(task_id,))
    get_db().execute('DELETE FROM pet_studio_equipped WHERE task=?',(task_id,))


def appearance(owner):
    r=get_db().execute("SELECT t.id,t.name,a.id AS version FROM pet_studio_equipped e JOIN pet_studio_tasks t ON t.id=e.task AND t.owner=e.owner JOIN pet_studio_adaptations a ON a.task=t.id AND a.status='reviewed' JOIN pet_studio_assets s ON s.task=t.id AND s.slot='adapted' WHERE e.owner=?",(owner,)).fetchone()
    if not r: return None
    if not quality.ready(r['id']): return None
    return dict(id='studio-'+r['id']+'-'+r['version'],name=r['name'],custom=True,
                model='/api/pet-studio/'+r['id']+'/assets/adapted',task=r['id'])
