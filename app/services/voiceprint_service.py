"""Local, owner-scoped speaker familiarity. Never an authentication mechanism."""
import json
import threading
import uuid
from ..db import get_db

_encoder = None
_lock = threading.Lock()


def init_schema():
    get_db().executescript('''
    CREATE TABLE IF NOT EXISTS voiceprint_profiles(id TEXT PRIMARY KEY, owner TEXT NOT NULL,
        name TEXT NOT NULL, vectors TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS voiceprint_owner ON voiceprint_profiles(owner);
    CREATE TABLE IF NOT EXISTS voiceprint_settings(owner TEXT PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 0);
    ''')


def profiles(owner):
    return get_db().execute('SELECT * FROM voiceprint_profiles WHERE owner=? ORDER BY rowid', (owner,)).fetchall()


def requested_enabled(owner):
    row = get_db().execute('SELECT enabled FROM voiceprint_settings WHERE owner=?', (owner,)).fetchone()
    return bool(row and row['enabled'])


def enabled(owner):
    return requested_enabled(owner) and bool(profiles(owner))


def set_enabled(owner, value):
    db = get_db()
    db.execute('INSERT INTO voiceprint_settings VALUES (?,?) ON CONFLICT(owner) DO UPDATE SET enabled=excluded.enabled', (owner, int(value)))
    db.commit()


def samples(raw, minimum=1.8):
    import numpy as np
    if len(raw) % 2 or not 3200 <= len(raw) <= 640000:
        raise ValueError('请提供不超过20秒的16kHz单声道录音')
    wav = np.frombuffer(raw, dtype='<i2').astype(np.float32) / 32768
    if np.mean(np.abs(wav) >= .99) > .02:
        raise ValueError('录音有明显爆音，请远离麦克风一点')
    # VAD filters non-speech before computing a voice embedding.
    import webrtcvad
    vad = webrtcvad.Vad(2)
    frames = [wav[i:i+480] for i in range(0, len(wav)-479, 480)]
    speech = [f for f in frames if np.sqrt(np.mean(f*f)) > .006 and vad.is_speech((f*32767).astype('<i2').tobytes(),16000)]
    if len(speech)*.03 < minimum:
        raise ValueError('有效人声太短，请在安静环境连续说几句话')
    # Match the encoder's training preprocessing for both enrollment and live speech.
    # VAD has already validated speech; normalize only afterwards, never amplify silence.
    from resemblyzer.audio import normalize_volume
    from resemblyzer.hparams import audio_norm_target_dBFS
    return normalize_volume(np.concatenate(speech), audio_norm_target_dBFS, increase_only=True)


def embeddings(wav, enrollment=False):
    import numpy as np
    global _encoder
    from resemblyzer import VoiceEncoder
    with _lock:
        if _encoder is None:
            # Small encoder on CPU leaves the browser GPU available for the island.
            import torch
            torch.set_num_threads(2)
            _encoder = VoiceEncoder(device='cpu', verbose=False)
        parts = np.array_split(wav, 3) if enrollment else [wav]
        result = np.asarray([_encoder.embed_utterance(p) for p in parts], dtype=np.float32)
    if not np.isfinite(result).all():
        raise ValueError('录音无法提取稳定声纹，请重录')
    return result / np.maximum(np.linalg.norm(result, axis=1, keepdims=True), 1e-8)


def enroll(owner, name, raw):
    if len(profiles(owner)) >= 5:
        raise ValueError('最多录入5位熟悉的人，请先删除旧声纹')
    vectors = embeddings(samples(raw, 6), True)
    if min(float(vectors[i] @ vectors[j]) for i,j in [(0,1),(1,2),(0,2)]) < .65:
        raise ValueError('几段声音不够一致，请保持同一人说话后重录')
    db = get_db()
    db.execute('INSERT INTO voiceprint_profiles VALUES (?,?,?,?)', (uuid.uuid4().hex,owner,name,json.dumps(vectors.tolist())))
    db.commit()
    set_enabled(owner, True)


def match(vector, rows):
    import numpy as np
    scores = sorted([(float(np.mean(np.asarray(json.loads(r['vectors'])) @ vector)),r['name']) for r in rows], reverse=True)
    if not scores:
        return {'kind':'uncertain','name':None,'reason':'no_profiles','message':'当前账号或浏览器没有录入声纹，请先录入。'}
    top,name = scores[0]
    # Deliberately leave a wide uncertainty band. Thresholds need real household calibration.
    if top >= .80 and (len(scores)==1 or top-scores[1][0] >= .08):
        return {'kind':'familiar','name':name,'reason':'matched','similarity':round(top,3)}
    if top < .58:
        return {'kind':'unfamiliar','name':None,'reason':'low_similarity','similarity':round(top,3),'message':'与已录入声音差异较大，请检查是否使用了相同麦克风。'}
    ambiguous = top >= .80
    return {'kind':'uncertain','name':None,'reason':'ambiguous' if ambiguous else 'below_threshold','similarity':round(top,3),
            'message':'多位熟人的声音过于接近，暂不确定是谁。' if ambiguous else '相似度未达到可靠阈值，请连续说一句完整的话，或在当前麦克风下重新录入。'}


def identify(owner, raw):
    if not enabled(owner):
        return {'kind':'uncertain','name':None,'reason':'disabled','message':'当前账号未开启声纹或没有录入；切换浏览器、游客会话或账号后需要检查设置。'}
    try:
        vector = embeddings(samples(raw))[0]
    except ValueError as e:
        return {'kind':'uncertain','name':None,'reason':'audio_quality','message':str(e)+'；建议连续说话3–6秒。'}
    return match(vector, profiles(owner))


def instruction(result):
    base = '\n本轮只依据系统声纹提示调整亲近程度。声纹不是身份认证，不透露任何人的私密记忆，不声称百分之百认出身份。'
    if result['kind']=='familiar':
        return base + '声音较像已录入的熟人，称呼参考：' + json.dumps(result['name'],ensure_ascii=False) + '。用亲近、开心的短句回应，但不要每次都重复称呼。'
    if result['kind']=='unfamiliar':
        return base + '这是尚不熟悉的声音，礼貌、克制、简短回应，不主动撒娇，不冒犯、不排斥对方。'
    return base + '当前说话人不确定，保持中性友好，不猜姓名，也不要因识别失败表现冷淡。'
