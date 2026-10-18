"""Windows bearer API. Reuses authoritative services, never browser cookies."""
import hashlib
import secrets
import time

from flask import Blueprint, current_app, g, jsonify, request
from flask.sessions import SessionInterface, SecureCookieSession
from werkzeug.security import check_password_hash, generate_password_hash

from ..db import get_db
from ..services import companion_service as companion
from ..services import cat_market_service as market, supply_service as supplies
from ..services import farm_service as farm, pet_voice_service as voices
from ..services import park_service as park, growth_service, wardrobe_service

bp = Blueprint('native', __name__, url_prefix='/api/native/v1')
_DUMMY = generate_password_hash('native-login-timing-only')


@bp.record_once
def install(state):
    original = state.app.session_interface
    class NativeSessionInterface(SessionInterface):
        def open_session(self, app, req):
            if req.path.startswith('/api/native/v1/'):
                return SecureCookieSession()
            return original.open_session(app, req)

        def save_session(self, app, session, response):
            if not request.path.startswith('/api/native/v1/'):
                original.save_session(app, session, response)
    state.app.session_interface = NativeSessionInterface()
    with state.app.app_context():
        growth_service.init_schema()
        wardrobe_service.init_schema()
        park.init_schema()
        get_db().execute('''CREATE TABLE IF NOT EXISTS native_sessions(
            digest TEXT PRIMARY KEY, user_id INTEGER NOT NULL,
            created REAL NOT NULL, expires REAL NOT NULL)''')
        get_db().commit()


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


@bp.before_request
def guard():
    origin = request.headers.get('Origin')
    if ((origin and origin.rstrip('/') != request.host_url.rstrip('/'))
            or request.headers.get('Sec-Fetch-Site') == 'cross-site'):
        return jsonify(error='请求来源不受支持'), 403
    if request.method not in ('GET', 'HEAD') and request.endpoint != 'native.voice_upload':
        if not request.is_json:
            return jsonify(error='请使用 JSON 请求'), 415
        if not request.content_length or request.content_length > 16384:
            return jsonify(error='请求内容过大或长度未知'), 413
        if not isinstance(request.get_json(silent=True), dict):
            return jsonify(error='请求格式错误'), 400
        if any(k in request.get_json() for k in ('owner', 'account_id', 'user_id', 'balance')):
            return jsonify(error='账号身份由登录会话决定'), 400
    if request.endpoint in ('native.bootstrap', 'native.login', 'native.register'):
        return None
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer ') or not 32 <= len(auth[7:]) <= 128:
        return jsonify(error='请登录派特岛账号'), 401
    row = get_db().execute('''SELECT s.digest,s.expires,u.user_id,u.user_name
        FROM native_sessions s JOIN users u ON u.user_id=s.user_id
        WHERE s.digest=? AND s.expires>?''', (digest(auth[7:]), time.time())).fetchone()
    if row is None:
        return jsonify(error='登录已过期，请重新登录'), 401
    g.native_user = row
    g.companion_owner = 'user:' + str(row['user_id'])
    db = get_db()
    db.execute('INSERT OR IGNORE INTO companion_owners(owner) VALUES (?)', (g.companion_owner,))
    db.commit()


@bp.after_request
def private(response):
    response.headers['Cache-Control'] = 'private, no-store'
    return response


@bp.errorhandler(market.MarketError)
@bp.errorhandler(voices.VoiceError)
@bp.errorhandler(park.ParkError)
def service_error(error):
    return jsonify(error=str(error)), error.status


@bp.get('/park')
def park_snapshot():
    from ..services.park_navigation import LAYOUT
    return jsonify(**park.snapshot(g.companion_owner), navigation=LAYOUT)


@bp.post('/park/<operation>')
def park_operation(operation):
    data = request.get_json()
    if operation == 'join':
        from ..services.park_navigation import LAYOUT
        return jsonify(**park.join(g.companion_owner, data), navigation=LAYOUT)
    if operation in ('sync', 'leave'):
        return jsonify(**park.update(g.companion_owner, data, operation == 'leave'))
    if operation == 'route':
        from ..services.native_park_navigation import route
        row = get_db().execute('SELECT * FROM park_presence WHERE owner=?', (g.companion_owner,)).fetchone()
        token = data.get('token')
        if (not row or not isinstance(token, str) or len(token) != 48
                or any(c not in '0123456789abcdef' for c in token)
                or not secrets.compare_digest(token, row['token']) or row['updated'] <= park.clock()-park.TTL):
            raise park.ParkError('请重新带伙伴入园', 409)
        x, z, _ = park.point(dict(x=data.get('x'), z=data.get('z'), yaw=0))
        return jsonify(path=route((row['x'], row['z']), (x, z)))
    return jsonify(error='操作不存在'), 404


@bp.get('/bootstrap')
def bootstrap():
    return jsonify(apiVersion=1, fixture=bool(current_app.config.get('NATIVE_FIXTURE', False)), providerFixture=bool(current_app.config.get('NATIVE_PROVIDER_FIXTURE', False)), capabilities=['account', 'inventory', 'farm-beds', 'chat', 'voice-profiles', 'realtime', 'account-cat-bowls', 'public-park'],
                   pending=['native-map-placement', 'portal-lease', 'runtime-private-model'])


@bp.post('/session')
def login():
    from .mobile import _login_limited
    if _login_limited():
        return jsonify(error='登录尝试过多，请稍后重试'), 429, {'Retry-After': '60'}
    data = request.get_json()
    name, password = data.get('username'), data.get('password')
    if not isinstance(name, str) or not 1 <= len(name) <= 128 or not isinstance(password, str) or not 1 <= len(password) <= 1024:
        return jsonify(error='请输入有效的账号和密码'), 400
    row = get_db().execute('SELECT user_id,user_name,pwd FROM users WHERE user_name=?', (name,)).fetchone()
    valid = check_password_hash(row['pwd'] if row else _DUMMY, password)
    if not row or not valid:
        return jsonify(error='用户名或密码不正确'), 401
    token, now = secrets.token_urlsafe(48), time.time()
    db = get_db()
    with db:
        db.execute('DELETE FROM native_sessions WHERE expires<=?', (now,))
        db.execute('INSERT INTO native_sessions VALUES (?,?,?,?)', (digest(token), row['user_id'], now, now + 43200))
    return jsonify(token=token, expiresAt=now + 43200, username=row['user_name'], accountId=row['user_id'])


@bp.delete('/session')
def logout():
    db = get_db()
    with db:
        db.execute('DELETE FROM native_sessions WHERE digest=?', (g.native_user['digest'],))
    return jsonify(ok=True)


@bp.post('/registration')
def register():
    from .mobile import _login_limited
    if _login_limited():
        return jsonify(error='尝试过多，请稍后重试'), 429
    data = request.get_json()
    name, password = data.get('username'), data.get('password')
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 64:
        return jsonify(error='用户名需要在 1–64 字以内'), 400
    if not isinstance(password, str) or not 8 <= len(password) <= 128 or password != data.get('password2'):
        return jsonify(error='密码需要至少 8 位，且两次输入一致'), 400
    name = name.strip()
    password_hash = generate_password_hash(password)
    db = get_db()
    db.execute('BEGIN IMMEDIATE')
    try:
        if db.execute('SELECT 1 FROM users WHERE user_name=?', (name,)).fetchone():
            db.rollback()
            return jsonify(error='该用户名已被注册'), 409
        db.execute('INSERT INTO users(user_name,pwd) VALUES (?,?)', (name, password_hash))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return jsonify(ok=True, username=name), 201


@bp.get('/account')
def account():
    return jsonify(username=g.native_user['user_name'], accountId=g.native_user['user_id'],
                   balance=market.state(companion.owner_key())['balance'])


@bp.get('/supplies')
def inventory():
    return jsonify(supplies.state(companion.owner_key()))


@bp.post('/supplies/<operation>')
def supply_operation(operation):
    if operation not in ('daily', 'buy', 'cancel', 'bowl-refill', 'bowl-consume'):
        return jsonify(error='该操作尚未完成原生行为确认适配'), 409
    if operation in ('bowl-refill', 'bowl-consume') and get_db().execute(
            "SELECT 1 FROM portal_trips WHERE owner=? AND pet=? AND status IN ('pairing','active')",
            (companion.owner_key(), str(request.get_json().get('pet')))).fetchone():
        return jsonify(error='请先召回宠物再使用岛上的食盆'), 409
    return jsonify(supplies.operate(companion.owner_key(), operation, request.get_json()))


@bp.get('/farm')
def garden():
    return jsonify(farm.state(companion.owner_key()))


@bp.post('/farm/<operation>')
def garden_operation(operation):
    if operation not in ('start', 'buy', 'plant', 'water', 'fertilize', 'harvest', 'cook'):
        return jsonify(error='原生地图摆放尚待地图版本适配，不会写入旧地图坐标'), 409
    return jsonify(farm.operate(companion.owner_key(), operation, request.get_json()))


@bp.get('/history')
def history():
    from .mobile import _selected_pet
    try:
        return jsonify(messages=companion.history(companion.owner_key(), _selected_pet()))
    except (ValueError, LookupError):
        return jsonify(error='请选择有效宠物'), 400


@bp.post('/chat')
def chat():
    from .mobile import chat as mobile_chat
    g.mobile_user = g.native_user
    return mobile_chat()


@bp.get('/voices')
def voice_state():
    from .pet_voice import profiles
    return profiles()


@bp.post('/voices/selection')
def voice_selection():
    from .pet_voice import selection
    return selection()


@bp.post('/voices')
def voice_upload():
    from .pet_voice import profiles
    return profiles()


@bp.post('/voices/<profile_id>/preview')
def voice_preview(profile_id):
    from .pet_voice import preview
    return preview(profile_id)


@bp.post('/tts')
def speech():
    from .pet_voice import pet
    data = request.get_json()
    text = data.get('text')
    if not isinstance(text, str) or not 1 <= len(text.strip()) <= 500:
        return jsonify(error='朗读内容需要在 1–500 字以内'), 400
    number = pet(data.get('petId'))
    selected = voices.active(companion.owner_key(), number)
    # Null means the default voice; even this must match the request snapshot.
    if 'voiceProfileId' not in data or data['voiceProfileId'] != (selected['id'] if selected else None):
        return jsonify(error='声音已切换，请重新播放'), 409
    raw = voices.synthesize(text.strip(), selected['voice'] if selected else voices.default_voice(number))
    return current_app.response_class(raw, mimetype='audio/wav')


@bp.delete('/voices/<profile_id>')
def voice_delete(profile_id):
    voices.remove(companion.owner_key(), profile_id)
    return jsonify(ok=True)


@bp.post('/voices/<profile_id>/reconcile')
def voice_reconcile(profile_id):
    return jsonify(voices.reconcile(companion.owner_key(), profile_id))


@bp.get('/companion')
def companion_profile():
    from .companion import archive
    return archive()


@bp.route('/memories', methods=['POST'])
@bp.route('/memories/<int:fact_id>', methods=['PATCH', 'DELETE'])
def memories(fact_id=None):
    from .companion import edit_memory
    return edit_memory(fact_id)


@bp.get('/market')
def market_state():
    return jsonify(market.state(companion.owner_key()))


@bp.post('/market/<operation>')
def market_operation(operation):
    # Equip is intentionally gated until native/runtime models can be changed.
    if operation not in ('daily', 'buy'):
        return jsonify(error='原生换装显示仍在适配，当前外观不变'), 409
    return jsonify(market.operate(companion.owner_key(), operation, request.get_json()))


def _voice_ticket():
    from itsdangerous import URLSafeTimedSerializer
    return URLSafeTimedSerializer(current_app.secret_key, salt='native-voice-round-v1')


def _voice_call_context(data):
    from itsdangerous import BadSignature, SignatureExpired
    from ..services import voiceprint_service
    try:
        ticket = _voice_ticket().loads(data.get('ticket', ''), max_age=600)
    except (BadSignature, SignatureExpired, TypeError):
        raise voices.VoiceError('通话已过期，请重新连接', 409)
    owner = companion.owner_key()
    if ticket.get('session') != g.native_user['digest']:
        raise voices.VoiceError('通话账号已变化', 409)
    if voiceprint_service.requested_enabled(owner):
        raise voices.VoiceError('已开启声纹保护，原生声纹闸门适配前请使用网页通话', 409)
    selected = voices.active(owner, ticket['pet'])
    if (ticket['revision'] != companion.settings(owner)['revision']
            or ticket['voice'] != (selected['id'] if selected else None)):
        raise voices.VoiceError('档案或音色已更新，请重新开始通话', 409)
    return ticket


@bp.post('/realtime/session')
def realtime_session():
    from ..services import realtime_service, voiceprint_service
    from .realtime import _rate_limited
    from .pet_voice import pet
    owner = companion.owner_key()
    number = pet(request.get_json().get('petId'))
    if voiceprint_service.requested_enabled(owner):
        return jsonify(error='声纹保护已开启，原生声纹识别适配前请使用网页语音'), 409
    if _rate_limited('native:' + owner):
        return jsonify(error='连接过于频繁，请稍后重试'), 429
    try:
        payload = realtime_service.build_realtime_session(number, surface='chat')
    except realtime_service.RealtimeError as error:
        return jsonify(error=str(error)), error.status
    # The native client has not yet implemented the scene action protocol.
    # Keep conversation in chat mode instead of promising unexecuted actions.
    payload['ticket'] = _voice_ticket().dumps(dict(
        session=g.native_user['digest'], pet=number,
        revision=payload['profileRevision'],
        voice=payload['customVoice']['id'] if payload['customVoice'] else None))
    return jsonify(payload)


@bp.post('/realtime/check')
def realtime_check():
    _voice_call_context(request.get_json())
    return jsonify(ok=True)


@bp.post('/realtime/round')
def realtime_round():
    data = request.get_json()
    context = _voice_call_context(data)
    user, answer, request_id = data.get('message'), data.get('assistantText'), data.get('requestId')
    if (not isinstance(user, str) or not 1 <= len(user.strip()) <= 1000
            or not isinstance(answer, str) or not 1 <= len(answer.strip()) <= 2000
            or not isinstance(request_id, str) or not 8 <= len(request_id) <= 80):
        return jsonify(error='缺少完整语音回合'), 400
    from ..services.chat_service import handle_chat
    payload, status = handle_chat(dict(message=user, petId=context['pet'],
        assistantText=answer, requestId=request_id, surface='chat',
        profileRevision=context['revision'], profileScope=companion.browser_scope()),
        observed_reply=answer)
    return jsonify(payload), status
