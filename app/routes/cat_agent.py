from urllib.parse import urlsplit
from flask import Blueprint,jsonify,request
from ..services import cat_agent_service as agent, companion_service as companion

bp=Blueprint('cat_agent',__name__)

@bp.before_request
def validate():
    origin=request.headers.get('Origin')
    if (origin and urlsplit(origin).netloc!=request.host) or request.headers.get('Sec-Fetch-Site')=='cross-site':
        return jsonify(error='请在本站使用猫咪探索'),403
    if request.method=='POST':
        if request.headers.get('X-Profile-Scope')!=companion.browser_scope():return jsonify(error='账号已变化，请刷新页面'),409
        if not request.is_json:return jsonify(error='请发送JSON'),415
        if request.content_length and request.content_length>4096:return jsonify(error='请求过大'),413

@bp.after_request
def no_cache(response):
    response.headers['Cache-Control']='no-store';return response

@bp.get('/api/cat-agent')
def status():
    return jsonify(scope=companion.browser_scope(),catalog=agent.CATALOG,memory=agent.memories(companion.owner_key()))

@bp.post('/api/cat-agent/<operation>')
def operate(operation):
    data=request.get_json(silent=True)
    if not isinstance(data,dict):return jsonify(error='请求格式错误'),400
    owner=companion.owner_key()
    try:
        if operation=='decide':return jsonify(**agent.decide(owner,data),scope=companion.browser_scope())
        if operation=='report':return jsonify(memory=agent.record(owner,data),scope=companion.browser_scope())
        return jsonify(error='操作不存在'),404
    except ValueError as e:return jsonify(error=str(e)),400
