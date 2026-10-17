"""Personal companion records: session-owned APIs and an editable profile page."""
import uuid
from urllib.parse import urlsplit

from flask import Blueprint, jsonify, render_template, request

from ..db import get_db
from ..llm import pets
from ..services import companion_service as memory
from ..services import diary_service as diary

bp = Blueprint('companion', __name__)


@bp.before_request
def same_origin():
    if request.method in ('POST','PATCH','DELETE'):
        origin = request.headers.get('Origin')
        if (origin and urlsplit(origin).netloc != request.host) or request.headers.get('Sec-Fetch-Site') == 'cross-site':
            return jsonify(error='请在本站操作自己的陪伴档案'), 403
        if not request.is_json:
            return jsonify(error='请使用 JSON 请求'), 415


def pet_id():
    try:
        return pets.get_pet(request.args.get('petId',1))['id']
    except LookupError:
        return None


@bp.route('/companion')
def page():
    return render_template('companion.html', pets=[pets.public_info(p) for p in pets.list_pets()])


@bp.route('/api/companion', methods=['GET','PATCH','DELETE'])
def archive():
    owner = memory.owner_key()
    p = pet_id()
    if p is None: return jsonify(error='宠物不存在'), 400
    db = get_db()
    if request.method == 'PATCH':
        data = request.get_json(silent=True)
        if not isinstance(data,dict) or type(data.get('enabled')) is not bool:
            return jsonify(error='enabled 必须是布尔值'),400
        with db:
            db.execute('UPDATE companion_owners SET enabled=? WHERE owner=?', (int(data['enabled']),owner))
            memory.invalidate_context(db,owner)
    elif request.method == 'DELETE':
        with db:
            diary.forget(db,owner)
            from ..services import growth_service
            growth_service.forget(db,owner)
            db.execute('DELETE FROM pet_care_events WHERE owner=?',(owner,))
            db.execute('DELETE FROM companion_memories WHERE owner=?',(owner,))
            db.execute('DELETE FROM companion_messages WHERE owner=?',(owner,))
            db.execute('DELETE FROM cat_scene_observations WHERE owner=?',(owner,))
            db.execute('DELETE FROM cat_scene_decisions WHERE owner=?',(owner,))
            memory.invalidate_context(db,owner)
    return jsonify(memory.profile(owner,p)),200,{'Cache-Control':'no-store'}


@bp.route('/api/companion/history', methods=['GET','DELETE'])
def conversation():
    owner = memory.owner_key()
    p = pet_id() if 'petId' in request.args else None
    if 'petId' in request.args and p is None: return jsonify(error='宠物不存在'),400
    if request.method == 'DELETE':
        db=get_db()
        with db:
            if p is None: db.execute('DELETE FROM pet_care_events WHERE owner=? AND source_id IS NOT NULL',(owner,))
            else: db.execute('DELETE FROM pet_care_events WHERE owner=? AND pet_id=? AND source_id IS NOT NULL',(owner,p))
            if p is None: db.execute('DELETE FROM companion_messages WHERE owner=?',(owner,))
            else: db.execute('DELETE FROM companion_messages WHERE owner=? AND pet_id=?',(owner,p))
            diary.remove_chats(db,owner,p)
            memory.invalidate_context(db,owner)
    return jsonify(messages=memory.history(owner,p)),200,{'Cache-Control':'no-store'}


@bp.route('/api/companion/history/<int:message_id>', methods=['DELETE'])
def delete_message(message_id):
    owner=memory.owner_key();db=get_db()
    with db:
        row=db.execute('SELECT id,pet_id,request_id FROM companion_messages WHERE owner=? AND id=?',(owner,message_id)).fetchone()
        if not row:return jsonify(error='记录不存在'),404
        turn=db.execute("SELECT id FROM companion_messages WHERE owner=? AND pet_id=? AND request_id=? AND role='user'",(owner,row['pet_id'],row['request_id'])).fetchone()
        db.execute('DELETE FROM pet_care_events WHERE owner=? AND source_id=?',(owner,message_id))
        db.execute('DELETE FROM companion_messages WHERE owner=? AND id=?',(owner,message_id))
        if turn: diary.remove_chats(db,owner,message_id=turn['id'])
        memory.invalidate_context(db,owner)
    return jsonify(success=True)


@bp.get('/api/diary')
def daily_diary():
    from datetime import date
    before=request.args.get('before')
    if before:
        try: before=date.fromisoformat(before).isoformat()
        except ValueError: return jsonify(error='日期格式不正确'),400
    return jsonify(diary.pages(memory.owner_key(),before)),200,{'Cache-Control':'private, no-store'}


@bp.post('/api/diary/events')
def diary_interaction():
    import time
    owner=memory.owner_key()
    if request.headers.get('X-Profile-Scope')!=memory.browser_scope():
        return jsonify(error='账号已变化，请刷新页面'),409
    data=request.get_json(silent=True)
    if not isinstance(data,dict) or type(data.get('petId')) is not int or data['petId'] not in diary.NAMES:
        return jsonify(error='请选择有效宠物'),400
    kind=data.get('kind')
    if not isinstance(kind,str) or kind not in (*diary.INTERACTIONS,'visit'):
        return jsonify(error='互动类型不正确'),400
    pet=data['petId'];now=time.time()
    source=f'visit:{pet}:{diary.day(now)}' if kind=='visit' else f'interaction:{pet}:{kind}:{int(now//60)}'
    db=get_db()
    with db: diary.record(db,owner,pet,source,'visit' if kind=='visit' else 'interaction',kind,now)
    return jsonify(ok=True),200,{'Cache-Control':'no-store'}


@bp.delete('/api/diary/<int:pet>/<date>')
def delete_daily_diary(pet,date):
    owner=memory.owner_key();db=get_db()
    with db:
        changed=db.execute('UPDATE pet_diary_days SET deleted=1,body=\'\',title=\'\' WHERE owner=? AND pet_id=? AND day=? AND deleted=0',(owner,pet,date)).rowcount
        if not changed:return jsonify(error='日记不存在'),404
        db.execute('DELETE FROM pet_diary_facts WHERE owner=? AND pet_id=? AND day=?',(owner,pet,date))
    return jsonify(ok=True),200,{'Cache-Control':'no-store'}


@bp.route('/api/companion/memories', methods=['POST'])
@bp.route('/api/companion/memories/<int:fact_id>', methods=['PATCH','DELETE'])
def edit_memory(fact_id=None):
    owner = memory.owner_key(); db=get_db()
    p=pet_id()
    if p is None: return jsonify(error='宠物不存在'),400
    if fact_id is not None:
        row=db.execute('SELECT * FROM companion_memories WHERE owner=? AND id=?',(owner,fact_id)).fetchone()
        if not row: return jsonify(error='记忆不存在'),404
    if request.method == 'DELETE':
        with db:
            db.execute('DELETE FROM companion_memories WHERE owner=? AND id=?',(owner,fact_id))
            memory.invalidate_context(db,owner)
    else:
        data=request.get_json(silent=True)
        if not isinstance(data,dict): return jsonify(error='请求格式错误'),400
        value=data.get('value'); cat=data.get('category') if fact_id is None else row['category']
        if not isinstance(cat,str) or cat not in memory.CATEGORIES or not isinstance(value,str) or not 0<len(value.strip())<=80:
            return jsonify(error='请填写有效分类和 1–80 字的内容'),400
        value=value.strip()
        scope=p if cat in ('pet_name','memory') else 0
        if fact_id is not None: scope=row['pet_id']
        with db:
            if cat in ('likes','dislikes'):
                opposite='dislikes' if cat=='likes' else 'likes'
                db.execute('DELETE FROM companion_memories WHERE owner=? AND pet_id=? AND category=? AND value=?',(owner,scope,opposite,value))
            if fact_id is not None:
                db.execute('DELETE FROM companion_memories WHERE owner=? AND pet_id=? AND category=? AND value=? AND id<>?',(owner,scope,cat,value,fact_id))
                db.execute("UPDATE companion_memories SET value=?,source_quote='用户在档案中编辑确认',confirmed=1,updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE owner=? AND id=?",(value,owner,fact_id))
            else:
                if db.execute('SELECT COUNT(*) FROM companion_memories WHERE owner=?',(owner,)).fetchone()[0]>=80:
                    return jsonify(error='最多保存80条，请先整理已有记忆'),400
                if cat in memory.SINGLE: db.execute('DELETE FROM companion_memories WHERE owner=? AND pet_id=? AND category=?',(owner,scope,cat))
                db.execute("INSERT INTO companion_memories(owner,pet_id,category,value,source_quote,confirmed) VALUES (?,?,?,?,'用户主动添加',1) ON CONFLICT(owner,pet_id,category,value) DO UPDATE SET confirmed=1",(owner,scope,cat,value))
            memory.invalidate_context(db,owner)
    return jsonify(memory.profile(owner,p)),200,{'Cache-Control':'no-store'}


@bp.route('/api/companion/voice-round', methods=['POST'])
def voice_round():
    # Realtime transport already generated/spoke the answer; only archive and extract the user turn.
    from ..services.chat_service import handle_chat
    data=request.get_json(silent=True)
    if not isinstance(data,dict) or not isinstance(data.get('assistantText'),str):
        return jsonify(error='缺少完整语音回合'),400
    data['surface']='den' if data.get('surface')=='den' else 'chat'
    payload,status=handle_chat(data, observed_reply=data['assistantText'][:2000])
    if status == 200:
        from ..services.realtime_service import build_instructions
        gender=data.get('petGender') if data.get('petGender') in ('male','female') else None
        payload['instructions']=build_instructions(payload['pet']['id'],gender,data['surface'])
    return jsonify(payload),status,{'Cache-Control':'no-store'}
