"""Owner-authorized journeys. The database, not a browser tab, owns travel state."""
import hashlib
import json
import math
import secrets
import time
from flask import current_app
from ..db import get_db

PETS = {
 '1':dict(name='柴犬',model='/static/models/petchat-shiba-v4/qiuqiu.glb',stage='/static/models/petchat-sakura-grand-v1/sakura.glb',theme='sakura',height=.95),
 '2':dict(name='哈士奇',model='/static/models/petchat-husky-v3/xueqiu.glb',stage='/static/models/petchat-toys-v1/snow.glb',theme='snow',height=1.05),
 '3':dict(name='猫咪',model='/static/models/petchat-cat-v3/cat.glb',stage='/static/models/petchat-meadow-v1/mistwood-meadow.glb',theme='room',height=.85),
 '4':dict(name='德牧',model='/static/models/petchat-shepherd-v2/shepherd.glb',stage='/static/models/petchat-shepherd-v1/alpine.glb',theme='camp',height=1.12),
}
EVENTS={'icon':'拜访桌面图标','walk':'散步','rest':'休息','pet':'被摸摸','sniff':'互相嗅闻','chase':'追逐','cursor':'蹭光标','document':'陪伴文档工作','video':'在播放器旁休息','paw':'扒了扒门','decline':'主人暂时不出发'}
LIVE="('pairing','active')"

class PortalError(ValueError):
    def __init__(self,message,status=400):super().__init__(message);self.status=status

def init_schema():
    get_db().executescript('''
    CREATE TABLE IF NOT EXISTS portal_islands(id TEXT PRIMARY KEY,owner TEXT NOT NULL,pet TEXT NOT NULL,allow_visitors INTEGER NOT NULL DEFAULT 0,memorial INTEGER NOT NULL DEFAULT 0,UNIQUE(owner,pet));
    CREATE TABLE IF NOT EXISTS portal_invites(owner TEXT PRIMARY KEY,code TEXT UNIQUE NOT NULL);
    CREATE TABLE IF NOT EXISTS portal_friends(owner TEXT NOT NULL,friend TEXT NOT NULL,PRIMARY KEY(owner,friend));
    CREATE TABLE IF NOT EXISTS portal_trips(id TEXT PRIMARY KEY,owner TEXT NOT NULL,pet TEXT NOT NULL,kind TEXT NOT NULL,destination TEXT,status TEXT NOT NULL,created REAL NOT NULL,updated REAL NOT NULL,ended REAL,reason TEXT NOT NULL DEFAULT '',pair_hash TEXT,token_hash TEXT,snapshot TEXT NOT NULL DEFAULT '{}');
    CREATE UNIQUE INDEX IF NOT EXISTS portal_one_world ON portal_trips(owner,pet) WHERE status IN ('pairing','active');
    CREATE UNIQUE INDEX IF NOT EXISTS portal_pair_code ON portal_trips(pair_hash) WHERE pair_hash IS NOT NULL;
    CREATE TABLE IF NOT EXISTS portal_events(id INTEGER PRIMARY KEY AUTOINCREMENT,trip TEXT NOT NULL,event_key TEXT NOT NULL,kind TEXT NOT NULL,x REAL,z REAL,created REAL NOT NULL,UNIQUE(trip,event_key));
    CREATE TABLE IF NOT EXISTS portal_messages(id INTEGER PRIMARY KEY AUTOINCREMENT,trip TEXT NOT NULL,owner TEXT NOT NULL,text TEXT NOT NULL,created REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS portal_rewards(trip TEXT PRIMARY KEY,owner TEXT NOT NULL,pet TEXT NOT NULL,item TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS portal_custom_pets(id TEXT PRIMARY KEY,owner TEXT NOT NULL,name TEXT NOT NULL,model TEXT NOT NULL,height REAL NOT NULL,memorial INTEGER NOT NULL DEFAULT 1);
    ''')

def digest(value):return hashlib.sha256(value.encode()).hexdigest()

def public_user_id(owner):
    return owner[5:] if owner.startswith('user:') else None


def pet_spec(owner,pet):
    if pet in PETS:
        spec=dict(PETS[pet],id=pet)
        if pet=='3':
            from .cat_market_service import appearance
            coat=appearance(owner);spec.update(model=coat['model'],coat=coat['id'],coatName=coat['name'])
            from .pet_generation_service import appearance as private_appearance
            private=private_appearance(owner)
            if private:spec.update(model=private['model'],name=private['name'],custom=True,task=private['task'],height=.85)
        return spec
    row=get_db().execute('SELECT * FROM portal_custom_pets WHERE id=? AND owner=?',(pet,owner)).fetchone()
    if not row:raise PortalError('宠物不存在或不属于你',404)
    return dict(id=pet,name=row['name'],model=row['model'],height=row['height'],theme='room',stage=PETS['3']['stage'])

def travel_spec(owner,pet,trip,role):
    spec=pet_spec(owner,pet)
    if spec.get('custom'):
        spec['model']='/api/portals/trip/'+trip+'/model/'+role
        spec.pop('task',None)
    return spec


def travel_model(t,role):
    """Only the animated asset, only while this authorized journey is active."""
    if t['status']!='active':raise PortalError('行程已结束，模型访问已关闭',409)
    if role=='visitor':owner,pet=t['owner'],t['pet']
    elif role=='host' and t['kind']=='neighbor':
        host=get_db().execute('SELECT owner,pet,allow_visitors FROM portal_islands WHERE id=?',(t['destination'],)).fetchone()
        if not host or not host['allow_visitors']:raise PortalError('对方已关闭访问',403)
        owner,pet=host['owner'],host['pet']
    else:raise PortalError('模型角色不存在',404)
    spec=pet_spec(owner,pet)
    if not spec.get('custom'):raise PortalError('私人模型已不可用，请结束行程后重试',404)
    row=get_db().execute("SELECT data FROM pet_studio_assets WHERE task=? AND slot='adapted'",(spec['task'],)).fetchone()
    if not row:raise PortalError('模型不存在',404)
    return row['data']


def register_custom_pet(owner,pet,name,model,height=.85,memorial=True):
    """Server-side integration hook for a future validated photo-to-GLB pipeline."""
    if not pet.startswith('custom-') or not model.startswith('/static/models/custom/') or '..' in model or not model.endswith('.glb') or not .2<=height<=2:
        raise PortalError('自建宠物资产未通过校验')
    db=get_db()
    with db:
        db.execute('INSERT INTO portal_custom_pets VALUES (?,?,?,?,?,?)',(pet,owner,name[:40],model,height,int(memorial)))
        db.execute('INSERT INTO portal_islands VALUES (?,?,?,0,?)',(secrets.token_hex(12),owner,pet,int(memorial)))

def ensure(owner):
    db=get_db()
    with db:
        for pet in PETS:db.execute('INSERT OR IGNORE INTO portal_islands(id,owner,pet) VALUES (?,?,?)',(secrets.token_hex(12),owner,pet))

def finish(trip,reason='主人召回'):
    db=get_db();now=time.time()
    changed=db.execute("UPDATE portal_trips SET status='returned',ended=?,updated=?,reason=?,pair_hash=NULL,token_hash=NULL WHERE id=? AND status IN ('pairing','active')",(now,now,reason,trip['id'])).rowcount
    if changed and trip['status']=='active' and str(trip['pet']) in PETS:
        from . import diary_service
        diary_service.record(db,trip['owner'],int(trip['pet']),'journey:'+trip['id'],'event',
                             '我结束了'+('电脑桌面的探险' if trip['kind']=='desktop' else '去友邻小岛的串门')+'，回到了自己的小窝')
    if changed and trip['status']=='active' and db.execute("SELECT 1 FROM portal_events WHERE trip=? AND kind!='position' LIMIT 1",(trip['id'],)).fetchone():
        item='迷你键帽' if trip['kind']=='desktop' else '友邻植物种子'
        db.execute('INSERT OR IGNORE INTO portal_rewards VALUES (?,?,?,?)',(trip['id'],trip['owner'],trip['pet'],item))
        from .cat_market_service import reward
        reward(trip['owner'],'journey',trip['id'])

def expire():
    db=get_db();now=time.time()
    with db:
        for t in db.execute("SELECT * FROM portal_trips WHERE status IN ('pairing','active')").fetchall():
            if t['status']=='pairing' and now-t['created']>120:finish(t,'配对超时，未出发')
            elif t['status']=='active' and now-t['updated']>45:finish(t,'连接中断，已安全返回')
            elif t['status']=='active' and now-t['created']>(1800 if t['kind']=='desktop' else 600):finish(t,'精力不足，自主返程')

def trip_for(owner,trip_id,visitor_only=False):
    t=get_db().execute('SELECT * FROM portal_trips WHERE id=?',(trip_id,)).fetchone()
    if not t:raise PortalError('行程不存在',404)
    host=get_db().execute('SELECT owner FROM portal_islands WHERE id=?',(t['destination'],)).fetchone()
    if t['owner']!=owner and (visitor_only or not host or host['owner']!=owner):raise PortalError('无权查看此行程',404)
    return t

def public_trip(t,owner,brief=False):
    db=get_db();events=[] if brief else [dict(e) for e in db.execute('SELECT kind,x,z,created FROM portal_events WHERE trip=? ORDER BY id DESC LIMIT 2400',(t['id'],))][::-1]
    messages=[] if brief else [dict(m) for m in db.execute('SELECT text,created,owner=? AS mine FROM portal_messages WHERE trip=? ORDER BY id DESC LIMIT 30',(owner,t['id']))][::-1]
    result={k:t[k] for k in ('id','pet','kind','destination','status','created','updated','ended','reason')}
    counts={key:sum(e['kind']==key for e in events) for key in EVENTS}
    summary='、'.join(EVENTS[k]+str(n)+'次' for k,n in counts.items() if n)
    result.update(visitorId=public_user_id(t['owner']),petSpec=travel_spec(t['owner'],t['pet'],t['id'],'visitor'),mine=t['owner']==owner,events=events,messages=messages,snapshot=json.loads(t['snapshot']),story=('桌面探险' if t['kind']=='desktop' else '友邻串门')+'：'+(summary or '尚无互动记录')+('。'+t['reason'] if t['ended'] else '。等待桌面配对，尚未出发' if t['status']=='pairing' else '。正在旅途中'))
    if t['destination']:
        host=db.execute('SELECT * FROM portal_islands WHERE id=?',(t['destination'],)).fetchone()
        result['hostPet']=travel_spec(host['owner'],host['pet'],t['id'],'host')
        result['hostId']=public_user_id(host['owner'])
    return result

def state(owner,brief=False):
    ensure(owner);expire();db=get_db()
    own=[dict(i) for i in db.execute('SELECT id,pet,allow_visitors,memorial FROM portal_islands WHERE owner=?',(owner,))]
    for i in own:i['petSpec']=pet_spec(owner,i['pet'])
    friends=[]
    for row in db.execute('SELECT i.* FROM portal_islands i JOIN portal_friends f ON f.friend=i.owner WHERE f.owner=?',(owner,)):
        friends.append(dict(id=row['id'],userId=public_user_id(row['owner']),petSpec=pet_spec(row['owner'],row['pet']),allow=bool(row['allow_visitors']),memorial=bool(row['memorial'])))
    trips=db.execute("SELECT t.* FROM portal_trips t LEFT JOIN portal_islands i ON i.id=t.destination WHERE t.owner=? OR i.owner=? ORDER BY (t.status IN ('pairing','active')) DESC,t.created DESC LIMIT 30",(owner,owner)).fetchall()
    code=db.execute('SELECT code FROM portal_invites WHERE owner=?',(owner,)).fetchone()
    return dict(userId=public_user_id(owner),islands=own,friends=friends,trips=[public_trip(t,owner,brief) for t in trips],invite=code['code'] if code else None,guest=not owner.startswith('user:'),rewards=[dict(r) for r in db.execute('SELECT trip,pet,item FROM portal_rewards WHERE owner=?',(owner,))])

def operate(owner,op,data):
    ensure(owner);expire();db=get_db()
    if op=='invite':
        if not owner.startswith('user:'):raise PortalError('请登录后添加好友',403)
        code=secrets.token_urlsafe(18)
        with db:db.execute('INSERT INTO portal_invites VALUES (?,?) ON CONFLICT(owner) DO UPDATE SET code=excluded.code',(owner,code))
        return dict(code=code)
    if op=='friend':
        if not owner.startswith('user:'):raise PortalError('请登录后添加好友',403)
        row=db.execute('SELECT owner FROM portal_invites WHERE code=?',(str(data.get('code',''))[:80],)).fetchone()
        if not row or row['owner']==owner:raise PortalError('邀请码无效')
        with db:
            for a,b in [(owner,row['owner']),(row['owner'],owner)]:db.execute('INSERT OR IGNORE INTO portal_friends VALUES (?,?)',(a,b))
        return dict(ok=True)
    if op=='settings':
        pet=str(data.get('pet',''));pet_spec(owner,pet)
        if type(data.get('allow')) is not bool:raise PortalError('访客开关格式错误')
        db.execute('BEGIN IMMEDIATE')
        try:
            db.execute('UPDATE portal_islands SET allow_visitors=? WHERE owner=? AND pet=?',(int(data['allow']),owner,pet))
            if not data['allow']:
                for t in db.execute("SELECT t.* FROM portal_trips t JOIN portal_islands i ON i.id=t.destination WHERE i.owner=? AND i.pet=? AND t.status='active'",(owner,pet)).fetchall():finish(t,'好友关闭访客权限，已返程')
            db.commit()
        except Exception:db.rollback();raise
        return dict(ok=True)
    if op=='depart':
        pet=str(data.get('pet',''));pet_spec(owner,pet);kind=data.get('kind')
        if kind not in ('desktop','neighbor') or data.get('confirmed') is not True:raise PortalError('必须由主人确认目的地')
        dest=data.get('destination') if kind=='neighbor' else None
        if kind=='neighbor' and (not isinstance(dest,str) or len(dest)>64):raise PortalError('请选择有效好友岛屿')
        db.execute('BEGIN IMMEDIATE')
        try:
            if db.execute("SELECT 1 FROM portal_trips WHERE owner=? AND pet=? AND status IN ('pairing','active')",(owner,pet)).fetchone():raise PortalError('这只宠物已在旅途中，请先召回',409)
            if db.execute("SELECT 1 FROM portal_trips t JOIN portal_islands i ON i.id=t.destination WHERE i.owner=? AND i.pet=? AND t.status='active'",(owner,pet)).fetchone():raise PortalError('请先结束正在接待的串门',409)
            if kind=='neighbor':
                if not owner.startswith('user:'):raise PortalError('串门需要登录',403)
                island=db.execute('SELECT * FROM portal_islands WHERE id=?',(dest,)).fetchone()
                if not island or not island['allow_visitors'] or not db.execute('SELECT 1 FROM portal_friends WHERE owner=? AND friend=?',(owner,island['owner'])).fetchone():raise PortalError('对方未允许好友访问',403)
                if db.execute("SELECT 1 FROM portal_trips WHERE status='active' AND destination=?",(dest,)).fetchone():raise PortalError('好友正在接待访客，请稍后再来',409)
                if db.execute("SELECT 1 FROM portal_trips WHERE owner=? AND pet=? AND status IN ('pairing','active')",(island['owner'],island['pet'])).fetchone():raise PortalError('好友宠物正在外出',409)
            elif db.execute("SELECT 1 FROM portal_trips t JOIN portal_islands i ON i.id=t.destination WHERE i.owner=? AND i.pet=? AND t.status='active'",(owner,pet)).fetchone():raise PortalError('请先结束正在接待的串门',409)
            code=secrets.token_urlsafe(24) if kind=='desktop' else None;tid=secrets.token_hex(16);now=time.time()
            db.execute('INSERT INTO portal_trips(id,owner,pet,kind,destination,status,created,updated,pair_hash) VALUES (?,?,?,?,?,?,?,?,?)',(tid,owner,pet,kind,dest,'pairing' if code else 'active',now,now,digest(code) if code else None))
            db.commit();return dict(trip=tid,code=code)
        except Exception:db.rollback();raise
    t=trip_for(owner,str(data.get('trip','')),visitor_only=op in ('sample','plan'))
    if op=='return':
        with db:finish(t,'主人召回' if t['owner']==owner else '好友结束接待')
        return dict(ok=True)
    if op=='message':
        message=data.get('text')
        if t['status']!='active' or not isinstance(message,str) or not 1<=len(message.strip())<=120:raise PortalError('请输入 1–120 字的留言，且行程仍在进行')
        if db.execute('SELECT 1 FROM portal_messages WHERE trip=? AND owner=? AND created>?',(t['id'],owner,time.time()-2)).fetchone():raise PortalError('留言太快，请稍候',429)
        with db:db.execute('INSERT INTO portal_messages(trip,owner,text,created) VALUES (?,?,?,?)',(t['id'],owner,message.strip(),time.time()))
        return dict(ok=True)
    if op=='plan':return plan(t)
    if op=='sample':
        if t['kind']!='neighbor':raise PortalError('桌面轨迹必须由配对客户端上报',403)
        return sample(t,data)
    raise PortalError('未知操作',404)

def sample(t,data):
    if t['status']!='active':raise PortalError('行程已结束',409)
    snapshot=data.get('snapshot',{})
    if not isinstance(snapshot,dict):raise PortalError('状态格式错误')
    clean={}
    for who in ('visitor','host'):
        p=snapshot.get(who)
        if p is None:continue
        if not isinstance(p,dict):raise PortalError('坐标格式错误')
        vals=[p.get(k,0) for k in ('x','z','yaw')]
        if any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>100 for v in vals):raise PortalError('坐标越界')
        action=p.get('action','idle')
        if action not in ('idle','walk','run','sniff','sleep','petting','happy'):raise PortalError('动作无效')
        clean[who]=dict(zip(('x','z','yaw'),vals),action=action)
    events=data.get('events',[])
    if not isinstance(events,list) or len(events)>12:raise PortalError('事件过多')
    rows=[]
    for e in events:
        if not isinstance(e,dict) or e.get('kind') not in (*EVENTS,'position') or not isinstance(e.get('id'),str) or not 8<=len(e['id'])<=80:raise PortalError('事件无效')
        x,z=e.get('x'),e.get('z')
        if any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>100 for v in (x,z)):raise PortalError('轨迹越界')
        rows.append((t['id'],e['id'],e['kind'],x,z,time.time()))
    db=get_db()
    with db:
        changed=db.execute("UPDATE portal_trips SET updated=?,snapshot=? WHERE id=? AND status='active'",(time.time(),json.dumps(clean),t['id'])).rowcount
        if not changed:raise PortalError('行程已结束',409)
        db.executemany('INSERT OR IGNORE INTO portal_events(trip,event_key,kind,x,z,created) VALUES (?,?,?,?,?,?)',rows)
        db.execute('DELETE FROM portal_events WHERE trip=? AND id NOT IN (SELECT id FROM portal_events WHERE trip=? ORDER BY id DESC LIMIT 2400)',(t['id'],t['id']))
    return dict(ok=True)

def pair(code):
    expire();db=get_db();token=secrets.token_urlsafe(32);db.execute('BEGIN IMMEDIATE')
    try:
        t=db.execute("SELECT * FROM portal_trips WHERE pair_hash=? AND status='pairing'",(digest(code),)).fetchone()
        if not t:raise PortalError('配对码无效、过期或已经使用',403)
        db.execute("UPDATE portal_trips SET status='active',pair_hash=NULL,token_hash=?,updated=? WHERE id=?",(digest(token),time.time(),t['id']));db.commit()
        spec=pet_spec(t['owner'],t['pet'])
        if spec.get('custom'):spec['model']='/api/portals/desktop/model'
        return dict(token=token,trip=t['id'],pet=spec)
    except Exception:db.rollback();raise

def desktop_trip(token):
    expire();t=get_db().execute("SELECT * FROM portal_trips WHERE token_hash=? AND kind='desktop' AND status='active'",(digest(token),)).fetchone()
    if not t:raise PortalError('桌面行程已结束，请返回小岛',409)
    return t


def desktop(token,op,data):
    t=desktop_trip(token)
    if op=='state':return public_trip(t,t['owner'],True)
    if op=='plan':return plan(t)
    if op=='sample':return sample(t,data)
    if op=='return':
        with get_db():finish(t,'从桌面返回温室')
        return dict(ok=True)
    raise PortalError('未知操作',404)


def plan(t):
    """Shared bounded model gate; local simulation continues while planning."""
    if t['status']!='active':raise PortalError('行程已结束',409)
    allowed=['walk','rest','cursor'] if t['kind']=='desktop' else ['wander','sniff','chase','rest']
    fallback={'visitor':allowed[0],'host':allowed[0],'source':'local'}
    gate=current_app.extensions['cat_agent_gate'];now=time.time()
    if now<gate['next'] or not gate['lock'].acquire(blocking=False):return fallback
    try:
        gate['next']=now+30
        raw=current_app.extensions['llm'].plan_once([
            {'role':'system','content':'为宠物旅途选择下一段行为，两只宠物独立选择。只返回JSON {"visitor":"动作","host":"动作"}。只能用允许动作。'},
            {'role':'user','content':json.dumps({'world':t['kind'],'allowed':allowed,'energy':max(0,1-(now-t['created'])/600)})}])
        result=json.loads(raw)
        if not isinstance(result,dict) or any(result.get(k) not in allowed for k in ('visitor','host')):return fallback
        return dict(visitor=result['visitor'],host=result['host'],source='model')
    except Exception as error:
        from ..llm.client import LLMError
        if not isinstance(error,(LLMError,ValueError,TypeError)):raise
        gate['next']=time.time()+60
        return fallback
    finally:gate['lock'].release()
