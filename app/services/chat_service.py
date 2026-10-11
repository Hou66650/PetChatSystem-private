# -*- coding: utf-8 -*-
"""聊天编排：角色提示词 + 历史裁剪 + 调用 GLM。

旧版的两个隐性 bug 在这里一并修复：
1. convert_to_openai_messages 把所有非 'w' 的 sender（包括 AI 的自定义名）
   一律映射成 user 角色，导致"记忆"里的 AI 回复全被当成用户发言；
   现在前端历史带 role 字段，后端只认 user/assistant，其余丢弃。
2. 全量历史无限送入，长对话会撑爆 token；现在按 HISTORY_LIMIT 截断。
"""
from flask import current_app

from ..config import Config
from ..llm import pets as pet_registry
from ..llm.client import LLMError


def _sanitize_history(history):
    """清洗前端聊天历史：只保留带合法 role 的条目，截断条数与单条长度。"""
    if not isinstance(history, list):
        return []
    msgs = []
    for entry in history:
        if not isinstance(entry, dict):
            continue
        role = entry.get('role')
        content = str(entry.get('message') or entry.get('content') or '').strip()
        if role not in ('user', 'assistant') or not content:
            continue
        msgs.append({'role': role, 'content': content[:Config.MAX_MESSAGE_CHARS]})
    return msgs[-Config.HISTORY_LIMIT:]


def handle_chat(data):
    """处理 /get_gpt_response。返回 (payload, http_status)。"""
    if not isinstance(data, dict):
        return {'error': '请求格式错误'}, 400

    user_message = str(data.get('message') or '').strip()
    if not user_message:
        return {'error': '请输入消息内容。'}, 400

    # 宠物编号白名单加载，非法编号回落到 1 号宠物
    try:
        pet = pet_registry.get_pet(data.get('petId', 1))
    except LookupError:
        pet = pet_registry.get_pet(1)

    model = data.get('model') or Config.GLM_MODELS[0]
    client = current_app.extensions['llm']

    # 性别白名单（S1-09）：只有 male/female 进入 prompt，其余（含任意长字符串/对象）一律丢弃
    gender = data.get('petGender')
    if gender not in ('male', 'female'):
        gender = None

    messages = [{'role': 'system', 'content': pet_registry.build_system_prompt(pet, gender)}]
    messages += _sanitize_history(data.get('chatHistory'))
    messages.append({'role': 'user', 'content': user_message[:Config.MAX_MESSAGE_CHARS]})

    try:
        reply = client.chat(messages, model=model)
    except LLMError as e:
        current_app.logger.error('GLM 调用失败: %s', e)
        # 限流是瞬时的：明确告诉用户稍等再试，避免误以为服务坏了
        if '429' in str(e):
            return {'error': '当前聊天的人有点多，请几秒后再试一下'}, 503
        return {'error': f'AI 服务暂时不可用，请稍后再试（{e}）'}, 503

    return {
        'reply': reply,
        'pet': pet_registry.public_info(pet),
    }, 200
