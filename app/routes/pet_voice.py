from urllib.parse import urlsplit
from flask import Blueprint, jsonify, request, current_app
from ..services import pet_voice_service as voice, companion_service as companion

bp = Blueprint('pet_voice', __name__)


@bp.before_request
def guard():
    origin = request.headers.get('Origin')
    if origin and urlsplit(origin).netloc != request.host:
        return jsonify(error='请在本站设置宠物声音'), 403
    if request.method != 'GET':
        if not companion.owner_key().startswith('user:'):
            return jsonify(error='请先登录，再保存专属声音'), 403
        if request.headers.get('X-Profile-Scope') != companion.browser_scope():
            return jsonify(error='账号已变化，请重新打开声音设置'), 409


@bp.after_request
def private(response):
    response.headers['Cache-Control'] = 'private, no-store'
    return response


@bp.errorhandler(voice.VoiceError)
def error(exc):
    return jsonify(error=str(exc)), exc.status


def pet(value):
    try:
        number = int(value)
    except (ValueError, TypeError):
        number = 0
    if number not in (1,2,3,4):
        raise voice.VoiceError('请选择有效宠物')
    return number


@bp.route('/api/pet-voices', methods=['GET', 'POST'])
def profiles():
    owner = companion.owner_key()
    if request.method == 'GET':
        return jsonify(voice.state(owner, pet(request.args.get('petId'))))
    if not request.content_length or request.content_length > 2_100_000:
        raise voice.VoiceError('音频过大，请选择 3–30 秒录音', 413)
    if request.form.get('consent') != 'true':
        raise voice.VoiceError('请确认使用本人或已获授权的说话录音')
    if not current_app.config.get('GLM_API_KEY'):
        raise voice.VoiceError('语音服务尚未配置', 503)
    name = request.form.get('name', '').strip()
    transcript = request.form.get('transcript', '').strip()
    if not 1 <= len(name) <= 32 or len(transcript) > 1000:
        raise voice.VoiceError('声音名称限 32 字，录音原文限 1000 字')
    audio = request.files.get('audio')
    if not audio:
        raise voice.VoiceError('请选择录音文件')
    return jsonify(voice.create(owner, pet(request.form.get('petId')), name, transcript,
                                audio.read(2_000_001), request.form.get('requestId',''))), 202


@bp.route('/api/pet-voices/selection', methods=['PATCH'])
def selection():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not (data.get('id') is None or isinstance(data.get('id'), str)):
        raise voice.VoiceError('无效的声音设置')
    number = pet(data.get('petId'))
    voice.select(companion.owner_key(), number, data.get('id'))
    return jsonify(voice.state(companion.owner_key(), number))


@bp.route('/api/pet-voices/<profile_id>/preview', methods=['POST'])
def preview(profile_id):
    row = voice.owned(companion.owner_key(), profile_id)
    if row['status'] != 'ready':
        raise voice.VoiceError('请等待音色创建完成', 409)
    return current_app.response_class(voice.synthesize(voice.PREVIEW, row['voice']), mimetype='audio/wav')


@bp.route('/api/pet-voices/<profile_id>', methods=['DELETE'])
def remove(profile_id):
    voice.remove(companion.owner_key(), profile_id)
    return jsonify(ok=True)


@bp.route('/api/pet-voices/<profile_id>/reconcile', methods=['POST'])
def reconcile(profile_id):
    return jsonify(voice.reconcile(companion.owner_key(),profile_id))
