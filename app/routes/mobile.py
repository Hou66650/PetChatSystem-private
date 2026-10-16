"""JSON entry points for the native tablet client, sharing existing account memory."""
from collections import OrderedDict
from threading import Lock
import time

from flask import Blueprint, current_app, g, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from ..db import get_db, query_db
from ..llm import pets
from ..services import chat_service, companion_service

bp = Blueprint('mobile', __name__, url_prefix='/api/mobile/v1')
_DUMMY_HASH = generate_password_hash('not-a-real-account-password')


@bp.record_once
def install(state):
    state.app.extensions['mobile_login_gate'] = {'lock': Lock(), 'hits': OrderedDict()}
    state.app.extensions['mobile_chat_gate'] = {'lock': Lock(), 'active': set()}


def _login_limited():
    # Single-process development guard; public multi-worker hosting needs a shared limiter.
    gate = current_app.extensions['mobile_login_gate']
    now = time.monotonic()
    key = request.remote_addr or 'unknown'
    with gate['lock']:
        hits = gate['hits']
        recent = [t for t in hits.pop(key, []) if now - t < 60]
        limited = len(recent) >= 10
        if not limited:
            recent.append(now)
        hits[key] = recent
        while len(hits) > 2048:
            hits.popitem(last=False)
    return limited


@bp.before_request
def validate_request():
    if request.method in ('POST', 'DELETE'):
        origin = request.headers.get('Origin')
        if ((origin and origin.rstrip('/') != request.host_url.rstrip('/'))
                or request.headers.get('Sec-Fetch-Site') == 'cross-site'):
            return jsonify(error='请求来源不受支持'), 403
        if not request.is_json:
            return jsonify(error='请使用 JSON 请求'), 415
        if request.content_length is None or request.content_length > 16384:
            return jsonify(error='请求内容过大或长度未知'), 413
        if not isinstance(request.get_json(silent=True), dict):
            return jsonify(error='请求格式错误'), 400
    if request.endpoint in ('mobile.bootstrap', 'mobile.login'):
        return None
    if session.get('auth_kind') != 'user':
        return jsonify(error='请先登录'), 401
    user = query_db('SELECT user_id, user_name FROM users WHERE user_name=?',
                    (session.get('user_id'),), one=True)
    if user is None:
        session.clear()
        return jsonify(error='登录已失效，请重新登录'), 401
    g.mobile_user = user


@bp.after_request
def no_cache(response):
    response.headers['Cache-Control'] = 'no-store'
    return response


@bp.get('/bootstrap')
def bootstrap():
    return jsonify(apiVersion=1, appVersion=current_app.config['APP_VERSION'],
                   pets=[pets.public_info(p) for p in pets.list_pets()],
                   maxMessageChars=current_app.config['MAX_MESSAGE_CHARS'],
                   sessionCookieName=current_app.config['SESSION_COOKIE_NAME'])


@bp.post('/session')
def login():
    if _login_limited():
        return jsonify(error='登录尝试过多，请一分钟后重试'), 429, {'Retry-After': '60'}
    data = request.get_json()
    username, password = data.get('username'), data.get('password')
    if (not isinstance(username, str) or not 0 < len(username) <= 128
            or not isinstance(password, str) or not 0 < len(password) <= 1024):
        return jsonify(error='请输入有效的用户名和密码'), 400
    user = query_db('SELECT user_name, pwd FROM users WHERE user_name=?', (username,), one=True)
    valid = check_password_hash(user['pwd'] if user else _DUMMY_HASH, password)
    if not user or not valid:
        return jsonify(error='用户名或密码不正确'), 401
    session.clear()
    session['user_id'] = user['user_name']
    session['auth_kind'] = 'user'
    session.permanent = True
    return jsonify(username=user['user_name'])


@bp.get('/session')
def current_session():
    return jsonify(username=g.mobile_user['user_name'])


@bp.delete('/session')
@bp.post('/logout')
def logout():
    session.clear()
    return jsonify(ok=True)


@bp.get('/history')
def history():
    raw = request.args.get('petId', '')
    if not raw.isdecimal():
        return jsonify(error='请选择有效宠物'), 400
    try:
        pet = pets.get_pet(raw)
    except LookupError:
        return jsonify(error='宠物不存在'), 400
    return jsonify(messages=companion_service.history(companion_service.owner_key(), pet['id']))


@bp.post('/chat')
def chat():
    data = request.get_json()
    if type(data.get('petId')) is not int:
        return jsonify(error='请选择有效宠物'), 400
    request_id = data.get('requestId')
    if not isinstance(request_id, str) or not 8 <= len(request_id) <= 80:
        return jsonify(error='缺少有效请求编号'), 400
    message = data.get('message')
    if not isinstance(message, str) or len(message) > current_app.config['MAX_MESSAGE_CHARS']:
        return jsonify(error='消息长度不符合要求'), 400
    # Keep timed-out tablet retries from making a second concurrent model call.
    gate = current_app.extensions['mobile_chat_gate']
    key = (g.mobile_user['user_id'], data['petId'], request_id)
    with gate['lock']:
        if key in gate['active']:
            return jsonify(error='原消息仍在处理中，请稍后重试'), 409
        if len(gate['active']) >= 128:
            return jsonify(error='服务繁忙，请稍后重试'), 429
        gate['active'].add(key)
    try:
        # No body/3D executor exists in the first native milestone.
        payload, status = chat_service.handle_chat({
            'petId': data['petId'], 'message': message, 'requestId': request_id, 'surface': 'chat',
        })
        return jsonify(payload), status
    finally:
        with gate['lock']:
            gate['active'].discard(key)


@bp.route('/companion', methods=['GET', 'POST'])
def companion():
    raw = request.args.get('petId', '')
    if not raw.isdecimal():
        return jsonify(error='请选择有效宠物'), 400
    try:
        pet = pets.get_pet(raw)
    except LookupError:
        return jsonify(error='宠物不存在'), 400
    owner = companion_service.owner_key()
    if request.method == 'POST':
        enabled = request.get_json().get('enabled')
        if type(enabled) is not bool:
            return jsonify(error='enabled 必须是布尔值'), 400
        db = get_db()
        with db:
            db.execute('UPDATE companion_owners SET enabled=? WHERE owner=?', (int(enabled), owner))
            companion_service.invalidate_context(db, owner)
    profile = companion_service.profile(owner, pet['id'])
    detail = profile['pet']
    return jsonify(
        petId=pet['id'], name=detail['name'], species=detail['species'],
        role=pet['role'], companionStyle=detail['companionStyle'],
        interactionCount=detail['interactionCount'], enabled=profile['enabled'],
        memories=[{'id': item['id'], 'label': companion_service.CATEGORIES.get(item['category'], item['category']),
                   'value': item['value']} for item in profile['memories']])
