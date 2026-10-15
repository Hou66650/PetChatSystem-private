"""Account-scoped album and short-lived monitor commands."""
import base64,json,re,time,uuid
from ..db import get_db

def db_ready():
    db=get_db()
    db.execute('CREATE TABLE IF NOT EXISTS cat_album(owner TEXT NOT NULL, day TEXT NOT NULL, story TEXT NOT NULL, coat TEXT NOT NULL, image BLOB NOT NULL, PRIMARY KEY(owner,day))')
    db.execute('CREATE TABLE IF NOT EXISTS cat_controls(owner TEXT NOT NULL, stream TEXT NOT NULL, id TEXT NOT NULL, action TEXT NOT NULL, created REAL NOT NULL, result TEXT NOT NULL, PRIMARY KEY(owner,stream))')
    return db

def album(owner):
    return [dict(r) for r in db_ready().execute('SELECT day,story,coat FROM cat_album WHERE owner=? ORDER BY day DESC LIMIT 90',(owner,))]

def save_card(owner,identifier):
    from .story_art_service import snapshot
    art=snapshot(owner);card=art.get('card',{})
    if not isinstance(identifier,str) or identifier!=art.get('id') or art.get('status')!='ready' or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',card.get('day','')):
        raise ValueError('请先生成今天的插画，再收藏。')
    db=db_ready()
    with db:
        db.execute('INSERT INTO cat_album VALUES (?,?,?,?,?) ON CONFLICT(owner,day) DO UPDATE SET story=excluded.story,coat=excluded.coat,image=excluded.image',
                   (owner,card['day'],card['story'],card['coat'],base64.b64decode(art['image'].split(',',1)[1])))
        db.execute('DELETE FROM cat_album WHERE owner=? AND day NOT IN (SELECT day FROM cat_album WHERE owner=? ORDER BY day DESC LIMIT 90)',(owner,owner))
    return album(owner)

def delete_card(owner,day):
    if not isinstance(day,str):raise ValueError('日期无效')
    db=db_ready()
    with db:db.execute('DELETE FROM cat_album WHERE owner=? AND day=?',(owner,day))
    return album(owner)

def image(owner,day):
    row=db_ready().execute('SELECT image FROM cat_album WHERE owner=? AND day=?',(owner,day)).fetchone()
    return row['image'] if row else None

def send_control(owner,data):
    from .cat_agent_service import monitor_state
    stream=data.get('stream');action=data.get('action')
    if not isinstance(stream,str) or action not in ('pause','resume','home'):raise ValueError('指令无效')
    live=next((s for s in monitor_state(owner)['streams'] if s['stream']==stream),None)
    if not live or time.time()-live['updated']>10 or live['snapshot'].get('phase')=='stopped':raise ValueError('猫咪页面不在线，请先打开小岛。')
    db=db_ready();identifier=uuid.uuid4().hex
    with db:
        db.execute('DELETE FROM cat_controls WHERE created<?',(time.time()-86400,))
        db.execute('INSERT INTO cat_controls VALUES (?,?,?,?,?,?) ON CONFLICT(owner,stream) DO UPDATE SET id=excluded.id,action=excluded.action,created=excluded.created,result=excluded.result',
                   (owner,stream,identifier,action,time.time(),'pending'))
    return dict(id=identifier,result='pending')

def controls(owner):
    return [dict(r) for r in db_ready().execute('SELECT stream,id,action,created,result FROM cat_controls WHERE owner=?',(owner,))]

def delivery(owner,data):
    db=db_ready();stream=data['stream'];ack=data.get('controlAck')
    with db:
        if isinstance(ack,dict) and isinstance(ack.get('id'),str) and ack.get('result') in ('applied','busy','unavailable'):
            db.execute('UPDATE cat_controls SET result=? WHERE owner=? AND stream=? AND id=? AND result=?',(ack['result'],owner,stream,ack['id'],'pending'))
        db.execute("UPDATE cat_controls SET result='expired' WHERE owner=? AND result='pending' AND created<?",(owner,time.time()-30))
    row=db.execute("SELECT id,action FROM cat_controls WHERE owner=? AND stream=? AND result='pending'",(owner,stream)).fetchone()
    return dict(row) if row else None
