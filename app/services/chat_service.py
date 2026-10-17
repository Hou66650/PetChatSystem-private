"""Dialogue, server-owned memory and validated behavior plans share one model call."""
import uuid
from urllib.parse import urlsplit

from flask import current_app, request

from ..config import Config
from ..llm import pets as pet_registry
from ..llm.client import LLMError
from . import companion_service as memory


def _sanitize_history(history):
    if not isinstance(history,list): return []
    return [{'role':r['role'],'content':str(r.get('message') or r.get('content') or '')[:Config.MAX_MESSAGE_CHARS]}
            for r in history if isinstance(r,dict) and r.get('role') in ('user','assistant')][-Config.HISTORY_LIMIT:]


def handle_chat(data, observed_reply=None):
    """Legacy Web/Harmony adapter: identity comes only from the signed session."""
    if not isinstance(data,dict): return {'error':'请求格式错误'},400
    origin=request.headers.get('Origin')
    if (origin and urlsplit(origin).netloc != request.host) or request.headers.get('Sec-Fetch-Site')=='cross-site':
        return {'error':'请在本站发送消息'},403
    return chat_for_owner(memory.owner_key(), data.get('petId', 1), data,
                          surface='den' if data.get('surface') == 'den' else 'chat',
                          observed_reply=observed_reply)


def chat_for_owner(owner, pet_id, data, *, surface, observed_reply=None, before_save=None):
    """Internal entry. Caller must authenticate owner/pet; body cannot select identity.

    Requires an application context, not a browser request/session. Desktop caller
    supplies a transaction guard; web adapters cannot select desktop surface.
    """
    if not isinstance(data,dict): return {'error':'请求格式错误'},400
    if surface not in ('chat', 'den', 'desktop') or (surface == 'desktop' and before_save is None):
        return {'error':'该聊天入口尚未支持此场景'},400
    from ..db import get_db
    if not isinstance(owner,str) or not get_db().execute(
            'SELECT 1 FROM companion_owners WHERE owner=?',(owner,)).fetchone():
        return {'error':'聊天身份无效'},403
    if not isinstance(data.get('message'),str) or not data['message'].strip():
        return {'error':'请输入消息内容。'},400
    message=data['message'].strip()[:Config.MAX_MESSAGE_CHARS]
    try:
        if type(pet_id) is not int and not (isinstance(pet_id,str) and pet_id.isascii() and pet_id.isdecimal()):
            raise LookupError('Invalid pet identity')
        pet=pet_registry.get_pet(pet_id)
    except LookupError: return {'error':'宠物不存在'},400
    gender=data.get('petGender')
    if gender not in ('male','female'): gender=None
    state=memory.settings(owner)
    if observed_reply is not None and (data.get('profileRevision', state['revision']) != state['revision']
            or data.get('profileScope', memory.owner_scope(owner)) != memory.owner_scope(owner)):
        return {'error':'档案已更新，这轮旧语音未写入，请重新开始通话。'},409
    request_id=data.get('requestId')
    if not isinstance(request_id,str) or not 8<=len(request_id)<=80: request_id=uuid.uuid4().hex
    previous=get_db().execute("SELECT content FROM companion_messages WHERE owner=? AND pet_id=? AND request_id=? AND role='assistant'",(owner,pet['id'],request_id)).fetchone()
    if previous:
        return {'reply':previous['content'],'pet':pet_registry.public_info(pet),'actions':[],
                'duplicate':True,'profile':memory.profile(owner,pet['id'])},200
    messages=[{'role':'system','content':pet_registry.build_system_prompt(pet,gender)+memory.planner_prompt(owner,pet['id'],surface)}]
    if surface=='desktop':
        messages[0]['content']+='\n你正在电脑桌面与主人聊天。目前只支持聊天和朗读，没有提醒、专注计时、系统通知、文件或应用操作工具。不要声称已执行这些操作；收到此类请求时说明尚未开放。actions 必须是 []。'
    if state['enabled']:
        messages += [{'role':r['role'],'content':r['content']} for r in memory.history(owner,pet['id'],for_prompt=True)]
    # Browser chatHistory and body userId are deliberately ignored: account isolation is server-owned.
    messages.append({'role':'user','content':message})
    try:
        raw=current_app.extensions['llm'].chat(messages,model=data.get('model') or Config.GLM_MODELS[0],temperature=.4,json_mode=True)
    except LLMError:
        current_app.logger.warning('Companion model request failed')
        return {'error':'AI 服务暂时不可用，请稍后重试'},503
    plan=memory.decode_plan(raw,message,surface,pet['id'])
    if observed_reply is not None: plan['reply']=observed_reply
    if not memory.save_turn(owner,pet['id'],request_id,message,plan,state['revision'],before_save=before_save):
        return {'error':'陪伴档案刚刚发生变化，请重新发送这条消息。'},409
    return {'reply':plan['reply'],'pet':pet_registry.public_info(pet),'actions':plan['actions'],
            'profile':memory.profile(owner,pet['id']),
            'memorySaved':bool(state['enabled'] and plan['memories']),
            'requestId':request_id,'care':plan.get('care')},200
