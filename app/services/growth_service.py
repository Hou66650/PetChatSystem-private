"""Calendar growth and factual memories; existing pets opt in without being reset."""
import calendar
import json
import time
import uuid
from datetime import date, datetime, timedelta

from ..db import get_db
from . import diary_service as diary

PERSONALITIES = {'gentle':'温柔亲人', 'curious':'好奇活泼', 'careful':'谨慎安静'}
NODES = [(0,'初来小岛'),(7,'熟悉小窝'),(14,'慢慢安心'),(30,'相伴满月'),(60,'一起发现'),
         (90,'熟悉彼此'),(100,'相伴百天'),(180,'半年的陪伴'),(270,'珍藏日常'),(365,'相伴一周年')]
FIRSTS = {'visit':('meet','第一次在岛上见面'),'chat':('chat','第一次聊天'),
          'pet':('pet','第一次温柔抚摸'),'feed':('feed','第一次亲手喂食'),
          'game':('game','第一次一起玩游戏'),'explore':('explore','第一次完成探索'),
          'name':('name','第一次回应自己的名字')}
DEFAULT_PREFS = dict(autoPhoto=True, sound=True, ambient='off', footsteps=False, haptics=0)


def init_schema():
    get_db().executescript('''
    CREATE TABLE IF NOT EXISTS pet_growth_profiles(
      owner TEXT NOT NULL,pet INTEGER NOT NULL,mode TEXT NOT NULL,name TEXT NOT NULL,
      birthday TEXT NOT NULL,estimated INTEGER NOT NULL,adopted TEXT NOT NULL,
      personality TEXT NOT NULL,likes TEXT NOT NULL,breed TEXT NOT NULL,
      certificate TEXT NOT NULL,enrolled REAL NOT NULL,prefs TEXT NOT NULL,
      PRIMARY KEY(owner,pet));
    CREATE TABLE IF NOT EXISTS pet_growth_facts(
      owner TEXT NOT NULL,pet INTEGER NOT NULL,source TEXT NOT NULL,day TEXT NOT NULL,
      kind TEXT NOT NULL,detail TEXT NOT NULL,created REAL NOT NULL,
      PRIMARY KEY(owner,pet,source));
    CREATE INDEX IF NOT EXISTS growth_facts_day ON pet_growth_facts(owner,pet,day);
    CREATE TABLE IF NOT EXISTS pet_growth_memories(
      id INTEGER PRIMARY KEY AUTOINCREMENT,owner TEXT NOT NULL,pet INTEGER NOT NULL,
      key TEXT NOT NULL,title TEXT NOT NULL,story TEXT NOT NULL,day TEXT NOT NULL,
      created REAL NOT NULL,photo BLOB,UNIQUE(owner,pet,key));
    CREATE INDEX IF NOT EXISTS growth_memories_owner ON pet_growth_memories(owner,pet,id);
    ''')


def today(): return date.fromisoformat(diary.day())


def months_after(d, months):
    year, month = divmod(d.year*12+d.month-1+months,12)
    return date(year,month+1,min(d.day,calendar.monthrange(year,month+1)[1]))


def get(db, owner, pet):
    row=db.execute('SELECT * FROM pet_growth_profiles WHERE owner=? AND pet=?',(owner,pet)).fetchone()
    return dict(row) if row else None


def enabled(db, owner):
    r=db.execute('SELECT enabled FROM companion_owners WHERE owner=?',(owner,)).fetchone()
    return bool(r and r[0])


def remember(db,p,key,title,story,when=None):
    when=time.time() if when is None else when
    added=db.execute('INSERT OR IGNORE INTO pet_growth_memories(owner,pet,key,title,story,day,created) VALUES (?,?,?,?,?,?,?)',
                    (p['owner'],p['pet'],key,title,story,diary.day(when),when)).rowcount
    if added:
        diary.record(db,p['owner'],p['pet'],'growth:'+str(p['pet'])+':'+key,'event',story,when)
    return bool(added)


def validate(data, existing=None):
    if not isinstance(data,dict): raise ValueError('请填写成长资料')
    name=data.get('name');personality=data.get('personality');mode=data.get('mode')
    if not isinstance(name,str) or not 1<=len(name.strip())<=24: raise ValueError('名字需要 1–24 个字')
    if not isinstance(personality,str) or personality not in PERSONALITIES or mode not in ('adopt','real'): raise ValueError('请选择领养方式和性格')
    likes=data.get('likes','');breed=data.get('breed','')
    if not isinstance(likes,str) or len(likes)>160 or not isinstance(breed,str) or len(breed)>40: raise ValueError('喜好最多 160 字，品种最多 40 字')
    now=today()
    if mode=='adopt':
        birth=date.fromisoformat(existing['birthday']) if existing else months_after(now,-3)
        adopted=date.fromisoformat(existing['adopted']) if existing else now
        estimated=True
    else:
        try:
            birth=date.fromisoformat(data.get('birthday',''))
            adopted=date.fromisoformat(existing['adopted']) if existing else date.fromisoformat(data.get('adopted',''))
        except (ValueError,TypeError): raise ValueError('请填写有效的生日和相识日期')
        if birth>adopted or adopted>now or birth<months_after(now,-360): raise ValueError('生日不能晚于相识日期，日期不能在未来；支持最近 30 年')
        estimated=data.get('estimated',False)
        if type(estimated) is not bool: raise ValueError('请选择生日是否为估计')
    if existing and (mode!=existing['mode'] or personality!=existing['personality']):
        raise ValueError('领养方式和基础性格建立后保持不变，日常习惯会随经历成长')
    return dict(name=name.strip(),birthday=birth.isoformat(),adopted=adopted.isoformat(),estimated=int(estimated),
                personality=personality,mode=mode,likes=likes.strip(),breed=breed.strip())


def save(owner,pet,data,editing=False):
    db=get_db()
    with db:
        db.execute('BEGIN IMMEDIATE')
        if not enabled(db,owner): raise ValueError('请先在陪伴档案中开启记忆，再建立成长记录')
        p=get(db,owner,pet)
        if bool(p)!=editing: raise ValueError('成长资料已建立，请刷新页面编辑' if p else '请先建立成长资料')
        v=validate(data,p)
        if not p:
            db.execute('INSERT INTO pet_growth_profiles VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                       (owner,pet,v['mode'],v['name'],v['birthday'],v['estimated'],v['adopted'],v['personality'],v['likes'],v['breed'],uuid.uuid4().hex[:12].upper(),time.time(),json.dumps(DEFAULT_PREFS)))
            p=get(db,owner,pet)
        else:
            db.execute('UPDATE pet_growth_profiles SET name=?,birthday=?,estimated=?,likes=?,breed=? WHERE owner=? AND pet=?',
                       (v['name'],v['birthday'],v['estimated'],v['likes'],v['breed'],owner,pet))
        db.execute("DELETE FROM companion_memories WHERE owner=? AND pet_id=? AND category='pet_name'",(owner,pet))
        db.execute("INSERT INTO companion_memories(owner,pet_id,category,value,confirmed) VALUES (?,?,'pet_name',?,1)",(owner,pet,v['name']))
        if not editing:remember(db,p,'islander','获得岛民证','我有了自己的岛民证，名字叫'+v['name'])
    return state(owner,pet)


def appearance(p, now=None):
    now=now or today();birth=date.fromisoformat(p['birthday']);adopted=date.fromisoformat(p['adopted'])
    age=max(0,(now-birth).days);days=max(0,(now-adopted).days)
    phase='幼年' if now<months_after(birth,6) else '少年' if now<months_after(birth,12) else '成年'
    # One grounded rig, three size stages with gradual interpolation. No new mesh loading.
    scale=round(.72+.28*min(1,max(0,(age-90)/275)),4)
    index=max(i for i,(d,_) in enumerate(NODES) if now>=node_date(adopted,d))
    unlocks=['回应名字','温柔互动']
    if days>=7:unlocks.append('好奇观察')
    if days>=30:unlocks.append('开心问候')
    if days>=100:unlocks.append('亲密撒娇')
    return dict(ageDays=age,togetherDays=days,stage=phase,scale=scale,node=index+1,nodeName=NODES[index][1],
                unlocks=unlocks,voiceRate=round(1+(1-scale)*.4,3))


def node_date(adopted,days):
    return months_after(adopted,12) if days==365 else months_after(adopted,1) if days==30 else adopted+timedelta(days=days)


def anniversaries(db,p):
    if not enabled(db,p['owner']): return
    now=today();start=date.fromisoformat(diary.day(p['enrolled']));adopt=date.fromisoformat(p['adopted']);birth=date.fromisoformat(p['birthday'])
    due=[]
    for n,title in NODES[1:]:
        date_due=node_date(adopt,n)
        due.append(('node:'+str(n),title,date_due))
    for year in range(max(1,start.year-birth.year-1),now.year-birth.year+1):
        due.append(('birthday:'+str(year),str(year)+'岁生日',months_after(birth,12*year)))
    for year in range(max(2,start.year-adopt.year-1),now.year-adopt.year+1):
        due.append(('anniversary:'+str(year),'相伴'+str(year)+'周年',months_after(adopt,12*year)))
    for key,title,date_due in due:
        if start<=date_due<=now:
            stamp=datetime.combine(date_due,datetime.min.time(),tzinfo=diary.TZ).timestamp()+12*3600
            # Calendar events are dated correctly even when first read later; no invented activity.
            remember(db,p,key,title,'今天是我的'+title+'，这一页记下我们一起走过的日子',stamp)


def observe(db,owner,pet,source,kind,detail,now):
    if source.startswith('growth:'):return
    p=get(db,owner,pet)
    if not p or now<p['enrolled'] or not enabled(db,owner):return
    if kind not in ('visit','chat','interaction','explore','activity','event'):return
    if not db.execute('INSERT OR IGNORE INTO pet_growth_facts VALUES (?,?,?,?,?,?,?)',
                      (owner,pet,source,diary.day(now),kind,detail,now)).rowcount:return
    key=detail if kind=='interaction' else kind
    if key in FIRSTS:
        code,title=FIRSTS[key];remember(db,p,'first:'+code,title,'我记住了'+title+'的这一天',now)
    if kind=='activity' and detail in (diary.ACTIVITIES['jump'],diary.ACTIVITIES['sleep']):
        title='第一次完成跳跃' if detail==diary.ACTIVITIES['jump'] else '第一次回窝入睡'
        remember(db,p,'first:'+('jump' if detail==diary.ACTIVITIES['jump'] else 'sleep'),title,'今天，我'+detail,now)
    if source.startswith('journey:'):
        remember(db,p,'first:journey','第一次外出归来',detail,now)


def name_response(db,owner,pet,message):
    p=get(db,owner,pet)
    nickname=db.execute("SELECT value FROM companion_memories WHERE owner=? AND pet_id=? AND category='pet_name' ORDER BY updated_at DESC LIMIT 1",(owner,pet)).fetchone()
    if p and nickname and nickname['value']!=p['name']:
        p['name']=nickname['value']
        db.execute('UPDATE pet_growth_profiles SET name=? WHERE owner=? AND pet=?',(p['name'],owner,pet))
    if p and message.strip().startswith(p['name']) and enabled(db,owner):
        remember(db,p,'first:name',FIRSTS['name'][1],'主人叫了我的名字，我给出了自己的回应')


def traits(db,p):
    # Distinct active days, not spam volume. Inactivity never subtracts trust.
    rows=db.execute('''SELECT kind,detail,COUNT(DISTINCT day) AS days FROM pet_growth_facts WHERE owner=? AND pet=?
        AND day IN (SELECT DISTINCT day FROM pet_growth_facts WHERE owner=? AND pet=? ORDER BY day DESC LIMIT 30)
        GROUP BY kind,detail''',(p['owner'],p['pet'],p['owner'],p['pet'])).fetchall()
    contact=db.execute("SELECT COUNT(DISTINCT day) FROM pet_growth_facts WHERE owner=? AND pet=? AND kind IN ('chat','interaction')",(p['owner'],p['pet'])).fetchone()[0]
    places=sorted((r for r in rows if r['kind']=='explore'),key=lambda r:-r['days'])
    habits=[dict(label=('常去'+r['detail'] if r['kind']=='explore' else '常常'+r['detail']),days=r['days'])
            for r in rows if r['kind'] in ('explore','activity') and r['days']>=3][:8]
    habits += [dict(label={'pet':'习惯温柔抚摸','game':'喜欢一起玩游戏','feed':'熟悉亲手喂食','gaze':'习惯安静对视'}[r['detail']],days=r['days'])
               for r in rows if r['kind']=='interaction' and r['detail'] in ('pet','game','feed','gaze') and r['days']>=3]
    return dict(trustDays=contact,trust='初识' if contact<3 else '熟悉' if contact<10 else '信赖' if contact<30 else '亲密',
                habits=habits,favoritePlace=places[0]['detail'] if places and places[0]['days']>=3 else None,
                mood='等待新的互动',base=PERSONALITIES[p['personality']])


def state(owner,pet,limit=300):
    db=get_db();p=get(db,owner,pet)
    if not p:return dict(enrolled=False,petId=pet,nodes=NODES)
    with db:anniversaries(db,p)
    records=[dict(r) for r in db.execute('SELECT id,key,title,story,day,created,photo IS NOT NULL AS hasPhoto FROM pet_growth_memories WHERE owner=? AND pet=? ORDER BY day DESC,id DESC LIMIT ?',(owner,pet,limit))]
    for r in records:r['image']='/api/growth/'+str(pet)+'/memories/'+str(r['id'])+'/image'
    date_now=today()
    return dict(enrolled=True,petId=pet,profile={k:p[k] for k in ('mode','name','birthday','estimated','adopted','personality','likes','breed','certificate')},
                appearance=appearance(p),traits=traits(db,p),prefs=json.loads(p['prefs']),memories=records,nodes=NODES,
                onThisDay=[r for r in records if r['day'][:4]!=str(date_now.year) and r['day'][5:]==date_now.isoformat()[5:]],
                memoryEnabled=enabled(db,owner),serverTime=time.time())


def behavior(owner,pet,base):
    db=get_db();p=get(db,owner,pet)
    if not p or not enabled(db,owner):return base
    base=dict(base)
    if base.get('sourceIds'):return base # Explicit user preference takes precedence.
    trust=traits(db,p)['trustDays'];kind=p['personality']
    if kind=='careful':base.update(mode='calm',idleSeconds=[10 if trust<10 else 7,18],speedScale=.85,reaction='subtle')
    elif kind=='curious':base.update(mode='lively',idleSeconds=[3,7],speedScale=1.05,reaction='happy')
    else:base.update(mode='natural',idleSeconds=[5,10],speedScale=.95,reaction='natural')
    base['summary']='基础性格：'+PERSONALITIES[kind]+'；已在 '+str(trust)+' 个实际互动日积累信任'
    return base


def update_prefs(owner,pet,data):
    if not isinstance(data,dict) or set(data)-set(DEFAULT_PREFS):raise ValueError('设置不正确')
    for k,v in data.items():
        if k in ('autoPhoto','sound','footsteps') and type(v) is not bool:raise ValueError('开关值不正确')
        if k=='haptics' and (type(v) is not int or v not in (0,1,2,3)):raise ValueError('振动强度不正确')
        if k=='ambient' and v not in ('off','rain','insects'):raise ValueError('环境音不正确')
    db=get_db();p=get(db,owner,pet)
    if not p:raise ValueError('请先建立成长资料')
    prefs=json.loads(p['prefs']);prefs.update(data)
    with db:db.execute('UPDATE pet_growth_profiles SET prefs=? WHERE owner=? AND pet=?',(json.dumps(prefs),owner,pet))
    return prefs


def forget(db,owner):
    for table in ('pet_growth_profiles','pet_growth_facts','pet_growth_memories'):
        db.execute('DELETE FROM '+table+' WHERE owner=?',(owner,))


def context(owner,pet):
    db=get_db();p=get(db,owner,pet)
    if not p or not enabled(db,owner):return {}
    a=appearance(p);t=traits(db,p)
    return dict(name=p['name'],ageDays=a['ageDays'],stage=a['stage'],togetherDays=a['togetherDays'],
                basePersonality=t['base'],trust=t['trust'],ownerProvidedLikes=p['likes'],
                learnedHabits=t['habits'],favoritePlace=t['favoritePlace'])
