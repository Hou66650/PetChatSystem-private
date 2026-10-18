"""Private, original animal audio clips. No voice cloning or invented vocalizations."""
import array
import io
import math
import subprocess
import tempfile
import threading
import time
import uuid
import wave
from pathlib import Path

from ..db import get_db

SLOTS = threading.BoundedSemaphore(1)
RATE = 24000
MAX_UPLOAD = 64 * 1024 * 1024
KINDS = ('greeting', 'comfort', 'play')


class CallError(ValueError):
    pass


def init_schema():
    get_db().executescript('''
    CREATE TABLE IF NOT EXISTS pet_call_sources(id TEXT PRIMARY KEY,owner TEXT NOT NULL,pet_id INTEGER NOT NULL,audio BLOB NOT NULL,duration REAL NOT NULL,created REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS pet_calls(id TEXT PRIMARY KEY,owner TEXT NOT NULL,pet_id INTEGER NOT NULL,name TEXT NOT NULL,kind TEXT NOT NULL,audio BLOB NOT NULL,duration REAL NOT NULL,created REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS pet_call_settings(owner TEXT NOT NULL,pet_id INTEGER NOT NULL,enabled INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(owner,pet_id));
    ''')


def wav_bytes(pcm):
    out = io.BytesIO()
    with wave.open(out, 'wb') as writer:
        writer.setparams((1, 2, RATE, 0, 'NONE', 'not compressed')); writer.writeframes(pcm)
    return out.getvalue()


def decode(raw):
    if not raw or len(raw) > MAX_UPLOAD: raise CallError('请选择不超过 64MB 的音频或视频')
    if not SLOTS.acquire(blocking=False): raise CallError('正在处理另一段声音，请稍后再试')
    try:
        import imageio_ffmpeg
        with tempfile.TemporaryDirectory(prefix='pait-pet-call-') as folder:
            src = Path(folder) / 'input'; out = Path(folder) / 'audio.pcm'; src.write_bytes(raw)
            # Only local, self-contained media. Do not allow uploaded playlists to
            # fetch network URLs; no shell, scripts, subtitles or video decoding.
            result = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-nostdin', '-hide_banner', '-loglevel', 'error',
                '-protocol_whitelist', 'file,pipe', '-format_whitelist', 'mov,mp3,wav,ogg,matroska,webm,flac,aac', '-threads', '1', '-i', str(src), '-t', '121', '-vn', '-sn', '-dn',
                '-ac', '1', '-ar', str(RATE), '-f', 's16le', '-y', str(out)],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                timeout=40, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if result.returncode or not out.exists(): raise CallError('没有找到可读取的音轨，请换一段带声音的 MP4、MOV、WAV 或 MP3')
            pcm = out.read_bytes(); duration = len(pcm) / (RATE * 2)
            if not .3 <= duration <= 120: raise CallError('请截取 0.3–120 秒、含宠物叫声的片段后上传')
            return pcm, duration
    except ImportError: raise CallError('本机音频提取组件尚未安装，请安装 requirements.txt 中的 imageio-ffmpeg')
    except subprocess.TimeoutExpired: raise CallError('音频处理超时，请换一段更短的视频')
    finally: SLOTS.release()


def candidates(pcm):
    samples = array.array('h', pcm); step = RATE // 10
    levels = [math.sqrt(sum(x*x for x in samples[i:i+step]) / max(1, len(samples[i:i+step]))) for i in range(0, len(samples), step)]
    if not levels or max(levels) < 80: return []
    threshold = max(150, max(levels) * .12)
    spans = []; start = None; last = None
    for i, level in enumerate(levels):
        if level >= threshold:
            if start is None: start = i
            last = i
        elif start is not None and i-last >= 4:
            spans.append((max(0, start*.1-.15), min(len(samples)/RATE, (last+1)*.1+.2))); start = None
    if start is not None: spans.append((max(0,start*.1-.15),len(samples)/RATE))
    return [dict(start=round(a,2),end=round(min(b,a+12),2)) for a,b in spans[:8] if b-a>=.2]


def source(owner, pet_id, raw):
    pcm, duration = decode(raw); source_id = uuid.uuid4().hex; db = get_db()
    with db:
        db.execute('DELETE FROM pet_call_sources WHERE owner=? AND created<?', (owner,time.time()-86400))
        # Two editable sources per account, independent of public model assets.
        old = db.execute('SELECT id FROM pet_call_sources WHERE owner=? ORDER BY created DESC', (owner,)).fetchall()
        for row in old[1:]: db.execute('DELETE FROM pet_call_sources WHERE id=?', (row['id'],))
        db.execute('INSERT INTO pet_call_sources VALUES (?,?,?,?,?,?)', (source_id,owner,pet_id,wav_bytes(pcm),duration,time.time()))
    return dict(id=source_id,duration=duration,candidates=candidates(pcm),note='推荐片段仅按声音强弱定位，可能包含人声或音乐；请试听确认它确实是你的宠物。')


def get_audio(owner, item_id, source=False):
    table = 'pet_call_sources' if source else 'pet_calls'
    row = get_db().execute('SELECT * FROM '+table+' WHERE owner=? AND id=?', (owner,item_id)).fetchone()
    if not row or source and row['created'] < time.time()-86400: raise CallError('这段声音不存在或临时素材已过期')
    return row


def save(owner, pet_id, data):
    if not isinstance(data,dict) or data.get('confirmed') is not True: raise CallError('请试听并确认这是宠物本来的叫声')
    if data.get('kind') not in KINDS: raise CallError('请选择欢迎、陪伴或玩耍场景')
    row = get_audio(owner, str(data.get('sourceId','')), True)
    if row['pet_id'] != pet_id: raise CallError('素材不属于当前宠物')
    name = data.get('name') or '熟悉的叫声'
    if not isinstance(name,str) or not 1 <= len(name.strip()) <= 32: raise CallError('声音名称限 32 字')
    try:
        start,end=float(data['start']),float(data['end'])
        if not 0 <= start < end <= row['duration'] or not .2 <= end-start <= 12: raise ValueError()
    except (KeyError, TypeError, ValueError, OverflowError): raise CallError('请选择素材中 0.2–12 秒的叫声片段')
    with wave.open(io.BytesIO(row['audio']),'rb') as wav:
        wav.setpos(int(start*RATE));pcm=wav.readframes(int((end-start)*RATE))
    samples = array.array('h',pcm)
    if not samples or math.sqrt(sum(x*x for x in samples)/len(samples)) < 50: raise CallError('这段片段几乎无声，请重新选择')
    # Preserve pitch/timbre; trim with a short fade to prevent clicks, never turn
    # a meow into synthetic speech or aggressively amplify background noise.
    fade=min(240,len(samples)//4)
    for i in range(fade): samples[i]=int(samples[i]*i/fade);samples[-i-1]=int(samples[-i-1]*i/fade)
    db=get_db();item_id=uuid.uuid4().hex
    with db:
        db.execute('BEGIN IMMEDIATE')
        if db.execute('SELECT count(*) FROM pet_calls WHERE owner=? AND pet_id=?',(owner,pet_id)).fetchone()[0]>=8: raise CallError('每只宠物最多保留 8 段叫声，请先删除不用的片段')
        db.execute('INSERT INTO pet_calls VALUES (?,?,?,?,?,?,?,?)',(item_id,owner,pet_id,name.strip(),data['kind'],wav_bytes(samples.tobytes()),end-start,time.time()))
    return item_id


def state(owner, pet_id):
    db=get_db();row=db.execute('SELECT enabled FROM pet_call_settings WHERE owner=? AND pet_id=?',(owner,pet_id)).fetchone()
    clips=[dict(r) for r in db.execute('SELECT id,name,kind,duration FROM pet_calls WHERE owner=? AND pet_id=? ORDER BY created DESC',(owner,pet_id))]
    sources=[dict(r) for r in db.execute('SELECT id,duration,created FROM pet_call_sources WHERE owner=? AND pet_id=? AND created>? ORDER BY created DESC',(owner,pet_id,time.time()-86400))]
    return dict(enabled=bool(row and row['enabled']),clips=clips,sources=sources)
