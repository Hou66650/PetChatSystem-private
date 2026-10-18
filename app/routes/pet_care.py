"""Owner-scoped care and original animal recordings."""
from urllib.parse import urlsplit
from flask import Blueprint, jsonify, request, current_app
from ..db import get_db
from ..services import companion_service as memory, pet_care_service as care, pet_call_service as calls

bp = Blueprint('pet_care', __name__)


@bp.before_request
def guard():
    if request.method != 'GET':
        origin = request.headers.get('Origin')
        if origin and urlsplit(origin).netloc != request.host or request.headers.get('Sec-Fetch-Site') == 'cross-site': return jsonify(error='请在本站操作'),403
        if not memory.owner_key().startswith('user:'): return jsonify(error='请登录后设置自己的陪伴与叫声'),403
        if request.headers.get('X-Profile-Scope') != memory.browser_scope(): return jsonify(error='账号已变化，请刷新页面'),409


@bp.after_request
def private(response):
    response.headers['Cache-Control']='private, no-store'
    response.headers['X-Profile-Scope']=memory.browser_scope()
    response.headers['X-Content-Type-Options']='nosniff'
    return response


@bp.errorhandler(care.CareError)
@bp.errorhandler(calls.CallError)
def invalid(error): return jsonify(error=str(error)),400


def pet():
    try: number=int(request.args.get('petId',0))
    except (TypeError,ValueError): number=0
    if number not in (1,2,3,4): raise care.CareError('请选择一只宠物')
    return number


@bp.route('/api/pet-care',methods=['GET','PATCH'])
def settings():
    owner=memory.owner_key();number=pet()
    if request.method=='PATCH': care.save_settings(owner,number,request.get_json(silent=True))
    return jsonify(care.state(owner,number))


@bp.route('/api/pet-care/events',methods=['POST'])
@bp.route('/api/pet-care/events/<event_id>',methods=['PATCH','DELETE'])
def events(event_id=None):
    owner=memory.owner_key();number=pet()
    if request.method=='DELETE':
        db=get_db()
        with db: db.execute('DELETE FROM pet_care_events WHERE owner=? AND pet_id=? AND id=?',(owner,number,event_id))
    else: care.save_event(owner,number,request.get_json(silent=True),event_id)
    return jsonify(care.state(owner,number))


@bp.route('/api/pet-care/claim',methods=['POST'])
def claim():
    return jsonify(scope=memory.browser_scope(),petId=pet(),notice=care.claim(memory.owner_key(),pet()))


@bp.route('/api/pet-calls',methods=['GET','POST','PATCH'])
def clips():
    owner=memory.owner_key();number=pet()
    if request.method=='POST': calls.save(owner,number,request.get_json(silent=True))
    if request.method=='PATCH':
        data=request.get_json(silent=True)
        if not isinstance(data,dict) or type(data.get('enabled')) is not bool: raise calls.CallError('声音开关格式不正确')
        db=get_db()
        with db: db.execute('INSERT OR REPLACE INTO pet_call_settings VALUES (?,?,?)',(owner,number,int(data['enabled'])))
    return jsonify(scope=memory.browser_scope(),petId=number,**calls.state(owner,number))


@bp.route('/api/pet-calls/source',methods=['POST'])
def source():
    if not request.content_length or request.content_length > calls.MAX_UPLOAD+100000: return jsonify(error='文件不能超过 64MB'),413
    if request.form.get('consent')!='true': raise calls.CallError('请确认有权使用此视频或录音')
    audio=request.files.get('media')
    if not audio: raise calls.CallError('请选择音频或视频')
    result=calls.source(memory.owner_key(),pet(),audio.read(calls.MAX_UPLOAD+1))
    return jsonify(scope=memory.browser_scope(),petId=pet(),**result)


@bp.route('/api/pet-calls/source/<source_id>',methods=['GET','DELETE'])
def source_audio(source_id):
    row=calls.get_audio(memory.owner_key(),source_id,True)
    if request.method=='DELETE':
        db=get_db()
        with db: db.execute('DELETE FROM pet_call_sources WHERE id=? AND owner=?',(source_id,memory.owner_key()))
        return jsonify(ok=True)
    return current_app.response_class(row['audio'],mimetype='audio/wav')


@bp.get('/api/pet-calls/source/<source_id>/info')
def source_info(source_id):
    import io, wave
    row=calls.get_audio(memory.owner_key(),source_id,True)
    if row['pet_id'] != pet(): raise calls.CallError('素材不属于当前宠物')
    with wave.open(io.BytesIO(row['audio']),'rb') as wav: pcm=wav.readframes(wav.getnframes())
    return jsonify(scope=memory.browser_scope(),petId=row['pet_id'],id=row['id'],duration=row['duration'],candidates=calls.candidates(pcm),note='声音强弱仅帮助定位，请试听并确认是宠物原声，未确认不会自动使用。')


@bp.route('/api/pet-calls/<clip_id>',methods=['GET','DELETE'])
def audio(clip_id):
    row=calls.get_audio(memory.owner_key(),clip_id)
    if request.method=='DELETE':
        db=get_db()
        with db: db.execute('DELETE FROM pet_calls WHERE id=? AND owner=?',(clip_id,memory.owner_key()))
        return jsonify(ok=True)
    return current_app.response_class(row['audio'],mimetype='audio/wav')
