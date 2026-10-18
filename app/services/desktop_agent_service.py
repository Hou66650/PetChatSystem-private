"""Trip-authenticated desktop chat. No task tools and no browser-session identity."""
import base64
import hashlib
import json
import re
import threading
import time
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path

from flask import current_app
from ..db import get_db
from ..llm import pets
from . import companion_service as memory, pet_voice_service as voice, portal_service as portal


def init_schema():
    get_db().executescript('''
    CREATE TABLE IF NOT EXISTS desktop_agent_requests(
      owner TEXT NOT NULL, pet TEXT NOT NULL, trip TEXT NOT NULL,
      operation TEXT NOT NULL, request_id TEXT NOT NULL, payload_hash TEXT NOT NULL,
      version TEXT NOT NULL, state TEXT NOT NULL, created REAL NOT NULL,
      PRIMARY KEY(owner,pet,trip,operation,request_id));
    ''')
    current_app.extensions['desktop_reply_cache']=(threading.RLock(),OrderedDict())


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


@lru_cache(maxsize=128)
def file_digest(filename,mtime,size):
    if size>50*1024*1024:raise portal.PortalError('模型超过资源预算',413,'ASSET_INVALID')
    return hashlib.sha256(Path(filename).read_bytes()).hexdigest()


def asset_hash(url):
    root=Path(current_app.static_folder).resolve()
    if not isinstance(url,str) or not url.startswith('/static/models/') or not url.endswith('.glb'):
        raise portal.PortalError('模型路径无效',400,'ASSET_INVALID')
    path=(root/url.removeprefix('/static/')).resolve()
    if not path.is_relative_to(root/'models'):raise portal.PortalError('模型路径无效',400,'ASSET_INVALID')
    try:
        stat=path.stat()
        return file_digest(str(path),stat.st_mtime_ns,stat.st_size)
    except OSError:raise portal.PortalError('模型资源不可用',404,'ASSET_INVALID')


def manifest(t):
    spec=portal.pet_spec(t['owner'],t['pet'])
    model_hash=hashlib.sha256(portal.travel_model(t,'visitor')).hexdigest() if spec.get('custom') else asset_hash(spec['model'])
    accessories={item['id']:asset_hash('/static/models/wardrobe-v1/'+item['id']+'.glb') for item in spec.get('wardrobe',[])}
    try:pet=pets.get_pet(t['pet'])
    except LookupError:pet=None
    selected=voice.active(t['owner'],pet['id']) if pet else None
    voice_id=selected['voice'] if selected else voice.default_voice(pet['id']) if pet else ''
    revision=memory.settings(t['owner'])['revision']
    version=digest([t['owner'],t['pet'],t['id'],revision,pet,voice_id,selected['id'] if selected else None,model_hash,accessories,spec.get('height')])
    enabled=bool(current_app.config.get('DESKTOP_AGENT_ENABLED')) and pet is not None
    return dict(version=version,modelSha256=model_hash,accessories=accessories,
                chatEnabled=enabled,voiceEnabled=enabled and bool(current_app.config.get('GLM_API_KEY')),
                toolsEnabled=enabled and bool(current_app.config.get('TOOLS_ENABLED',True)),multipetEnabled=False,expiresAt=portal.expires_at(t))


def check(t,version):
    row=get_db().execute('SELECT * FROM portal_trips WHERE id=?',(t['id'],)).fetchone()
    if not row or row['status']!='active' or time.time()>=portal.expires_at(row) or time.time()-row['updated']>45:
        raise portal.PortalError('桌面行程已结束',409,'TRIP_ENDED')
    if row['phase']!='roaming':raise portal.PortalError('请等待宠物到达桌面',425,'TRIP_NOT_READY')
    m=manifest(row)
    if not m['chatEnabled']:raise portal.PortalError('此宠物的桌面聊天尚未开放',403,'AGENT_DISABLED')
    if version!=m['version']:raise portal.PortalError('档案、声音或模型已变化，请重新发送',409,'CONTEXT_CHANGED')
    return m


def cache(key,value=None):
    lock,entries=current_app.extensions['desktop_reply_cache']
    with lock:
        now=time.monotonic()
        for old in list(entries):
            if now-entries[old][0]>=600:entries.pop(old)
        if value is not None:
            size=len(json.dumps(value,ensure_ascii=False).encode())
            entries[key]=(now,value,size)
            while len(entries)>128 or sum(v[2] for v in entries.values())>32*1024*1024:entries.popitem(last=False)
        item=entries.get(key)
        return item[1] if item else None


def internal_id(key):return 'desktop:'+digest(key)


def reply_for(t,request_id,version):
    key=(t['owner'],t['pet'],t['id'],'chat',request_id)
    row=get_db().execute('SELECT * FROM desktop_agent_requests WHERE owner=? AND pet=? AND trip=? AND operation=? AND request_id=?',key).fetchone()
    if not row or row['state']!='done' or row['version']!=version:
        raise portal.PortalError('原回复暂不可确认，请勿重复执行',409,'RESULT_UNKNOWN')
    value=cache(key)
    if value is not None:return value
    # With memory off no reply text is persisted. A tombstone still prevents replay.
    if memory.settings(t['owner'])['enabled']:
        saved=get_db().execute("SELECT content FROM companion_messages WHERE owner=? AND pet_id=? AND request_id=? AND role='assistant'",
                               (t['owner'],t['pet'],internal_id(key))).fetchone()
        if saved:return dict(reply=saved['content'],requestId=request_id,version=version,actions=[],duplicate=True)
    raise portal.PortalError('原回复暂不可确认，请勿重复执行',409,'RESULT_UNKNOWN')


def dispatch(t,operation,data):
    if operation=='manifest':return manifest(t)
    allowed={'requestId','version','message'} if operation=='chat' else {'requestId','version','replyRequestId'}
    if set(data)-allowed:raise portal.PortalError('请求包含不支持的参数')
    rid=data.get('requestId')
    if not isinstance(rid,str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,80}',rid):raise portal.PortalError('请求编号无效')
    version=data.get('version');m=check(t,version)
    if operation=='chat':
        message=data.get('message')
        if not isinstance(message,str) or not message.strip() or len(message)>current_app.config['MAX_MESSAGE_CHARS']:
            raise portal.PortalError('请输入长度合适的消息')
    else:
        if not m['voiceEnabled']:raise portal.PortalError('语音服务尚未配置',503,'VOICE_DISABLED')
        if not isinstance(data.get('replyRequestId'),str):raise portal.PortalError('回复编号无效')
    key=(t['owner'],t['pet'],t['id'],operation,rid)
    payload_hash=digest(data);db=get_db()
    with db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT * FROM desktop_agent_requests WHERE owner=? AND pet=? AND trip=? AND operation=? AND request_id=?',key).fetchone()
        if row:
            if row['payload_hash']!=payload_hash:raise portal.PortalError('相同请求编号的内容不一致',409,'REQUEST_CONFLICT')
        else:db.execute('INSERT INTO desktop_agent_requests VALUES (?,?,?,?,?,?,?,?,?)',(*key,payload_hash,version,'started',time.time()))
    if row:
        if row['state']=='done':
            value=cache(key)
            if value is not None:return dict(value,duplicate=True)
            if operation=='chat':return reply_for(t,rid,version)
        raise portal.PortalError('原结果暂不可确认，不会自动重复调用',409,'RESULT_UNKNOWN')
    try:
        if operation=='chat':
            from .chat_service import chat_for_owner
            result,status=chat_for_owner(t['owner'],t['pet'],{'message':message,'requestId':internal_id(key)},
                                        surface='desktop',before_save=lambda:check(t,version))
            if status!=200:raise portal.PortalError(result['error'],status,'CHAT_FAILED')
            value=dict(reply=result['reply'],requestId=rid,version=version,actions=[])
        else:
            reply=reply_for(t,data['replyRequestId'],version)
            selected=voice.active(t['owner'],int(t['pet']))
            if not voice.SLOTS.acquire(blocking=False):raise portal.PortalError('语音服务正忙，请稍后再试',429,'VOICE_BUSY')
            try:raw=voice.synthesize(reply['reply'][:1000],selected['voice'] if selected else voice.default_voice(int(t['pet'])))
            except voice.VoiceError as error:raise portal.PortalError(str(error),error.status,'VOICE_FAILED')
            finally:voice.SLOTS.release()
            value=dict(audio=base64.b64encode(raw).decode(),mime='audio/wav',requestId=rid,version=version)
        check(t,version)
        cache(key,value)
        with db:db.execute("UPDATE desktop_agent_requests SET state='done' WHERE owner=? AND pet=? AND trip=? AND operation=? AND request_id=?",key)
        return value
    except Exception:
        with db:db.execute("UPDATE desktop_agent_requests SET state='failed' WHERE owner=? AND pet=? AND trip=? AND operation=? AND request_id=?",key)
        raise
