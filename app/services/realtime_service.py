# -*- coding: utf-8 -*-
"""GLM Realtime 会话服务：短期 JWT 签发 + 会话配置组装。

安全边界（方案 §0/§4.1）：
- GLM_API_KEY 只在后端使用，绝不进入任何接口响应或前端代码；
- 浏览器拿到的只有短效 JWT（GLM 官方鉴权格式：alg=HS256 + sign_type=SIGN，
  payload 为 api_key/exp/timestamp，默认 TTL 600 秒、上限 900 秒）；
- 音色只从 PET_TTS_VOICES 白名单按 petId 选择，忽略客户端传值；
- 人设复用 pet_registry.build_system_prompt，禁止另抄一套。
"""
import time
import uuid

import jwt
from flask import current_app

from ..llm import pets as pet_registry

# 语音约束追加在人设之后（方案 §7）：口语化、短句、可打断、不读 Markdown
VOICE_CONSTRAINTS = (
    '\n\n实时语音对话注意：'
    '你现在和用户进行的是语音通话，回复必须口语化、自然、简短，一次只说两三句话。'
    '不要使用任何 Markdown 格式、编号列表或表情符号。'
    '用户随时可能插话打断你，被打断时立即停下倾听，不要坚持把上一句说完。'
)


class RealtimeError(Exception):
    """业务异常：message 可回给客户端，status 为 HTTP 状态码。"""

    def __init__(self, message, status=500):
        super().__init__(message)
        self.status = status


def issue_realtime_token(ttl_seconds=600):
    """用 GLM_API_KEY（格式 {id}.{secret}）签发短期 JWT。

    返回 (token, exp_unix_seconds)。key 缺失返回 503，格式错误返回 500，
    两种情况都只在服务端日志留痕，不回显 key 内容。
    """
    api_key = current_app.config.get('GLM_API_KEY', '')
    if not api_key:
        raise RealtimeError('realtime api key missing', 503)
    parts = api_key.split('.', 1)
    if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
        current_app.logger.error('GLM_API_KEY format invalid for realtime JWT')
        raise RealtimeError('realtime api key invalid', 500)
    key_id, secret = parts
    now = int(time.time())
    payload = {
        'api_key': key_id,
        'exp': now + int(ttl_seconds),
        'timestamp': int(time.time() * 1000),
    }
    token = jwt.encode(payload, secret, algorithm='HS256',
                       headers={'alg': 'HS256', 'sign_type': 'SIGN'})
    return token, payload['exp']


def build_realtime_session(pet_id, gender=None):
    """组装 POST /api/realtime/session 的响应体。"""
    cfg = current_app.config
    if not cfg.get('GLM_REALTIME_ENABLED'):
        raise RealtimeError('realtime disabled', 503)
    try:
        pet = pet_registry.get_pet(pet_id)
    except LookupError:
        raise RealtimeError('pet not found', 404)
    if gender not in ('male', 'female', None):
        gender = None
    # 音色：服务端白名单决定（方案 §4.1）
    voice = (cfg.get('PET_TTS_VOICES') or {}).get(pet['id']) \
        or cfg.get('PET_TTS_DEFAULT_VOICE', 'tongtong')
    ttl = int(cfg.get('GLM_REALTIME_TOKEN_TTL', 600))
    token, exp = issue_realtime_token(ttl)
    instructions = pet_registry.build_system_prompt(pet, gender) + VOICE_CONSTRAINTS
    return {
        'sessionId': str(uuid.uuid4()),
        'token': token,
        'expiresAt': exp,
        'wsBaseUrl': cfg.get('GLM_REALTIME_URL',
                             'wss://open.bigmodel.cn/api/paas/v4/realtime'),
        'config': {
            'chat_mode': 'audio',
            'input_audio_format': cfg.get('GLM_REALTIME_INPUT_FORMAT', 'pcm16'),
            'output_audio_format': cfg.get('GLM_REALTIME_OUTPUT_FORMAT', 'pcm'),
            'turn_detection': {'type': cfg.get('GLM_REALTIME_VAD', 'server_vad')},
            'voice': voice,
            'instructions': instructions,
        },
    }
