from urllib.parse import urlsplit
from flask import Blueprint,request,jsonify,render_template,Response
from ..services import portal_service as portal,companion_service as companion

bp=Blueprint('portals',__name__)

@bp.before_request
def guard():
    if request.method!='POST':return
    if not request.is_json or (request.content_length or 0)>16384:return jsonify(error='请求格式或大小错误'),400
    origin=request.headers.get('Origin')
    if origin and urlsplit(origin).netloc!=request.host:return jsonify(error='请从本站发起操作'),403
    if request.headers.get('Sec-Fetch-Site')=='cross-site':return jsonify(error='禁止跨站操作'),403
    if '/desktop/' not in request.path and request.headers.get('X-Profile-Scope')!=companion.browser_scope():return jsonify(error='账号已变化，请刷新'),409

@bp.after_request
def uncached(response):response.headers['Cache-Control']='no-store';return response

@bp.errorhandler(portal.PortalError)
def error(e):return jsonify(error=str(e),code=e.code),e.status

@bp.get('/api/portals')
def state():return jsonify(**portal.state(companion.owner_key(),request.args.get("brief")=="1"),scope=companion.browser_scope())

@bp.post('/api/portals/<operation>')
def operate(operation):
    data=request.get_json(silent=True)
    if not isinstance(data,dict):raise portal.PortalError('请求格式错误')
    return jsonify(**portal.operate(companion.owner_key(),operation,data))

@bp.route('/api/portals/desktop/<operation>',methods=['GET','POST'])
def desktop(operation):
    data=request.get_json(silent=True) if request.method=='POST' else {}
    if not isinstance(data,dict):raise portal.PortalError('请求格式错误')
    if operation=='pair' and request.method=='POST':
        code=data.get('code')
        if not isinstance(code,str) or not 20<=len(code)<=80:raise portal.PortalError('配对码无效',403)
        return jsonify(**portal.pair(code))
    if operation not in ('state','model') and request.method!='POST':raise portal.PortalError('操作需要 POST',405)
    auth=request.headers.get('Authorization','')
    if not auth.startswith('Bearer ') or len(auth)>120:raise portal.PortalError('需要桌面配对凭证',401)
    if operation=='model':return Response(portal.travel_model(portal.desktop_trip(auth[7:]),'visitor'),mimetype='model/gltf-binary',headers={'X-Content-Type-Options':'nosniff'})
    return jsonify(**portal.desktop(auth[7:],operation,data))

@bp.get('/api/portals/trip/<trip>')
def trip(trip):
    portal.expire();owner=companion.owner_key();return jsonify(**portal.public_trip(portal.trip_for(owner,trip),owner))

@bp.get('/visit/<trip>')
def visit(trip):
    portal.trip_for(companion.owner_key(),trip)
    return render_template('portal-visit.html',trip=trip,scope=companion.browser_scope())

@bp.get('/journeys')
def journeys():return render_template('portal-journal.html',scope=companion.browser_scope())

@bp.get('/api/portals/trip/<trip>/model/<role>')
def trip_model(trip,role):
    portal.expire()
    t=portal.trip_for(companion.owner_key(),trip)
    return Response(portal.travel_model(t,role),mimetype='model/gltf-binary',headers={'X-Content-Type-Options':'nosniff'})
