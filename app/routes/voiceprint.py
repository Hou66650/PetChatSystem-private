import importlib.util
import re
from urllib.parse import urlsplit
from flask import Blueprint, jsonify, request
from ..db import get_db
from ..services import voiceprint_service as v, companion_service as c

bp = Blueprint('voiceprint', __name__)


@bp.before_request
def same_origin():
    origin = request.headers.get('Origin')
    if origin and urlsplit(origin).netloc != request.host:
        return jsonify(error='请在本站操作声纹'),403


@bp.after_request
def no_cache(response):
    response.headers['Cache-Control']='no-store'
    return response


@bp.route('/api/voiceprint', methods=['GET','PATCH'])
def status():
    owner=c.owner_key()
    if request.method=='PATCH':
        data=request.get_json(silent=True) or {}
        if not isinstance(data,dict) or type(data.get('enabled')) is not bool:
            return jsonify(error='无效的启用状态'),400
        v.set_enabled(owner,data['enabled'])
    return jsonify(enabled=v.enabled(owner),requestedEnabled=v.requested_enabled(owner),scope=c.browser_scope(),
                   ready=bool(importlib.util.find_spec('resemblyzer')),
                   profiles=[{'id':r['id'],'name':r['name']} for r in v.profiles(owner)])


def audio():
    if request.mimetype!='application/octet-stream' or not request.content_length or request.content_length>640000:
        raise ValueError('录音格式或长度不正确')
    return request.get_data()


@bp.route('/api/voiceprint/enroll',methods=['POST'])
def enroll():
    name=request.args.get('name','').strip()
    if not re.fullmatch(r'[\w\u4e00-\u9fff ·-]{1,24}',name):
        return jsonify(error='称呼限24个字，请勿输入特殊符号'),400
    try:
        v.enroll(c.owner_key(),name,audio())
    except ValueError as e:
        return jsonify(error=str(e)),400
    except (ImportError,RuntimeError,OSError):
        return jsonify(error='本地声纹模型暂不可用，请检查安装'),503
    return status()


@bp.route('/api/voiceprint/<profile_id>',methods=['DELETE'])
def delete(profile_id):
    db=get_db();db.execute('DELETE FROM voiceprint_profiles WHERE id=? AND owner=?',(profile_id,c.owner_key()));db.commit()
    return status()


@bp.route('/api/voiceprint/identify',methods=['POST'])
def identify():
    if request.headers.get('X-Profile-Scope')!=c.browser_scope():
        return jsonify(error='账户已变化，请重新开始通话'),409
    try:
        raw=audio()
        result=v.identify(c.owner_key(),raw)
        pet=int(request.args.get('petId',1))
        from ..services.realtime_service import build_instructions
        text=build_instructions(pet,request.args.get('gender') if request.args.get('gender') in ('male','female') else None, 'den' if request.args.get('surface')=='den' else 'chat',private_context=False)
    except (ValueError,LookupError):
        return jsonify(error='录音或宠物参数不正确'),400
    except (ImportError,RuntimeError,OSError):
        return jsonify(error='本地声纹模型暂不可用'),503
    return jsonify(**result,instructions=text+v.instruction(result))
