from urllib.parse import urlsplit
from flask import Blueprint, request, jsonify
from ..services import farm_service as farm, companion_service as companion
bp=Blueprint('farm',__name__)

@bp.after_request
def no_cache(response):response.headers['Cache-Control']='no-store';return response

@bp.errorhandler(farm.Error)
def error(e):return jsonify(error=str(e)),e.status

@bp.get('/api/farm')
def state():return jsonify(**farm.state(companion.owner_key()),scope=companion.browser_scope())

@bp.post('/api/farm/<op>')
def operate(op):
    origin=request.headers.get('Origin')
    if (origin and urlsplit(origin).netloc!=request.host) or request.headers.get('Sec-Fetch-Site')=='cross-site':raise farm.Error('请从本站操作',403)
    if request.headers.get('X-Profile-Scope')!=companion.browser_scope():raise farm.Error('账号已变化，请刷新',409)
    if not request.is_json or (request.content_length or 0)>2048:raise farm.Error('请求格式错误')
    data=request.get_json(silent=True)
    if not isinstance(data,dict):raise farm.Error('请求格式错误')
    return jsonify(**farm.operate(companion.owner_key(),op,data),scope=companion.browser_scope())
