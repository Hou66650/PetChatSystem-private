"""One factual, first-person page per owner/pet/Shanghai day, updated by completed events."""
from datetime import datetime, timedelta, timezone
import time

from ..db import get_db

TZ = timezone(timedelta(hours=8))
NAMES = {1: '球球', 2: '雪球', 3: '团子', 4: '大壮'}
HOMES = {1: '樱花庭院', 2: '雪境木屋', 3: '雾林温室', 4: '山岭营地'}
ACTIVITIES = {'drink':'喝了点清水','paw':'用爪子扒了扒门','nibble':'尝了尝猫草',
              'rub':'蹭了蹭脸','observe':'看了看四周','sniff':'闻了闻附近的气味',
              'rest':'歇了一会儿','groom':'整理了毛发','stretch':'伸了个懒腰',
              'jump':'轻轻跳了一下','eat':'吃了点饭','sleep':'回窝睡了一会儿'}
INTERACTIONS = {
    'pet': '主人轻轻摸了摸我，我把这份温柔收进了今天的记忆。',
    'hand': '主人的手靠近时，我和主人玩了一会儿面对面的互动。',
    'feed': '主人亲手喂了我，一小口食物也装着满满的关心。',
    'game': '我和主人玩了小游戏，这段一起玩的时间值得记下来。',
    'gaze': '我和主人对视了一会儿，安静地看着彼此也很温暖。',
    'gesture': '主人用手势和我打招呼，我也认真回应了这场小小的交流。',
}


def day(now=None):
    return datetime.fromtimestamp(time.time() if now is None else now, TZ).date().isoformat()


def init_schema():
    get_db().executescript('''
    CREATE TABLE IF NOT EXISTS pet_diary_facts(
      owner TEXT NOT NULL, source TEXT NOT NULL, pet_id INTEGER NOT NULL,
      day TEXT NOT NULL, kind TEXT NOT NULL, detail TEXT NOT NULL, created REAL NOT NULL,
      PRIMARY KEY(owner,source));
    CREATE INDEX IF NOT EXISTS diary_facts_day ON pet_diary_facts(owner,pet_id,day);
    CREATE TABLE IF NOT EXISTS pet_diary_days(
      owner TEXT NOT NULL, pet_id INTEGER NOT NULL, day TEXT NOT NULL,
      name TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL,
      updated REAL NOT NULL, deleted INTEGER NOT NULL DEFAULT 0,
      PRIMARY KEY(owner,pet_id,day));
    ''')


def write_day(db, owner, pet, date):
    rows = db.execute('''SELECT kind,detail,COUNT(*) AS n,MIN(created) AS first
        FROM pet_diary_facts WHERE owner=? AND pet_id=? AND day=?
        GROUP BY kind,detail ORDER BY first,kind,detail''', (owner,pet,date)).fetchall()
    existing = db.execute('SELECT deleted FROM pet_diary_days WHERE owner=? AND pet_id=? AND day=?', (owner,pet,date)).fetchone()
    if existing and existing['deleted']:
        return
    if not rows:
        db.execute('DELETE FROM pet_diary_days WHERE owner=? AND pet_id=? AND day=?', (owner,pet,date))
        return
    nickname = db.execute("SELECT value FROM companion_memories WHERE owner=? AND pet_id=? AND category='pet_name' ORDER BY updated_at DESC LIMIT 1", (owner,pet)).fetchone()
    name = nickname['value'] if nickname else NAMES[pet]
    paragraphs = [f'我是{name}，这是我给今天留下的一页日记。']
    places = list(dict.fromkeys(r['detail'] for r in rows if r['kind']=='explore'))
    if places:
        paragraphs.append('今天，我的小脚步走到了'+'、'.join(places[:12])+'。'+('还有一些熟悉的角落，也留下了我的足迹。' if len(places)>12 else '')+'每到一处，我都把这一站记在自己的小本子上。')
    elif any(r['kind']=='visit' for r in rows):
        paragraphs.append('今天我待在'+HOMES[pet]+'。小窝的这一页，又添上了属于我的一天。')
    activities = [r['detail'] for r in rows if r['kind']=='activity']
    if activities:
        paragraphs.append('在探索的间隙，我还'+ '、'.join(activities[:8])+'。')
    interactions = [INTERACTIONS[r['detail']] for r in rows if r['kind']=='interaction' and r['detail'] in INTERACTIONS]
    chats = sum(r['n'] for r in rows if r['kind']=='chat')
    if chats:
        topics = list(dict.fromkeys(r['detail'] for r in rows if r['kind']=='chat' and r['detail']))
        interactions.append(f'主人今天和我聊了{chats}轮。'+('我们聊到了'+'、'.join(topics[:5])+'，' if topics else '')+'能听见主人的话、给出自己的回应，就是我珍惜的陪伴。')
    if interactions:
        paragraphs.append('\n'.join(interactions))
    events = [r['detail'] for r in rows if r['kind']=='event']
    if events:
        paragraphs.append('今天还有几件值得记住的小事：'+ '；'.join(events[:8])+'。')
    closings = {1:'我把这些小事都装进了心里。明天，也想摇着尾巴和主人见面！',
                2:'把今天记好啦！明天还想和主人一起发现新鲜事，嗷呜。',
                3:'我把今天轻轻夹进这一页，留一个软软的爪印。明天见，喵。',
                4:'今天的记忆已经收好。明天，我也想稳稳地陪在主人身边。'}
    paragraphs.append(closings[pet])
    db.execute('''INSERT INTO pet_diary_days(owner,pet_id,day,name,title,body,updated)
        VALUES (?,?,?,?,?,?,?) ON CONFLICT(owner,pet_id,day) DO UPDATE SET
        name=excluded.name,title=excluded.title,body=excluded.body,updated=excluded.updated''',
        (owner,pet,date,name,'我的这一天','\n\n'.join(paragraphs),time.time()))


def record(db, owner, pet, source, kind, detail='', now=None, refresh=True):
    pet = int(pet)
    if pet not in NAMES:
        return False
    prefs = db.execute('SELECT enabled FROM companion_owners WHERE owner=?', (owner,)).fetchone()
    if not prefs or not prefs['enabled']:
        return False
    now = time.time() if now is None else now
    date = day(now)
    from . import growth_service
    growth_service.observe(db,owner,pet,source,kind,str(detail)[:160],now)
    deleted = db.execute('SELECT deleted FROM pet_diary_days WHERE owner=? AND pet_id=? AND day=?', (owner,pet,date)).fetchone()
    if deleted and deleted['deleted']:
        return False
    added = db.execute('INSERT OR IGNORE INTO pet_diary_facts VALUES (?,?,?,?,?,?,?)',
                       (owner,source,pet,date,kind,str(detail)[:160],now)).rowcount
    if added and refresh:
        write_day(db,owner,pet,date)
    return bool(added)


def topic(message):
    # No copied private transcript and no invented summary of what the user said.
    return '、'.join(t for t in ('工作','学习','考试','旅行','音乐','电影','游戏','天气','运动','心情') if t in message)[:50]


def backfill_chats(db, owner):
    changed = set()
    rows = db.execute('''SELECT m.id,m.pet_id,m.content,m.created_at FROM companion_messages m
        LEFT JOIN pet_diary_facts f ON f.owner=m.owner AND f.source='chat:'||m.id
        LEFT JOIN pet_diary_days d ON d.owner=m.owner AND d.pet_id=m.pet_id
          AND d.day=date(m.created_at,'+8 hours')
        WHERE m.owner=? AND m.role='user' AND f.source IS NULL AND COALESCE(d.deleted,0)=0
        AND EXISTS(SELECT 1 FROM companion_messages a WHERE a.owner=m.owner AND a.pet_id=m.pet_id
            AND a.request_id=m.request_id AND a.role='assistant')''', (owner,)).fetchall()
    for row in rows:
        try:
            stamp = datetime.fromisoformat(row['created_at'].replace('Z','+00:00'))
            if stamp.tzinfo is None: continue  # Never guess the day of undated legacy chats.
            now = stamp.timestamp()
        except (TypeError,ValueError):
            continue
        if record(db,owner,row['pet_id'],'chat:'+str(row['id']),'chat',topic(row['content']),now,False):
            changed.add((row['pet_id'],day(now)))
    for pet,date in changed:
        write_day(db,owner,pet,date)


def pages(owner, before=None):
    db=get_db()
    with db: backfill_chats(db,owner)
    sql='SELECT pet_id AS petId,day,name,title,body,updated FROM pet_diary_days WHERE owner=? AND deleted=0'
    args=[owner]
    if before: sql+=' AND day<?';args.append(before)
    # Page whole days so two pets on the boundary cannot be skipped.
    dates=[r[0] for r in db.execute('SELECT DISTINCT day FROM ('+sql+') ORDER BY day DESC LIMIT 31',args)]
    if not dates: return dict(entries=[],nextBefore=None,timezone='Asia/Shanghai')
    entries=[dict(r) for r in db.execute(sql+' AND day>=? ORDER BY day DESC,pet_id',args+[dates[min(29,len(dates)-1)]])]
    for entry in entries: entry['draft']=entry['day']==day()
    return dict(entries=entries,nextBefore=dates[29] if len(dates)>30 else None,timezone='Asia/Shanghai')


def remove_chats(db, owner, pet=None, message_id=None):
    sql="SELECT DISTINCT pet_id,day FROM pet_diary_facts WHERE owner=? AND kind='chat'";args=[owner]
    if pet is not None: sql+=' AND pet_id=?';args.append(pet)
    if message_id is not None: sql+=' AND source=?';args.append('chat:'+str(message_id))
    affected=db.execute(sql,args).fetchall()
    db.execute(sql.replace('SELECT DISTINCT pet_id,day','DELETE'),args)
    for row in affected: write_day(db,owner,row['pet_id'],row['day'])


def forget(db, owner):
    db.execute('DELETE FROM pet_diary_facts WHERE owner=?',(owner,))
    db.execute('DELETE FROM pet_diary_days WHERE owner=?',(owner,))
