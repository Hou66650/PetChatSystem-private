"""Observed relationship facts. No chat, recordings, offline simulation or decay."""
import re,time,hashlib
from datetime import datetime,timezone,timedelta
from ..db import get_db
TZ=timezone(timedelta(hours=8))
KINDS={'visit','pet','play','feed','drink','rest','explore','water_plant','meal','sip'}
TOYS={'ball','disc','rope','bone','duck','brush','rattle'}
def init_schema():
 get_db().executescript('''CREATE TABLE IF NOT EXISTS cat_life_events(owner TEXT NOT NULL,event TEXT NOT NULL,kind TEXT NOT NULL,target TEXT NOT NULL,created REAL NOT NULL,day TEXT NOT NULL,hour INTEGER NOT NULL,PRIMARY KEY(owner,event));
 CREATE INDEX IF NOT EXISTS cat_life_owner_date ON cat_life_events(owner,day);''')
def state(owner):
 db=get_db();now=time.time();today=datetime.fromtimestamp(now,TZ).date().isoformat()
 rows=[dict(r) for r in db.execute('SELECT * FROM cat_life_events WHERE owner=? ORDER BY created DESC LIMIT 2000',(owner,))]
 interactions=[r for r in rows if r['kind'] in ('pet','play','feed','drink','water_plant')]
 days=len({r['day'] for r in interactions});score=min(1,len(interactions)/60)*min(1,days/7)
 toys={};places={};hours={}
 for r in rows:
  if r['kind']=='play':toys[r['target']]=toys.get(r['target'],0)+1
  if r['kind']=='explore' or (r['kind'] in ('pet','play') and r['target'] and r['target'] not in TOYS):places[r['target']]=places.get(r['target'],0)+(4 if r['kind']=='pet' else 1)
  if r['kind']=='visit':hours.setdefault(r['hour']//3,set()).add(r['day'])
 favorite=max(toys,key=toys.get) if toys else None
 preferred=max(places,key=places.get) if places else None
 regular=max(hours,key=lambda h:len(hours[h])) if hours else None
 regular=regular if regular is not None and len(hours[regular])>=3 else None
 daily=[r for r in rows if r['day']==today];counts={k:sum(r['kind']==k for r in daily) for k in KINDS}
 counts['feed']+=counts['meal'];counts['drink']+=counts['sip']
 labels={'pet':'接受了你的抚摸','play':'和你完成了玩具寻回','feed':'吃过饭','drink':'喝过水','rest':'在窝里休息','explore':'完成了岛上探索','water_plant':'一起照料了植物'}
 story='；'.join(f"{labels[k]} {counts[k]} 次" for k in labels if counts[k]) or '今天还没有记录到完成的互动，慢慢来就好。'
 seed=hashlib.sha256(('pait-cat:'+owner).encode()).digest()
 personality=dict(curiosity=round(.35+seed[0]/255*.5,2),sociability=round(.3+seed[1]/255*.5,2),liveliness=round(.3+seed[2]/255*.5,2))
 return dict(personality=personality,familiarity=round(score,3),days=days,favoriteToy=favorite,preferredPlace=preferred,regularWindow=regular,counts=counts,story=story,day=today,imprints=[s for s in [('它已经更愿意主动靠近你。' if score>=.35 else '它正在慢慢熟悉你的陪伴。'),('它开始有了喜欢一起玩的玩具。' if favorite and toys[favorite]>=3 else ''),('它记住了你经常出现的时间段。' if regular is not None else '')] if s])
def record(owner,data):
 kind=data.get('kind');event=data.get('event');target=data.get('target','')
 if not isinstance(kind,str) or kind not in KINDS or not isinstance(event,str) or not re.fullmatch(r'[\w-]{8,80}',event) or not isinstance(target,str) or len(target)>40:raise ValueError('互动记录格式错误')
 if kind=='play' and target not in TOYS:raise ValueError('玩具不存在')
 if kind!='play' and (target or kind=='explore'):
  from .cat_agent_service import TARGETS
  if target not in TARGETS:raise ValueError('地点不存在')
 db=get_db();now=time.time();date=datetime.fromtimestamp(now,TZ)
 db.execute('BEGIN IMMEDIATE')
 try:
  # Completed gestures may be emitted repeatedly; throttle credit across tabs.
  cooldown=1800 if kind=='visit' else 30 if kind in ('pet','play') else 10
  old=db.execute('SELECT created FROM cat_life_events WHERE owner=? AND kind=? ORDER BY created DESC LIMIT 1',(owner,kind)).fetchone()
  if not old or now-old['created']>=cooldown:
   db.execute('INSERT OR IGNORE INTO cat_life_events VALUES (?,?,?,?,?,?,?)',(owner,event,kind,target,now,date.date().isoformat(),date.hour))
  db.execute('DELETE FROM cat_life_events WHERE owner=? AND event NOT IN (SELECT event FROM cat_life_events WHERE owner=? ORDER BY created DESC LIMIT 2000)',(owner,owner));db.commit()
 except Exception:db.rollback();raise
 return state(owner)
def clear(owner):
 with get_db() as db:db.execute('DELETE FROM cat_life_events WHERE owner=?',(owner,))
 return state(owner)
