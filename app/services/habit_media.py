"""Bounded local decoding. Sparse observations never claim full motion capture."""
import array
import io
import math
from pathlib import Path
import subprocess
import tempfile
import threading
import wave

from PIL import Image, ImageDraw

LOCK = threading.BoundedSemaphore(1)
WINDOW = 8.0
FPS = 3
RATE = 24000


def audio_signature(raw):
    return (raw[:4] in (b'RIFF', b'fLaC', b'OggS') or raw[:3] == b'ID3'
            or len(raw) > 1 and raw[0] == 255 and raw[1] & 0xe0 == 0xe0)


def ffmpeg(args, timeout=30):
    import imageio_ffmpeg
    result = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-nostdin', '-hide_banner', '-loglevel', 'error',
        '-protocol_whitelist', 'file,pipe', '-format_whitelist', 'mov,mp3,wav,ogg,matroska,webm,flac,aac',
        '-threads', '1', *args], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        timeout=timeout, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode:
        raise ValueError('素材解码失败，请换用可正常播放的文件')
    return result.stdout


def pcm(raw, start=0, duration=121):
    with tempfile.TemporaryDirectory(prefix='pait-habit-audio-') as folder:
        src = Path(folder)/'input'; src.write_bytes(raw)
        return ffmpeg(['-ss', str(start), '-i', str(src), '-t', str(duration), '-map', '0:a:0',
                       '-vn', '-sn', '-dn', '-ac', '1', '-ar', str(RATE), '-f', 's16le', 'pipe:1'])


def wav(data):
    out = io.BytesIO()
    with wave.open(out, 'wb') as writer:
        writer.setparams((1, 2, RATE, 0, 'NONE', 'not compressed')); writer.writeframes(data)
    return out.getvalue()


def decode_audio(raw):
    if not LOCK.acquire(blocking=False):
        raise ValueError('另一份素材正在解码，请稍后重试')
    try:
        data = pcm(raw); duration = len(data)/(2*RATE)
        if not .3 <= duration <= 120:
            raise ValueError('音频限 0.3–120 秒')
        picture = Image.new('RGB', (960, 160), '#e8eee4'); draw = ImageDraw.Draw(picture)
        samples = array.array('h', data)
        for x in range(960):
            chunk = samples[x*len(samples)//960:(x+1)*len(samples)//960]
            height = min(70, math.sqrt(sum(s*s for s in chunk)/max(1,len(chunk)))/32768*180)
            draw.line((x,80-height,x,80+height), fill='#426d62')
        preview = io.BytesIO(); picture.save(preview, 'JPEG')
        return 'audio/wav', wav(data), preview.getvalue(), [0], duration
    finally:
        LOCK.release()


def window(raw, start, duration):
    """24 ordered frames per 8-second window, with original-media timestamps."""
    with tempfile.TemporaryDirectory(prefix='pait-habit-video-') as folder:
        src = Path(folder)/'input'; src.write_bytes(raw)
        ffmpeg(['-ss', str(start), '-i', str(src), '-t', str(duration), '-map', '0:v:0', '-an', '-sn', '-dn',
                '-vf', 'fps=3,scale=256:144:force_original_aspect_ratio=decrease', '-frames:v', '24',
                '-threads', '1', str(Path(folder)/'%03d.jpg')])
        files = sorted(Path(folder).glob('*.jpg'))
        if not files:
            raise ValueError('这个片段没有可读取的画面')
        sheet = Image.new('RGB', (1024, math.ceil(len(files)/4)*170), '#f4f1e8')
        draw = ImageDraw.Draw(sheet); times = []
        for index, path in enumerate(files):
            timestamp = round(start+index/FPS, 3); times.append(timestamp)
            with Image.open(path) as image:
                x, y = index%4*256, index//4*170
                sheet.paste(image, (x, y)); draw.text((x+4,y+146), f'{index+1} / {timestamp:.2f}s', fill='black')
        out = io.BytesIO(); sheet.save(out, 'JPEG', quality=90)
        return out.getvalue(), times


def sound_segments(raw, start, duration):
    """Energy candidates ONLY. Owner must identify animal, meaning and context."""
    data = pcm(raw, start, duration); samples = array.array('h', data); stride = RATE//10
    levels = [math.sqrt(sum(v*v for v in samples[i:i+stride])/max(1,len(samples[i:i+stride])))
              for i in range(0,len(samples),stride)]
    if not levels or max(levels) < 200:
        return []
    noise = sorted(levels)[len(levels)//5]; threshold = max(300, noise*2.5)
    chunks = []; begin = None
    for i, level in enumerate(levels+[0]*4):
        if level > threshold:
            if begin is None: begin = max(0, i-1)
            last = i
        elif begin is not None and i-last >= 3:
            end = min(duration, (last+2)/10)
            if end-begin/10 >= .2:
                chunks.append((round(start+begin/10,3),round(start+min(end,begin/10+6),3)))
            begin = None
    return chunks[:4]
