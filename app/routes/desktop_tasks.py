from urllib.parse import urlsplit
from flask import Blueprint,request,jsonify
from ..services import desktop_task_service as tasks,portal_service as portal,companion_service as companion

bp=Blueprint('desktop_tasks',__name__)

@bp.after_request
def uncached(response):
    response.headers['Cache-Control']='private, no-store';return response

@bp.errorhandler(portal.PortalError)
def error(exc):return jsonify(error=str(exc),code=exc.code),exc.status

@bp.get('/api/desktop/v1/tasks')
def read_tasks():
    # Cookies grant read access only, never tool authority.
    return jsonify(tasks.snapshot(companion.owner_key()))

@bp.post('/api/desktop/v1/<operation>')
def operate(operation):
    if not request.is_json or (request.content_length or 0)>16384:raise portal.PortalError('请求格式或大小错误')
    origin=request.headers.get('Origin')
    if (origin and urlsplit(origin).netloc!=request.host) or request.headers.get('Sec-Fetch-Site')=='cross-site':raise portal.PortalError('禁止跨站操作',403)
    data=request.get_json(silent=True)
    if not isinstance(data,dict):raise portal.PortalError('参数格式错误')
    auth=request.headers.get('Authorization','')
    if not auth.startswith('Bearer ') or len(auth)>120:raise portal.PortalError('需要桌面行程凭证',401)
    token=auth[7:]
    # Receipt secrets authorize ONLY this already-claimed attempt after recall.
    if operation=='ack':return jsonify(tasks.acknowledge(token,data))
    t=portal.desktop_trip(token)
    if operation=='state':return jsonify(tasks.snapshot(t['owner'],t['id']))
    if operation=='claim':return jsonify(tasks.claim(t,token))
    return jsonify(tasks.mutate(t,operation,data))
