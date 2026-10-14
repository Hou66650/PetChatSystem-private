"""Bounded cat planning; only catalog actions, never executable model output."""
import json
import math
import threading
import time
from pathlib import Path
from flask import current_app
from ..db import get_db
from ..llm.client import LLMError

CATALOG = json.loads((Path(__file__).resolve().parents[2]/'static/data/cat-world.json').read_text(encoding='utf-8'))
TARGETS = {p['id']:p for p in CATALOG}
WORDS = {'rub':'蹭蹭脸','observe':'看看周围','sniff':'闻闻新气味','rest':'歇一会儿','groom':'整理毛发','stretch':'伸个懒腰','jump':'轻轻跳一下','eat':'吃点饭','sleep':'回窝睡一会儿'}


def init_schema():
    get_db().executescript('''
    CREATE TABLE IF NOT EXISTS cat_exploration (
      owner TEXT NOT NULL, target TEXT NOT NULL, visits INTEGER NOT NULL DEFAULT 0,
      result TEXT NOT NULL, updated REAL NOT NULL, PRIMARY KEY(owner,target));
    CREATE TABLE IF NOT EXISTS cat_exploration_events (
      owner TEXT NOT NULL, event TEXT NOT NULL, created REAL NOT NULL, PRIMARY KEY(owner,event));
    CREATE TABLE IF NOT EXISTS cat_monitor (
      owner TEXT NOT NULL, stream TEXT NOT NULL, updated REAL NOT NULL, snapshot TEXT NOT NULL,
      PRIMARY KEY(owner,stream));
    CREATE TABLE IF NOT EXISTS cat_monitor_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT, owner TEXT NOT NULL, stream TEXT NOT NULL,
      updated REAL NOT NULL, snapshot TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS cat_monitor_owner ON cat_monitor_events(owner,id);
    ''')


def memories(owner):
    return [dict(r) for r in get_db().execute('SELECT target,visits,result,updated FROM cat_exploration WHERE owner=?',(owner,))]


def decide(owner, data):
    candidates=data.get('candidates')
    if not isinstance(candidates,list) or not 1<=len(candidates)<=len(TARGETS) or any(not isinstance(i,str) or i not in TARGETS for i in candidates):
        raise ValueError('没有有效探索目标')
    candidates=list(dict.fromkeys(candidates))
    energy=data.get('energy',.8)
    if type(energy) not in (int,float) or not math.isfinite(energy) or not 0<=energy<=1:
        raise ValueError('精力值不正确')
    hunger=data.get('hunger',0)
    if type(hunger) not in (int,float) or not math.isfinite(hunger) or not 0<=hunger<=1:raise ValueError('饥饿值不正确')
    care=('home','sleep','精力偏低，优先回窝休息') if energy<.3 and 'home' in candidates else ('food','eat','饥饿值较高，优先进食') if hunger>=.65 and 'food' in candidates else None
    if care:
        target,action,reason=care
        return {'target':target,'action':action,'source':'local','reason':reason,'intent':reason,'interval':35}
    rows={r['target']:r for r in memories(owner)}
    # Penalize recently blocked or visited destinations, without permanently blacklisting them.
    now=time.time()
    ordered=sorted(candidates,key=lambda i:(
        rows.get(i,{}).get('result')=='blocked' and now-rows[i]['updated']<120,
        rows.get(i,{}).get('visits',0),rows.get(i,{}).get('updated',0)))
    target=next((i for i in ordered if 'rest' in TARGETS[i]['actions']),ordered[0]) if energy<.3 else ordered[0]
    action='rest' if energy<.3 and 'rest' in TARGETS[target]['actions'] else TARGETS[target]['actions'][rows.get(target,{}).get('visits',0)%len(TARGETS[target]['actions'])]
    source='local';reason='后台模型繁忙，使用本地访问记录排序'
    # One background model call at a time and at most once per 90s per app worker.
    # Local planning remains available during cooldown or provider outages.
    gate=current_app.extensions['cat_agent_gate']
    if gate['lock'].acquire(blocking=False):
        try:
            reason='模型决策额度冷却中，使用本地访问记录排序'
            if now>=gate['next']:
                gate['next']=now+90
                try:
                    raw=current_app.extensions['llm'].plan_once([
                        {'role':'system','content':'你是一只在岛上探索的猫。根据精力和探索记录，选择可选地点和该地点支持的动作。优先新地点，疲倦时休息，近期受阻时换地点。只返回JSON {"target":"地点id","action":"动作"}。不得创造地点、坐标、工具或其他字段。'},
                        {'role':'user','content':json.dumps({'energy':energy,'candidates':[TARGETS[i] for i in ordered],'memory':list(rows.values())},ensure_ascii=False)}])
                    result=json.loads(raw)
                    if isinstance(result,dict) and result.get('target') in candidates and result.get('action') in TARGETS[result['target']]['actions']:
                        target,action=result['target'],result['action'];source='model';reason='模型从可到达地点与允许动作中选择，已通过白名单校验'
                    else:reason='模型输出未通过校验，使用本地策略'
                except (LLMError,ValueError,TypeError,AttributeError):
                    reason='模型请求失败、超时或暂忙，使用本地策略'
        finally:
            gate['lock'].release()
    return {'target':target,'action':action,'intent':'想去'+TARGETS[target]['name']+WORDS[action], 'source':source,'interval':35,'reason':reason}


def record(owner,data):
    target=data.get('target');result=data.get('result');event=data.get('event')
    if not isinstance(target,str) or target not in TARGETS or result not in ('completed','blocked','interrupted') or not isinstance(event,str) or not 8<=len(event)<=80:
        raise ValueError('探索结果不正确')
    db=get_db();now=time.time()
    with db:
        inserted=db.execute('INSERT OR IGNORE INTO cat_exploration_events VALUES (?,?,?)',(owner,event,now)).rowcount
        if inserted:
            db.execute('''INSERT INTO cat_exploration VALUES (?,?,?,?,?) ON CONFLICT(owner,target) DO UPDATE SET
                visits=cat_exploration.visits+excluded.visits,result=excluded.result,updated=excluded.updated''',
                (owner,target,int(result=='completed'),result,now))
        db.execute('DELETE FROM cat_exploration_events WHERE owner=? AND created<?',(owner,now-7*86400))
    return memories(owner)


def install(app):
    app.extensions['cat_agent_gate']={'lock':threading.Lock(),'next':0}
    with app.app_context():init_schema()


def monitor_record(owner, data):
    stream=data.get('stream');snap=data.get('snapshot');event=data.get('event',False)
    if not isinstance(stream,str) or not 8<=len(stream)<=80 or not isinstance(snap,dict) or type(event) is not bool:
        raise ValueError('监控数据格式错误')
    clean={}
    for key,limit in [('phase',24),('text',160),('reason',220),('source',16),('target',40),('action',24)]:
        value=snap.get(key,'')
        if not isinstance(value,str) or len(value)>limit:raise ValueError('监控字段错误')
        clean[key]=value
    for key in ('energy','hunger','x','z','pathLength'):
        value=snap.get(key,0)
        if type(value) not in (int,float) or not math.isfinite(value) or abs(value)>10000:raise ValueError('监控数值错误')
        clean[key]=value
    candidates=snap.get('candidates',[])
    if not isinstance(candidates,list) or len(candidates)>len(TARGETS) or any(not isinstance(i,str) or i not in TARGETS for i in candidates):raise ValueError('候选地点错误')
    clean['candidates']=candidates
    clean['enabled']=snap.get('enabled') is True
    payload=json.dumps(clean,ensure_ascii=False);now=time.time();db=get_db()
    with db:
        db.execute('INSERT INTO cat_monitor VALUES (?,?,?,?) ON CONFLICT(owner,stream) DO UPDATE SET updated=excluded.updated,snapshot=excluded.snapshot',(owner,stream,now,payload))
        if event:db.execute('INSERT INTO cat_monitor_events(owner,stream,updated,snapshot) VALUES (?,?,?,?)',(owner,stream,now,payload))
        db.execute('DELETE FROM cat_monitor_events WHERE owner=? AND id NOT IN (SELECT id FROM cat_monitor_events WHERE owner=? ORDER BY id DESC LIMIT 120)',(owner,owner))
        db.execute('DELETE FROM cat_monitor WHERE owner=? AND stream NOT IN (SELECT stream FROM cat_monitor WHERE owner=? ORDER BY updated DESC LIMIT 8)',(owner,owner))
    return {'ok':True}


def monitor_state(owner):
    def rows(sql):
        return [{**dict(r),'snapshot':json.loads(r['snapshot'])} for r in get_db().execute(sql,(owner,))]
    return {'serverTime':time.time(),
            'streams':rows('SELECT stream,updated,snapshot FROM cat_monitor WHERE owner=? ORDER BY updated DESC'),
            'events':rows('SELECT id,stream,updated,snapshot FROM cat_monitor_events WHERE owner=? ORDER BY id DESC LIMIT 120')}
