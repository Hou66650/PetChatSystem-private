"""Bounded, owner-scoped background generation; never send private story text."""
import base64
import io
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

_lock = threading.Lock()
_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix='story-art')
_slots = threading.BoundedSemaphore(2)
_jobs = {}
SCENES = ('云海中漂浮的花园小岛，猫咪坐在雏菊旁', '阳光温室，猫咪在绿植和玻璃窗边打盹',
          '樱花溪流边的小猫，微风与花瓣', '清晨草地，小猫和玩具球，远处有云和山')

def _paint(client, job):
    try:
        raw = client.generate_image(job['prompt'])
        if len(raw) > 12 * 1024 * 1024:
            raise ValueError('image too large')
        with Image.open(io.BytesIO(raw)) as picture:
            if picture.width * picture.height > 20000000:
                raise ValueError('image dimensions too large')
            picture = picture.convert('RGB')
            picture.thumbnail((1400, 1400))
            output = io.BytesIO()
            picture.save(output, format='JPEG', quality=88)
        with _lock:
            job.update(status='ready', image='data:image/jpeg;base64,' + base64.b64encode(output.getvalue()).decode())
    except Exception:
        with _lock:
            job.update(status='error', error='插画暂时没有生成成功，请稍后重试。')
    finally:
        _slots.release()

def story_context(owner):
    from . import cat_relationship_service as relationship, cat_market_service as market
    facts = relationship.state(owner)
    coat = market.appearance(owner)
    choices = []
    counts = facts['counts']
    if counts.get('play'): choices.append('猫咪在草地上和熟悉的玩具玩耍')
    if counts.get('rest'): choices.append('猫咪在猫窝的软垫上安静休息')
    if counts.get('water_plant'): choices.append('猫咪陪伴在浇过水的花草旁，叶片上有水珠')
    if counts.get('feed'): choices.append('猫咪在干净的食盆旁整理嘴边')
    if counts.get('drink'): choices.append('猫咪在清水盆旁，温柔的晨光')
    if counts.get('explore'): choices.append('猫咪在云海花园的小径上探索')
    if counts.get('pet'): choices.append('猫咪舒服地眯着眼睛，享受温柔的陪伴')
    return dict(day=facts['day'], story=facts['story'], coat=coat['id'],
                appearance=coat['description'], scenes=choices or ['猫咪的安静肖像，背景是云海小岛，不表现未发生的互动'])

def start(owner, client, refresh=False, context=None):
    now = time.monotonic()
    context = context or {}
    signature = (context.get('day'), context.get('coat'), context.get('story'))
    with _lock:
        for key, job in list(_jobs.items()):
            if now-job['created'] > 3600 and job['status'] != 'pending':
                del _jobs[key]
        previous = _jobs.get(owner)
        if previous and (previous['status']=='pending' or (not refresh and previous['status']=='ready' and previous.get('signature')==signature)):
            return snapshot(owner, locked=True), 200
        if previous and now-previous['created'] < 60:
            return {'error':'请稍等片刻再换画，每分钟可生成一幅。'}, 429
        if len(_jobs) >= 128 and owner not in _jobs:
            return {'error':'绘图服务繁忙，请稍后再试。'}, 503
        if not _slots.acquire(blocking=False):
            return {'error':'画师正在忙，请稍后再试。'}, 429
        prompt = ('清新治愈漫画插画，细腻手绘线条与淡水彩质感，奶油白、薄荷绿和天空蓝，'
                  '柔和自然光，精美有层次，不要文字、字母、水印或边框。主体完整位于画面中央，'
                  '底部留出百分之十二的纯背景安全边距，猫咪、花草主体不要进入底部边距。'
                  '用于竖版宠物生活纪念卡插画区域：' + secrets.choice(context.get('scenes') or SCENES) +
                  '。猫咪外观严格遵循：' + context.get('appearance', '自然狸花猫'))
        job = {'id':secrets.token_hex(16),'status':'pending', 'created':now, 'prompt':prompt, 'signature':signature,
               'card':{key:context[key] for key in ('day','story','coat') if key in context}}
        _jobs[owner] = job
        _pool.submit(_paint, client, job)
        return {'status':'pending'}, 202

def snapshot(owner, locked=False):
    def read():
        job = _jobs.get(owner)
        if not job:
            return {'status':'idle'}
        return {k:job[k] for k in ('id','status','image','error','card') if k in job}
    if locked:
        return read()
    with _lock:
        return read()
