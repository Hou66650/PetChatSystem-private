"""Same-origin, explicitly enabled computer inference for the current website."""
import atexit
import hmac
import secrets
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request, session
from ..services.vision_service import VisionEngine, VisionBusy

bp = Blueprint('vision', __name__, url_prefix='/api/vision')


@bp.record_once
def install(state):
    engine = VisionEngine(Path(state.app.static_folder) / 'js/vendor/mediapipe')
    state.app.extensions['vision_engine'] = engine
    atexit.register(engine.close)


@bp.after_request
def private_response(response):
    response.headers['Cache-Control'] = 'no-store'
    return response


@bp.get('/capabilities')
def capabilities():
    if not current_app.config.get('VISION_REMOTE_ENABLED', False):
        return jsonify(enabled=False)
    if not session.get('vision_token'):
        session['vision_token'] = secrets.token_urlsafe(32)
    return jsonify(enabled=True, token=session['vision_token'], maxWidth=640, maxHeight=480)


@bp.post('/frame')
def frame():
    if not current_app.config.get('VISION_REMOTE_ENABLED', False):
        return jsonify(error='电脑识别未开启'), 503
    if (request.headers.get('Origin', '').rstrip('/') != request.host_url.rstrip('/')
            or request.headers.get('Sec-Fetch-Site') == 'cross-site'):
        return jsonify(error='请求来源不受支持'), 403
    token = session.get('vision_token', '')
    if not token or not hmac.compare_digest(token.encode(), request.headers.get('X-Vision-Token', '').encode()):
        return jsonify(error='请重新开启摄像头识别'), 403
    if request.mimetype != 'image/jpeg':
        return jsonify(error='需要 JPEG 画面'), 415
    if not request.content_length or request.content_length > 256 * 1024:
        return jsonify(error='画面超过大小限制'), 413
    if any(request.args.get(key, '1') not in ('0', '1') for key in ('face', 'hands')):
        return jsonify(error='识别选项无效'), 400
    face, hands = (request.args.get(key, '1') == '1' for key in ('face', 'hands'))
    if not face and not hands:
        return jsonify(error='请至少选择一种识别'), 400
    try:
        result = current_app.extensions['vision_engine'].detect(request.get_data(cache=False), face, hands)
        return jsonify(result)
    except VisionBusy:
        return jsonify(error='电脑识别忙，请稍后重试'), 429
    except ValueError:
        return jsonify(error='摄像头画面无效或尺寸过大'), 400
    except Exception:
        # Never include image data, token or model exceptions in logs/responses.
        return jsonify(error='电脑识别暂不可用，请检查识别依赖与模型文件'), 503
