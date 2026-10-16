"""Account/pet scoped speech voices. Recordings stay in memory, never in static assets."""
import array
import io
import re
import threading
import time
import uuid
import wave
from urllib.parse import quote

import requests
from flask import current_app
from ..db import get_db
from . import companion_service as companion

SLOTS = threading.BoundedSemaphore(2)
PREVIEW = '你好呀，我在派特岛等你。今天想和我一起散散步，还是看看花园里新开的花呢？'


class VoiceError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def init_schema():
    get_db().executescript('''
        CREATE TABLE IF NOT EXISTS pet_voice_profiles (
            id TEXT PRIMARY KEY, owner TEXT NOT NULL, pet_id INTEGER NOT NULL,
            name TEXT NOT NULL, status TEXT NOT NULL, voice TEXT NOT NULL DEFAULT '',
            file_id TEXT NOT NULL DEFAULT '', preview_file TEXT NOT NULL DEFAULT '',
            error TEXT NOT NULL DEFAULT '', created REAL NOT NULL,
            duration REAL NOT NULL, consent_at REAL NOT NULL, request_id TEXT NOT NULL,
            UNIQUE(owner, request_id));
        CREATE TABLE IF NOT EXISTS pet_voice_selection (
            owner TEXT NOT NULL, pet_id INTEGER NOT NULL, profile_id TEXT NOT NULL,
            PRIMARY KEY(owner, pet_id));
    ''')


def default_voice(pet_id):
    return (current_app.config.get('PET_TTS_VOICES') or {}).get(pet_id) or current_app.config.get('PET_TTS_DEFAULT_VOICE', 'tongtong')


def active(owner, pet_id):
    return get_db().execute('SELECT p.* FROM pet_voice_selection s JOIN pet_voice_profiles p ON p.id=s.profile_id '
                           "AND p.owner=s.owner AND p.pet_id=s.pet_id WHERE s.owner=? AND s.pet_id=? AND p.status='ready'", (owner, pet_id)).fetchone()


def owned(owner, profile_id):
    row = get_db().execute('SELECT * FROM pet_voice_profiles WHERE owner=? AND id=?', (owner, profile_id)).fetchone()
    if not row:
        raise VoiceError('没有找到这段宠物声音', 404)
    return row


def public(row):
    return {k: row[k] for k in ('id', 'pet_id', 'name', 'status', 'error', 'duration', 'created')}


def state(owner, pet_id):
    db = get_db()
    # A process restart cannot safely retry a potentially billed creation request.
    db.execute("UPDATE pet_voice_profiles SET status='uncertain',error='任务中断或超时，云端结果尚未确认；请勿重复提交同一录音。' WHERE owner=? AND status='creating' AND created<?", (owner, time.time()-300))
    db.commit()
    selected = active(owner, pet_id)
    return dict(scope=companion.browser_scope(), petId=pet_id, activeId=selected['id'] if selected else None,
                enabled=bool(current_app.config.get('GLM_API_KEY')) and owner.startswith('user:'),
                hint='上传音频会发送至智谱创建专属音色，服务商可能计费。请先试听再应用。' if owner.startswith('user:') else '请先登录账号，再创建和保存宠物的专属声音。',
                profiles=[public(r) for r in db.execute('SELECT * FROM pet_voice_profiles WHERE owner=? AND pet_id=? ORDER BY created DESC', (owner, pet_id))])


def validate_audio(raw):
    if not raw or len(raw) > 2_000_000:
        raise VoiceError('请上传 3–30 秒录音，转换后的音频不能超过 2MB')
    try:
        with wave.open(io.BytesIO(raw), 'rb') as wav:
            if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or wav.getframerate() != 24000 or wav.getcomptype() != 'NONE':
                raise VoiceError('请在页面中重新选择音频，转换为单声道 WAV 后上传')
            duration = wav.getnframes()/24000
            frames = wav.readframes(wav.getnframes())
            if len(frames) != wav.getnframes()*2 or not 3 <= duration <= 30:
                raise VoiceError('录音需要 3–30 秒，建议 10–20 秒清晰单人说话')
            samples = array.array('h', frames)
            if sum(v*v for v in samples)/len(samples) < 50**2:
                raise VoiceError('录音几乎没有声音，请换一段清晰说话录音')
            return duration
    except (wave.Error, EOFError, ValueError):
        raise VoiceError('音频损坏或格式不正确，请重新选择录音')


def voice_name(profile_id):
    # Upstream enforces 30 characters. Base36 keeps all 128 UUID bits in <=25.
    number = int(profile_id, 16)
    encoded = ''
    while number:
        number, digit = divmod(number, 36)
        encoded = '0123456789abcdefghijklmnopqrstuvwxyz'[digit] + encoded
    return 'pait_' + (encoded or '0')


def provider(method, path, missing_ok=False, **kwargs):
    key = current_app.config.get('GLM_API_KEY')
    if not key:
        raise VoiceError('语音服务尚未配置', 503)
    try:
        with requests.Session() as session:
            session.trust_env = current_app.config.get('LLM_TRUST_ENV', False)
            response = session.request(method, current_app.config['GLM_BASE_URL'].rstrip('/')+path,
                                       headers={'Authorization': 'Bearer '+key}, timeout=(10, 100), **kwargs)
    except requests.RequestException:
        raise VoiceError('语音服务连接超时，结果可能尚未确认，请稍后查看状态', 504)
    if response.status_code == 404 and missing_ok:
        return response
    if not response.ok:
        try:
            body = response.json()
            error = body.get('error', {}) if isinstance(body, dict) else {}
            if not isinstance(error, dict):error = {}
        except ValueError:
            error = {}
        code = str(error.get('code', ''))
        if not re.fullmatch(r'[0-9]{3,8}', code):code = ''
        detail = str(error.get('message', ''))
        message = {
            '1113':'语音服务账户余额不足，请在智谱平台充值后重试',
            '1210':'语音接口参数不正确，请联系维护者检查接入配置',
            '1211':'语音模型不存在，请检查模型配置',
            '1213':'语音接口缺少必要参数，请联系维护者检查接入配置',
            '1214':'语音接口参数不符合要求，请联系维护者检查接入配置',
            '1220':'当前账号没有访问该语音服务的权限',
            '1301':'语音服务未通过内容审核，请更换参考内容',
            '1302':'语音请求过于频繁，请稍后再试',
            '1305':'语音服务当前繁忙，请稍后再试',
            '1308':'语音服务已达到使用上限，请检查服务限额',
            '1311':'当前套餐未开放此语音模型权限',
        }.get(code) or {401:'语音服务凭证无效', 403:'语音服务权限不足', 429:'语音服务请求受限，请稍后再试'}.get(response.status_code, '语音服务暂时无法完成请求，请稍后查看状态')
        if code == '1214' and detail.startswith('voice_name:'):
            message = '音色名称不符合服务要求，请联系维护者检查接入配置'
            if '30 characters' in detail:message = '音色名称超过服务允许的 30 个字符，请更新页面后重新创建'
        if code:message += '（错误码 '+code+'）'
        # Do not log credentials, recording text, file IDs or raw upstream bodies.
        endpoint = '/files/*' if path.startswith('/files/') else path
        current_app.logger.warning('Voice provider rejected endpoint=%s http=%s code=%s', endpoint, response.status_code, code or 'unknown')
        raise VoiceError(message, 504 if response.status_code >= 500 else 502)
    return response


def synthesize(text, voice):
    response = provider('POST', '/audio/speech', json=dict(model='glm-tts', input=text, voice=voice,
                          response_format='wav', speed=.9, volume=1.0))
    raw = response.content
    if len(raw) < 44 or raw[:4] != b'RIFF' or raw[8:12] != b'WAVE' or len(raw) > 20_000_000:
        raise VoiceError('语音服务未返回可播放的声音', 502)
    return raw


def create(owner, pet_id, name, transcript, raw, request_id):
    duration = validate_audio(raw)
    if not re.fullmatch(r'[a-zA-Z0-9-]{16,64}', request_id):
        raise VoiceError('提交标识无效，请重新打开声音设置')
    db = get_db()
    db.execute('BEGIN IMMEDIATE')
    previous = db.execute('SELECT * FROM pet_voice_profiles WHERE owner=? AND request_id=?', (owner, request_id)).fetchone()
    if previous:
        db.rollback()
        if previous['pet_id'] != pet_id:
            raise VoiceError('本次提交的宠物已变化', 409)
        return public(previous)
    if db.execute('SELECT count(*) FROM pet_voice_profiles WHERE owner=?', (owner,)).fetchone()[0] >= 12:
        db.rollback()
        raise VoiceError('最多保存 12 个专属声音，请先删除不再使用的声音', 409)
    if not SLOTS.acquire(blocking=False):
        db.rollback()
        raise VoiceError('声音创建正在排队，请稍后再试', 429)
    profile_id = uuid.uuid4().hex
    try:
        db.execute('INSERT INTO pet_voice_profiles(id,owner,pet_id,name,status,created,duration,consent_at,request_id) VALUES (?,?,?,?,?,?,?,?,?)',
                   (profile_id,owner,pet_id,name,'creating',time.time(),duration,time.time(),request_id))
        db.commit()
        app = current_app._get_current_object()
        threading.Thread(target=generate, args=(app, profile_id, raw, transcript), daemon=True).start()
    except Exception:
        db.rollback()
        SLOTS.release()
        raise
    return public(owned(owner, profile_id))


def generate(app, profile_id, raw, transcript):
    try:
        with app.app_context():
            db = get_db()
            try:
                uploaded = provider('POST', '/files', data={'purpose':'voice-clone-input'}, files={'file':('reference.wav', raw, 'audio/wav')}).json()
                file_id = uploaded.get('id')
                if not isinstance(file_id, str) or not file_id:
                    raise VoiceError('上传结果无效，未创建音色', 502)
                db.execute('UPDATE pet_voice_profiles SET file_id=? WHERE id=?', (file_id,profile_id)); db.commit()
                payload = dict(model='glm-tts-clone', voice_name=voice_name(profile_id), input=PREVIEW, file_id=file_id, request_id=profile_id)
                if transcript:
                    payload['text'] = transcript
                cloned = provider('POST', '/voice/clone', json=payload).json()
                voice = cloned.get('voice')
                if not isinstance(voice, str) or not voice or len(voice)>256:
                    raise VoiceError('音色创建结果无效，暂未确认成功', 504)
                db.execute("UPDATE pet_voice_profiles SET status='ready',voice=?,preview_file=?,error='' WHERE id=?",
                           (voice,cloned.get('file_id') or '',profile_id)); db.commit()
            except Exception as error:
                message = str(error) if isinstance(error, VoiceError) else '音色服务返回异常，结果尚未确认'
                status = 'failed' if isinstance(error, VoiceError) and error.status != 504 else 'uncertain'
                db.execute('UPDATE pet_voice_profiles SET status=?,error=? WHERE id=?', (status,message,profile_id)); db.commit()
    finally:
        SLOTS.release()


def select(owner, pet_id, profile_id):
    db = get_db()
    db.execute('BEGIN IMMEDIATE')
    if profile_id:
        row = owned(owner, profile_id)
        if row['pet_id'] != pet_id or row['status'] != 'ready':
            db.rollback()
            raise VoiceError('该声音尚未就绪，或不属于这只宠物', 409)
        db.execute('INSERT OR REPLACE INTO pet_voice_selection VALUES (?,?,?)', (owner,pet_id,profile_id))
    else:
        db.execute('DELETE FROM pet_voice_selection WHERE owner=? AND pet_id=?', (owner,pet_id))
    db.commit()


def remove(owner, profile_id):
    row = owned(owner, profile_id)
    if row['status'] == 'creating':
        raise VoiceError('音色仍在创建，请等待结果后删除', 409)
    if row['status'] == 'uncertain':
        raise VoiceError('云端结果尚未确认，暂保留记录以便核查，避免留下无法追踪的音色', 409)
    db = get_db()
    db.execute('DELETE FROM pet_voice_selection WHERE owner=? AND profile_id=?', (owner,profile_id)); db.commit()
    if row['voice']:
        provider('POST', '/voice/delete', missing_ok=True, json={'voice':row['voice']})
        db.execute("UPDATE pet_voice_profiles SET voice='',status='failed' WHERE id=?", (profile_id,)); db.commit()
    for field in ('file_id', 'preview_file'):
        if row[field]:
            provider('DELETE', '/files/'+quote(row[field], safe=''), missing_ok=True)
            db.execute('UPDATE pet_voice_profiles SET '+field+"='' WHERE id=?", (profile_id,)); db.commit()
    db.execute('DELETE FROM pet_voice_profiles WHERE owner=? AND id=?', (owner,profile_id)); db.commit()


def reconcile(owner, profile_id):
    row = owned(owner, profile_id)
    if row['status'] != 'uncertain':
        raise VoiceError('这段声音不需要核查', 409)
    name = voice_name(profile_id)
    result = provider('GET', '/voice/list', params={'voiceName':name,'voiceType':'PRIVATE'}).json()
    matches = [item for item in result.get('voice_list', []) if item.get('voice_name')==name and isinstance(item.get('voice'),str) and item['voice']]
    if len(matches) != 1:
        raise VoiceError('暂未查到唯一的云端音色，请稍后再核查；不会重复创建或扣费', 409)
    db = get_db()
    db.execute("UPDATE pet_voice_profiles SET status='ready',voice=?,error='' WHERE owner=? AND id=? AND status='uncertain'", (matches[0]['voice'],owner,profile_id)); db.commit()
    return public(owned(owner,profile_id))
