# -*- coding: utf-8 -*-
"""实时语音（GLM Realtime）路由：短期会话签发 + 独立调试页。

浏览器直连 Realtime WS（token 走 URL query 参数，浏览器 WS 无法带 Header）；
本路由只做鉴权前置、限流和人设组装，不中转音频帧（方案 §3/§4.2）。
"""
import time
from collections import defaultdict

from flask import Blueprint, current_app, jsonify, render_template, request

from ..services.realtime_service import RealtimeError, build_realtime_session

bp = Blueprint('realtime', __name__)

# 按 IP 的进程内限流：5 次/分钟（方案 §4.2；单用户实例够用，不加存储依赖）
_rate_hits = defaultdict(list)
_RATE_LIMIT = 5
_RATE_WINDOW = 60.0


def _rate_limited(ip):
    now = time.monotonic()
    hits = [t for t in _rate_hits.get(ip, ()) if now - t < _RATE_WINDOW]
    if len(hits) >= _RATE_LIMIT:
        return True
    hits.append(now)
    _rate_hits[ip] = hits
    if len(_rate_hits) > 1000:   # 防止长期运行下 dict 无限膨胀
        _rate_hits.clear()
    return False


@bp.route('/api/realtime/session', methods=['POST'])
def realtime_session():
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict): return jsonify(error='invalid request'), 400
    try:
        pet_id = int(data.get('petId', 1))
    except (TypeError, ValueError):
        return jsonify({'error': 'invalid petId'}), 400
    gender = data.get('petGender')
    if gender not in ('male', 'female', None):
        gender = None
    if _rate_limited(request.remote_addr or 'unknown'):
        return jsonify({'error': 'rate limited, retry later'}), 429
    started = time.monotonic()
    try:
        payload = build_realtime_session(pet_id, gender, 'den' if data.get('surface') == 'den' else 'chat')
    except RealtimeError as e:
        # 日志只记元信息，严禁 token / API Key / 人设正文
        current_app.logger.info('realtime session petId=%s status=%s', pet_id, e.status)
        return jsonify({'error': str(e)}), e.status
    current_app.logger.info('realtime session petId=%s status=200 cost=%.0fms',
                            pet_id, (time.monotonic() - started) * 1000)
    return jsonify(payload), 200, {'Cache-Control': 'no-store'}


@bp.route('/realtime-debug')
def realtime_debug():
    """独立调试页：真实麦克风 + 合成语音注入两种端到端验证模式（方案 §9 第1天）。"""
    return render_template('realtime_debug.html')
