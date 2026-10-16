from urllib.parse import urlsplit
from flask import Blueprint,jsonify,request,render_template,current_app,Response
from ..services import cat_agent_service as agent, companion_service as companion

from ..services import cat_relationship_service as relationship
from ..services import cat_experience_service as experience
from ..services import cat_scene_service as scene

bp=Blueprint('cat_agent',__name__)

@bp.before_request
def validate():
    origin=request.headers.get('Origin')
    if (origin and urlsplit(origin).netloc!=request.host) or request.headers.get('Sec-Fetch-Site')=='cross-site':
        return jsonify(error='请在本站使用猫咪探索'),403
    if request.method=='POST':
        if request.headers.get('X-Profile-Scope')!=companion.browser_scope():return jsonify(error='账号已变化，请刷新页面'),409
        if not request.is_json:return jsonify(error='请发送JSON'),415
        if request.content_length and request.content_length>(16384 if request.path.endswith('/telemetry') else 4096):return jsonify(error='请求过大'),413

@bp.after_request
def no_cache(response):
    response.headers['Cache-Control']='no-store';return response

@bp.get('/api/cat-agent')
def status():
    owner=companion.owner_key()
    return jsonify(scope=companion.browser_scope(),catalog=agent.catalog(owner),memory=agent.memories(owner),world=scene.snapshot(owner))

@bp.get('/api/cat-agent/scene')
def scene_state():
    return jsonify(scope=companion.browser_scope(),world=scene.snapshot(companion.owner_key()))

@bp.post('/api/cat-agent/<operation>')
def operate(operation):
    data=request.get_json(silent=True)
    if not isinstance(data,dict):return jsonify(error='请求格式错误'),400
    owner=companion.owner_key()
    try:
        if operation=='relationship-event':return jsonify(**relationship.record(owner,data),scope=companion.browser_scope())
        if operation=='relationship-clear':return jsonify(**relationship.clear(owner),scope=companion.browser_scope())
        if operation=='telemetry':
            result=agent.monitor_record(owner,data)
            return jsonify(**result,control=experience.delivery(owner,data))
        if operation=='control':return jsonify(**experience.send_control(owner,data),scope=companion.browser_scope())
        if operation=='album-save':return jsonify(cards=experience.save_card(owner,data.get('id')),scope=companion.browser_scope())
        if operation=='album-delete':return jsonify(cards=experience.delete_card(owner,data.get('day')),scope=companion.browser_scope())
        if operation=='decide':return jsonify(**agent.decide(owner,data),scope=companion.browser_scope())
        if operation=='report':return jsonify(memory=agent.record(owner,data),scope=companion.browser_scope())
        return jsonify(error='操作不存在'),404
    except ValueError as e:return jsonify(error=str(e)),400


@bp.get('/cat-agent-monitor')
def monitor_page():
    from ..services.farm_service import LAYOUT
    return render_template('cat-agent-monitor.html',scope=companion.browser_scope(),farm_layout=LAYOUT)

@bp.get('/api/cat-agent/monitor')
def monitor_data():
    return jsonify(**agent.monitor_state(companion.owner_key()),scene=scene.monitor(companion.owner_key()),controls=experience.controls(companion.owner_key()),relationship=relationship.state(companion.owner_key()),scope=companion.browser_scope(),catalog=agent.catalog(companion.owner_key()),memory=agent.memories(companion.owner_key()))

@bp.get("/api/cat-agent/relationship")
def relationship_state():
    return jsonify(**relationship.state(companion.owner_key()),scope=companion.browser_scope())


@bp.post('/api/cat-agent/story-art')
def story_art_start():
    from ..services import story_art_service as art
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get('refresh', False), bool):
        return jsonify(error='请求格式错误'), 400
    owner = companion.owner_key()
    payload, code = art.start(owner, current_app.extensions['llm'], data.get('refresh', False), context=art.story_context(owner))
    return jsonify(**payload, scope=companion.browser_scope()), code

@bp.get('/api/cat-agent/story-art')
def story_art_status():
    from ..services import story_art_service as art
    return jsonify(**art.snapshot(companion.owner_key()), scope=companion.browser_scope())


@bp.get('/api/cat-agent/album')
def album_list():
    return jsonify(cards=experience.album(companion.owner_key()),scope=companion.browser_scope())

@bp.get('/api/cat-agent/album/<day>/image')
def album_image(day):
    raw=experience.image(companion.owner_key(),day)
    return Response(raw,mimetype='image/jpeg',headers={'X-Profile-Scope':companion.browser_scope()}) if raw else (jsonify(error='卡片不存在'),404)
