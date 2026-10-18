"""Private reconstruction workspace. Uploads never imply cloud-generation consent."""
import io
import json
import struct
import time
import uuid
import warnings
import zipfile
from urllib.parse import urlsplit

from flask import Blueprint, jsonify, render_template, request, send_file
from PIL import Image, ImageOps

from ..db import get_db
from ..services import companion_service as identity
from ..services import pet_adaptation_service as adaptation
from ..services import pet_generation_service as generation
from ..services import pet_quality_service as quality
from ..services import studio_memory_service as memories

bp = Blueprint('pet_studio', __name__)
VIEWS = ('front', 'left', 'right', 'back', 'detail')


def init_schema():
    get_db().executescript('''
    CREATE TABLE IF NOT EXISTS pet_studio_tasks(
      id TEXT PRIMARY KEY, owner TEXT NOT NULL, name TEXT NOT NULL,
      mode TEXT NOT NULL, status TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '',
      created REAL NOT NULL, updated REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS pet_studio_assets(
      task TEXT NOT NULL, slot TEXT NOT NULL, mime TEXT NOT NULL, data BLOB NOT NULL,
      PRIMARY KEY(task,slot));
    ''')
    memories.init_schema()


@bp.before_request
def protect():
    if request.path == '/pet-studio':
        return
    if not identity.owner_key().startswith('user:'):
        return jsonify(error='请登录后保存自己的宠物档案'), 403
    if request.method != 'GET':
        origin = request.headers.get('Origin')
        if (origin and urlsplit(origin).netloc != request.host) or request.headers.get('Sec-Fetch-Site') == 'cross-site':
            return jsonify(error='请从本站操作'), 403
        if request.headers.get('X-Profile-Scope') != identity.browser_scope():
            return jsonify(error='账号已变化，请刷新页面'), 409
        if request.content_length is None:
            return jsonify(error='请求缺少文件长度'), 411
        if request.content_length > 32 * 1024 * 1024:
            return too_large(None)


@bp.after_request
def private(response):
    response.headers['Cache-Control'] = 'private, no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


@bp.errorhandler(413)
def too_large(_):
    return jsonify(error='文件过大：照片最多 8 MB，模型最多 30 MB'), 413


def task(task_id):
    return get_db().execute('SELECT * FROM pet_studio_tasks WHERE id=? AND owner=?',
                            (task_id, identity.owner_key())).fetchone()


def snapshot():
    db = get_db()
    rows = []
    for row in db.execute('SELECT * FROM pet_studio_tasks WHERE owner=? ORDER BY created DESC', (identity.owner_key(),)):
        item = dict(row)
        del item['owner']
        item['assets'] = [r['slot'] for r in db.execute('SELECT slot FROM pet_studio_assets WHERE task=?', (row['id'],))]
        item['adaptation'] = adaptation.state(row['id'])
        item['quality'] = quality.state(row['id'])
        generation.resume(row['id'])
        item['generation'] = generation.state(row['id'])
        item['equipped'] = all(q['status']=='pass' for q in item['quality'].values()) and bool(db.execute('SELECT 1 FROM pet_studio_equipped WHERE owner=? AND task=?', (identity.owner_key(),row['id'])).fetchone())
        rows.append(item)
    return jsonify(tasks=rows, scope=identity.browser_scope(), generationAvailable=generation.available())


@bp.get('/pet-studio')
def page():
    return render_template('pet-studio.html', scope=identity.browser_scope())


@bp.get('/api/pet-studio')
def listing():
    return snapshot()


@bp.post('/api/pet-studio')
def create():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error='请求格式错误'), 400
    name = data.get('name')
    mode = data.get('mode')
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 30 or mode not in ('companion', 'memory'):
        return jsonify(error='请填写 1–30 字的名字，并选择创建方式'), 400
    db = get_db()
    db.execute('BEGIN IMMEDIATE')
    if db.execute('SELECT COUNT(*) FROM pet_studio_tasks WHERE owner=?', (identity.owner_key(),)).fetchone()[0] >= 20:
        db.rollback()
        return jsonify(error='最多保存 20 个档案，请先删除不需要的档案'), 409
    now = time.time()
    with db:
        db.execute('INSERT INTO pet_studio_tasks VALUES (?,?,?,?,?,?,?,?)',
                   (uuid.uuid4().hex, identity.owner_key(), name.strip(), mode, 'draft', '', now, now))
    return snapshot()


def validate_glb(raw):
    """Reject external dependencies; preview cannot fetch arbitrary model URLs."""
    if len(raw) < 20 or raw[:4] != b'glTF':
        raise ValueError('请上传 Blender 导出的 GLB 模型')
    version, length = struct.unpack_from('<II', raw, 4)
    if version != 2 or length != len(raw):
        raise ValueError('GLB 文件不完整')
    size, kind = struct.unpack_from('<II', raw, 12)
    if kind != 0x4E4F534A or size > len(raw)-20:
        raise ValueError('模型结构无效')
    doc = json.loads(raw[20:20+size])
    if doc.get('asset', {}).get('version') != '2.0':
        raise ValueError('仅支持 glTF 2.0')
    def check(value):
        if isinstance(value, dict):
            if 'uri' in value:
                raise ValueError('请在 Blender 中将贴图嵌入 GLB 后重新导出')
            for v in value.values(): check(v)
        elif isinstance(value, list):
            for v in value: check(v)
    check(doc)
    if not doc.get('meshes') or len(doc.get('nodes', [])) > 2000:
        raise ValueError('模型为空或过于复杂')


@bp.post('/api/pet-studio/<task_id>/assets/<slot>')
def upload(task_id, slot):
    row = task(task_id)
    if row is None: return jsonify(error='档案不存在'), 404
    if slot not in (*VIEWS, 'model'): return jsonify(error='未知视角'), 400
    file = request.files.get('file')
    if file is None: return jsonify(error='请选择文件'), 400
    limit = (30 if slot == 'model' else 8) * 1024 * 1024
    raw = file.stream.read(limit+1)
    if len(raw) > limit: return too_large(None)
    try:
        if slot == 'model':
            validate_glb(raw)
            mime = 'model/gltf-binary'
        else:
            with warnings.catch_warnings():
                warnings.simplefilter('error', Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(raw)) as source:
                    if source.width * source.height > 24000000 or min(source.size) < 128:
                        raise ValueError('照片需至少 128 像素，且不超过 2400 万像素')
                    im = ImageOps.exif_transpose(source).convert('RGB')
                    im.thumbnail((1600, 1600))
                    output = io.BytesIO()
                    im.save(output, format='JPEG', quality=92)
                    raw = output.getvalue()
            mime = 'image/jpeg'
    except Exception as exc:
        message = str(exc) if isinstance(exc, ValueError) else '无法读取文件，请使用有效的 JPG、PNG 或 GLB'
        return jsonify(error=message[:160]), 400
    db = get_db()
    db.execute('BEGIN IMMEDIATE')
    if task(task_id) is None:
        db.rollback()
        return jsonify(error='档案已被删除'), 404
    if generation.locked(task_id):
        db.rollback()
        return jsonify(error='请先完成或核对现有云端任务，再更换素材'), 409
    with db:
        generation.clear(task_id)
        adaptation.clear(task_id)
        db.execute('INSERT OR REPLACE INTO pet_studio_assets VALUES (?,?,?,?)', (task_id, slot, mime, raw))
        db.execute('UPDATE pet_studio_tasks SET status=?,updated=? WHERE id=?',
                   ('review' if slot == 'model' else 'draft', time.time(), task_id))
        if slot != 'model':
            db.execute("DELETE FROM pet_studio_assets WHERE task=? AND slot='model'", (task_id,))
    return snapshot()


@bp.get('/api/pet-studio/<task_id>/assets/<slot>')
def asset(task_id, slot):
    if task(task_id) is None: return jsonify(error='档案不存在'), 404
    row = get_db().execute('SELECT * FROM pet_studio_assets WHERE task=? AND slot=?', (task_id,slot)).fetchone()
    if row is None: return jsonify(error='文件不存在'), 404
    suffix = '.blend' if slot=='blend' else '.glb' if slot in ('model','adapted') else '.jpg'
    return send_file(io.BytesIO(row['data']), mimetype=row['mime'], download_name=slot+suffix, as_attachment=slot=='blend')


@bp.get('/api/pet-studio/<task_id>/references')
def references(task_id):
    row = task(task_id)
    if row is None: return jsonify(error='档案不存在'), 404
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('reference.json', json.dumps({'name':row['name'], 'mode':row['mode'],
            'notes':row['notes'], 'species':'cat', 'visibility':'private'}, ensure_ascii=False, indent=2))
        for image in get_db().execute("SELECT slot,data FROM pet_studio_assets WHERE task=? AND slot IN ('front','left','right','back','detail')", (task_id,)):
            archive.writestr(image['slot']+'.jpg', image['data'])
    output.seek(0)
    return send_file(output, mimetype='application/zip', as_attachment=True, download_name='pet-references.zip')


@bp.post('/api/pet-studio/<task_id>/<operation>')
def operate(task_id, operation):
    row = task(task_id)
    if row is None: return jsonify(error='档案不存在'), 404
    db = get_db()
    data = request.get_json(silent=True)
    if not isinstance(data, dict): return jsonify(error='请求格式错误'), 400
    status = row['status']
    if operation == 'delete':
        with db:
            memories.clear(task_id)
            generation.clear(task_id)
            adaptation.clear(task_id)
            db.execute('DELETE FROM pet_studio_assets WHERE task=?', (task_id,))
            db.execute('DELETE FROM pet_studio_quality WHERE task=?', (task_id,))
            db.execute('DELETE FROM pet_studio_tasks WHERE id=?', (task_id,))
        return snapshot()
    if operation == 'generate':
        try: generation.start(task_id, data.get('consent'))
        except ValueError as exc: return jsonify(error=str(exc)), 409
        return snapshot()
    if operation == 'resume-generation':
        generation.resume(task_id, explicit=True)
        return snapshot()
    if operation in ('equip','unequip'):
        db.execute('BEGIN IMMEDIATE')
        if db.execute("SELECT 1 FROM portal_trips t LEFT JOIN portal_islands i ON i.id=t.destination WHERE t.status IN ('active','pairing') AND ((t.owner=? AND t.pet='3') OR (i.owner=? AND i.pet='3'))", (identity.owner_key(),identity.owner_key())).fetchone():
            db.rollback()
            return jsonify(error='请先结束猫咪的旅行或接待，再切换伙伴'), 409
        a = adaptation.state(task_id)
        if operation == 'equip':
            try: quality.require(task_id, 'motion')
            except ValueError as exc:
                db.rollback()
                return jsonify(error=str(exc)), 409
            if not a or a['status'] != 'reviewed' or data.get('jobId') != a['id'] or not db.execute("SELECT 1 FROM pet_studio_assets WHERE task=? AND slot='adapted'",(task_id,)).fetchone():
                db.rollback()
                return jsonify(error='请先完成当前版本的全部动作验收'), 409
            db.execute('INSERT OR REPLACE INTO pet_studio_equipped VALUES (?,?)',(identity.owner_key(),task_id))
            # Equipping never grants visitor access implicitly; the owner opts in.
            db.execute("UPDATE portal_islands SET allow_visitors=0 WHERE owner=? AND pet='3'",(identity.owner_key(),))
        else:
            db.execute('DELETE FROM pet_studio_equipped WHERE owner=? AND task=?',(identity.owner_key(),task_id))
        db.commit()
        return snapshot()
    if operation == 'adapt':
        if status != 'approved': return jsonify(error='请先核对并确认外貌'), 409
        try: adaptation.start(task_id, data.get('mode','auto'), data.get('forward','-Y'))
        except ValueError as exc: return jsonify(error=str(exc)), 409
        return snapshot()
    if operation == 'review-motion':
        db.execute('BEGIN IMMEDIATE')
        result = adaptation.state(task_id)
        if not result or result['status'] != 'review_motion' or data.get('jobId') != result['id']:
            db.rollback()
            return jsonify(error='动作版本已变化，请刷新后重新检查'), 409
        checks = data.get('checks')
        if not isinstance(checks, list) or any(not isinstance(c,str) for c in checks) or set(checks) != set(adaptation.CHECKS):
            db.rollback()
            return jsonify(error='请逐项检查外貌、动作、头部及脚掌'), 400
        with db:
            try: quality.require(task_id, 'motion')
            except ValueError as exc:
                db.rollback()
                return jsonify(error=str(exc)), 409
            db.execute("UPDATE pet_studio_adaptations SET status='reviewed',updated=? WHERE task=?", (time.time(),task_id))
        return snapshot()
    if operation == 'prepare':
        if not db.execute("SELECT 1 FROM pet_studio_assets WHERE task=? AND slot='front'", (task_id,)).fetchone():
            return jsonify(error='请先上传一张清晰的正面照片'), 400
        if status in ('review','approved'): return jsonify(error='已有模型，请先完成外貌核对'), 409
        status = 'awaiting_generation'
    elif operation == 'approve':
        if status != 'review': return jsonify(error='请先导入模型并核对外貌'), 409
        try: quality.require(task_id, 'geometry')
        except ValueError as exc: return jsonify(error=str(exc)), 409
        status = 'approved'
    elif operation != 'notes': return jsonify(error='操作不存在'), 404
    notes = data.get('notes', row['notes'])
    if not isinstance(notes, str) or len(notes) > 1000: return jsonify(error='修正说明最多 1000 字'), 400
    with db:
        db.execute('UPDATE pet_studio_tasks SET status=?,notes=?,updated=? WHERE id=?', (status, notes, time.time(), task_id))
    return snapshot()
