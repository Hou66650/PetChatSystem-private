"""Account-scoped public park endpoints."""
from urllib.parse import urlsplit
from flask import Blueprint, jsonify, render_template, request
from ..services import companion_service as companion, park_service as park

bp = Blueprint('park', __name__)

@bp.before_request
def guard():
    if request.method != 'POST':
        return
    if not companion.owner_key().startswith('user:'):
        return jsonify(error='请先登录再带伙伴入园。'), 401
    if (request.content_length or 0)>4096 or not request.is_json:
        return jsonify(error='请求格式或大小无效'), 400
    origin = request.headers.get('Origin')
    if (origin and urlsplit(origin).netloc != request.host) or request.headers.get('Sec-Fetch-Site')=='cross-site':
        return jsonify(error='请从本站操作'), 403
    if request.headers.get('X-Profile-Scope') != companion.browser_scope():
        return jsonify(error='账号已变化，请刷新页面。'), 409
    if not isinstance(request.get_json(silent=True), dict):
        return jsonify(error='请求格式无效'), 400

@bp.after_request
def headers(response):
    response.headers['Cache-Control'] = 'private, no-store'
    return response

@bp.errorhandler(park.ParkError)
def error(e):
    return jsonify(error=str(e)), e.status

@bp.get('/park')
def page():
    return render_template('park.html', park_logged_in=companion.owner_key().startswith('user:'))

@bp.get('/api/park')
def state():
    owner = companion.owner_key()
    if not owner.startswith('user:'):
        return jsonify(count=0, players=[], capacity=park.CAPACITY, scope=companion.browser_scope())
    return jsonify(**park.snapshot(owner), scope=companion.browser_scope())

@bp.post('/api/park/<operation>')
def operate(operation):
    owner, data = companion.owner_key(), request.get_json()
    if operation=='join':
        return jsonify(**park.join(owner, data))
    if operation in ('sync', 'leave'):
        return jsonify(**park.update(owner, data, operation=='leave'))
    return jsonify(error='操作不存在'), 404
