"""Approved desktop tools: durable tasks, effects and notification attempts.

SQLite write transactions linearize approval, cancellation, due work and claims.
No model text can execute a tool. Notification attempts are never auto-retried.
"""
import json
import re
import secrets
import threading
import time
from flask import current_app
from ..db import get_db
from . import portal_service as portal, desktop_agent_service as agent

CAPABILITY_VERSION=1
CAPABILITIES=('reminder.create','focus_timer.start')


def init_schema():
    get_db().executescript('''
    CREATE TABLE IF NOT EXISTS desktop_tasks(
      id TEXT PRIMARY KEY, owner TEXT NOT NULL, pet TEXT NOT NULL, trip TEXT NOT NULL,
      capability TEXT NOT NULL, capability_version INTEGER NOT NULL,
      params TEXT NOT NULL, params_hash TEXT NOT NULL, context_version TEXT NOT NULL,
      resource_scope TEXT NOT NULL, status TEXT NOT NULL, version INTEGER NOT NULL,
      approval_expires REAL NOT NULL, trip_expires REAL NOT NULL, created REAL NOT NULL);
    CREATE INDEX IF NOT EXISTS desktop_tasks_trip ON desktop_tasks(trip,status);
    CREATE TABLE IF NOT EXISTS desktop_effects(
      id TEXT PRIMARY KEY, task_id TEXT NOT NULL UNIQUE, owner TEXT NOT NULL, trip TEXT NOT NULL,
      capability TEXT NOT NULL, state TEXT NOT NULL, version INTEGER NOT NULL,
      due_at REAL NOT NULL, finished REAL, reason TEXT NOT NULL DEFAULT '');
    CREATE UNIQUE INDEX IF NOT EXISTS desktop_one_focus ON desktop_effects(owner)
      WHERE capability='focus_timer.start' AND state='running';
    CREATE INDEX IF NOT EXISTS desktop_effects_due ON desktop_effects(state,due_at);
    CREATE TABLE IF NOT EXISTS desktop_deliveries(
      id TEXT PRIMARY KEY, effect_id TEXT NOT NULL, attempt INTEGER NOT NULL,
      state TEXT NOT NULL, version INTEGER NOT NULL, created REAL NOT NULL,
      claimed REAL, finished REAL, token_hash TEXT, auth_hash TEXT,
      cancel_requested INTEGER NOT NULL DEFAULT 0, evidence TEXT NOT NULL DEFAULT '',
      UNIQUE(effect_id,attempt));
    CREATE TABLE IF NOT EXISTS desktop_tool_requests(
      owner TEXT NOT NULL, pet TEXT NOT NULL, trip TEXT NOT NULL, operation TEXT NOT NULL,
      request_id TEXT NOT NULL, payload_hash TEXT NOT NULL, result_id TEXT NOT NULL,
      PRIMARY KEY(owner,pet,trip,operation,request_id));
    CREATE TABLE IF NOT EXISTS desktop_task_events(
      seq INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL, kind TEXT NOT NULL,
      detail TEXT NOT NULL, created REAL NOT NULL);
    ''')


def enabled():return bool(current_app.config.get('TOOLS_ENABLED',True) and current_app.config.get('DESKTOP_AGENT_ENABLED'))


def event(db,task_id,kind,detail,now):
    db.execute('INSERT INTO desktop_task_events(task_id,kind,detail,created) VALUES (?,?,?,?)',(task_id,kind,detail,now))


def delivery_state(db,row,state,now,evidence=''):
    if row['state']==state:return
    db.execute('UPDATE desktop_deliveries SET state=?,version=version+1,finished=?,evidence=? WHERE id=? AND version=?',
               (state,now,evidence,row['id'],row['version']))
    task=db.execute('SELECT task_id FROM desktop_effects WHERE id=?',(row['effect_id'],)).fetchone()
    event(db,task['task_id'],'delivery',state,now)


def cancel_task(db,task,now,reason):
    if task['status']=='awaiting_approval':
        db.execute("UPDATE desktop_tasks SET status='cancelled',version=version+1 WHERE id=? AND status='awaiting_approval'",(task['id'],))
        event(db,task['id'],'task','cancelled: '+reason,now)
    effect=db.execute('SELECT * FROM desktop_effects WHERE task_id=?',(task['id'],)).fetchone()
    if not effect:return
    if effect['state'] in ('scheduled','running'):
        db.execute("UPDATE desktop_effects SET state='cancelled',version=version+1,finished=?,reason=? WHERE id=?",(now,reason,effect['id']))
        event(db,task['id'],'effect','cancelled: '+reason,now)
    for row in db.execute("SELECT * FROM desktop_deliveries WHERE effect_id=? AND state IN ('pending','attempting','unknown')",(effect['id'],)).fetchall():
        db.execute('UPDATE desktop_deliveries SET cancel_requested=1 WHERE id=?',(row['id'],))
        if row['state']=='pending':delivery_state(db,row,'suppressed',now,'尚未领取，已取消')
        elif row['state']=='attempting':delivery_state(db,row,'unknown',now,'召回或取消时投递结果尚未确认')


def cancel_trip(db,trip,reason,now=None):
    now=time.time() if now is None else now
    for task in db.execute('SELECT * FROM desktop_tasks WHERE trip=?',(trip,)).fetchall():cancel_task(db,task,now,reason)


def live(trip,now):
    return trip and trip['status']=='active' and trip['phase']=='roaming' and now<portal.expires_at(trip) and now-trip['updated']<=45


def tick_locked(db,now):
    # Only in-flight rows need examination, not the entire historical task log.
    rows=db.execute("""SELECT DISTINCT t.* FROM desktop_tasks t LEFT JOIN desktop_effects e ON e.task_id=t.id
      LEFT JOIN desktop_deliveries d ON d.effect_id=e.id
      WHERE t.status='awaiting_approval' OR e.state IN ('scheduled','running') OR d.state IN ('pending','attempting')""").fetchall()
    for task in rows:
        trip=db.execute('SELECT * FROM portal_trips WHERE id=?',(task['trip'],)).fetchone()
        if not enabled() or not live(trip,now):
            cancel_task(db,task,now,'能力关闭或行程结束');continue
        if task['status']=='awaiting_approval':
            if now>=task['approval_expires']:
                db.execute("UPDATE desktop_tasks SET status='expired',version=version+1 WHERE id=? AND status='awaiting_approval'",(task['id'],))
                event(db,task['id'],'task','expired',now)
            else:
                try:changed=task['capability_version']!=CAPABILITY_VERSION or agent.manifest(trip)['version']!=task['context_version']
                except portal.PortalError:changed=True
                if changed:cancel_task(db,task,now,'档案、资产或能力版本已变化')
            continue
        effect=db.execute('SELECT * FROM desktop_effects WHERE task_id=?',(task['id'],)).fetchone()
        if effect and effect['state'] in ('scheduled','running') and now>=effect['due_at']:
            state='completed' if effect['capability']=='focus_timer.start' else 'due'
            db.execute('UPDATE desktop_effects SET state=?,version=version+1,finished=? WHERE id=?',(state,now,effect['id']))
            event(db,task['id'],'effect',state,now)
            delivery='missed' if now-effect['due_at']>60 else 'pending'
            db.execute("INSERT INTO desktop_deliveries(id,effect_id,attempt,state,version,created) VALUES (?,?,1,?,1,?)",
                       (secrets.token_hex(16),effect['id'],delivery,now))
            event(db,task['id'],'delivery',delivery,now)
    for row in db.execute("SELECT * FROM desktop_deliveries WHERE state IN ('pending','attempting')").fetchall():
        if row['state']=='attempting' and now-row['claimed']>=15:delivery_state(db,row,'unknown',now,'未收到可确认的系统回执')
        elif row['state']=='pending' and now-row['created']>60:delivery_state(db,row,'missed',now,'超过通知领取时限')


def tick():
    db=get_db()
    with db:
        db.execute('BEGIN IMMEDIATE');tick_locked(db,time.time())


def install(app):
    stop=threading.Event();app.extensions['desktop_task_scheduler_stop']=stop
    if app.testing or not app.config.get('DESKTOP_TASK_SCHEDULER_ENABLED',True):return
    def worker():
        while not stop.wait(1):
            try:
                with app.app_context():tick()
            except Exception:app.logger.exception('Desktop task scheduler tick failed')
    thread=threading.Thread(target=worker,name='desktop-task-scheduler',daemon=True);thread.start()
    app.extensions['desktop_task_scheduler']=thread


def public(task):
    db=get_db();result=dict(task);result['params']=json.loads(result['params'])
    result.pop('owner');result.pop('context_version')
    effect=db.execute('SELECT * FROM desktop_effects WHERE task_id=?',(task['id'],)).fetchone()
    result['effect']=None
    if effect:
        e={k:effect[k] for k in ('id','state','version','due_at','finished','reason')}
        e['deliveries']=[{k:r[k] for k in ('id','attempt','state','version','created','claimed','finished','cancel_requested','evidence')} for r in db.execute('SELECT * FROM desktop_deliveries WHERE effect_id=? ORDER BY attempt',(effect['id'],))]
        result['effect']=e
    result['seq']=db.execute('SELECT COALESCE(MAX(seq),0) FROM desktop_task_events WHERE task_id=?',(task['id'],)).fetchone()[0]
    return result


def snapshot(owner,trip=None):
    tick();db=get_db()
    with db:
        db.execute('BEGIN')
        rows=db.execute('SELECT * FROM desktop_tasks WHERE owner=?'+(' AND trip=?' if trip else '')+' ORDER BY created DESC LIMIT 100',
                        (owner,trip) if trip else (owner,)).fetchall()
        return dict(protocol=1,tasks=[public(r) for r in rows],serverTime=time.time(),toolsEnabled=enabled())


def owned(t,task_id):
    row=get_db().execute('SELECT * FROM desktop_tasks WHERE id=? AND owner=? AND pet=? AND trip=?',(task_id,t['owner'],t['pet'],t['id'])).fetchone()
    if not row:raise portal.PortalError('没有找到本次行程的任务',404,'TASK_NOT_FOUND')
    return row


def request_key(t,op,data):
    rid=data.get('requestId')
    if not isinstance(rid,str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,80}',rid):raise portal.PortalError('请求编号无效')
    return (t['owner'],t['pet'],t['id'],op,rid)


def validate_fields(data,fields):
    if not isinstance(data,dict) or set(data)-set(fields):raise portal.PortalError('请求参数不支持')


def mutate(t,op,data):
    fields={'propose':('requestId','contextVersion','capability','title','seconds'),
            'approve':('requestId','taskId','taskVersion','paramsHash'),
            'cancel':('requestId','taskId'),
            'retry':('requestId','taskId','deliveryId','confirmDuplicate')}
    if op not in fields:raise portal.PortalError('操作不存在',404)
    validate_fields(data,fields[op]);key=request_key(t,op,data);payload_hash=agent.digest(data)
    if op!='propose' and (not isinstance(data.get('taskId'),str) or not re.fullmatch(r'[a-f0-9]{32}',data['taskId'])):raise portal.PortalError('任务编号无效')
    if op=='approve' and (type(data.get('taskVersion')) is not int or not isinstance(data.get('paramsHash'),str)):raise portal.PortalError('审批版本无效')
    if op=='retry' and not isinstance(data.get('deliveryId'),str):raise portal.PortalError('通知编号无效')
    tick();db=get_db()
    with db:
        db.execute('BEGIN IMMEDIATE')
        now=time.time()  # Lock contention must not extend approval/trip deadlines.
        previous=db.execute('SELECT * FROM desktop_tool_requests WHERE owner=? AND pet=? AND trip=? AND operation=? AND request_id=?',key).fetchone()
        if previous:
            if previous['payload_hash']!=payload_hash:raise portal.PortalError('同一请求编号的内容已变化',409,'REQUEST_CONFLICT')
            return dict(task=public(owned(t,previous['result_id'])),duplicate=True)
        trip=db.execute('SELECT * FROM portal_trips WHERE id=?',(t['id'],)).fetchone()
        if not live(trip,now):raise portal.PortalError('桌面行程已结束或尚未到达',409,'TRIP_ENDED')
        if op!='cancel' and not enabled():raise portal.PortalError('桌面工具已关闭',403,'TOOLS_DISABLED')
        if op=='propose':
            agent.check(trip,data.get('contextVersion'))
            cap=data.get('capability');seconds=data.get('seconds');title=data.get('title')
            if cap not in CAPABILITIES or type(seconds) is not int or not 10<=seconds<=1800 or not isinstance(title,str) or not 1<=len(title.strip())<=80:
                raise portal.PortalError('请选择提醒或专注，时长 10–1800 秒，内容 1–80 字')
            if now+seconds>=portal.expires_at(trip):raise portal.PortalError('超出本次行程最迟返程时间，请缩短时长',409,'TRIP_DEADLINE')
            count=db.execute("SELECT count(*) FROM desktop_tasks WHERE owner=? AND status='awaiting_approval'",(t['owner'],)).fetchone()[0]
            if count>=40:raise portal.PortalError('待确认任务过多，请先处理已有审批',429,'TASK_LIMIT')
            params=dict(title=title.strip(),seconds=seconds)
            if cap=='reminder.create':params['dueAt']=now+seconds
            scope='trip:'+trip['id'];param_hash=agent.digest([params,scope,cap,CAPABILITY_VERSION])
            expires=min(now+300,params.get('dueAt',portal.expires_at(trip)-seconds))
            task_id=secrets.token_hex(16)
            db.execute('INSERT INTO desktop_tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                       (task_id,t['owner'],t['pet'],t['id'],cap,CAPABILITY_VERSION,json.dumps(params,ensure_ascii=False),param_hash,data['contextVersion'],scope,'awaiting_approval',1,expires,portal.expires_at(trip),now))
            event(db,task_id,'task','awaiting_approval',now)
        else:
            task=owned(t,data.get('taskId'));task_id=task['id']
            if op=='cancel':cancel_task(db,task,now,'主人取消')
            elif op=='approve':
                if task['status']!='awaiting_approval':raise portal.PortalError('审批已完成、过期或取消',409,'APPROVAL_CLOSED')
                if task['version']!=data.get('taskVersion') or task['params_hash']!=data.get('paramsHash'):
                    raise portal.PortalError('参数版本已变化，请重新查看审批卡',409,'APPROVAL_CHANGED')
                if now>=task['approval_expires'] or task['capability_version']!=CAPABILITY_VERSION:raise portal.PortalError('审批已过期',409,'APPROVAL_CLOSED')
                agent.check(trip,task['context_version']);params=json.loads(task['params'])
                due=params.get('dueAt',now+params['seconds'])
                if due<=now or due>=portal.expires_at(trip):raise portal.PortalError('任务已超出本次行程时限',409,'TRIP_DEADLINE')
                active=db.execute("SELECT count(*) FROM desktop_effects WHERE owner=? AND state IN ('running','scheduled')",(t['owner'],)).fetchone()[0]
                if active>=40:raise portal.PortalError('活跃任务过多',429,'TASK_LIMIT')
                if task['capability']=='focus_timer.start' and db.execute("SELECT 1 FROM desktop_effects WHERE owner=? AND capability='focus_timer.start' AND state='running'",(t['owner'],)).fetchone():
                    raise portal.PortalError('你已有一个专注计时，请先结束或取消它',409,'FOCUS_CONFLICT')
                db.execute('INSERT INTO desktop_effects(id,task_id,owner,trip,capability,state,version,due_at) VALUES (?,?,?,?,?,?,1,?)',
                           (secrets.token_hex(16),task_id,t['owner'],t['id'],task['capability'],'running' if task['capability']=='focus_timer.start' else 'scheduled',due))
                event(db,task_id,'effect','running' if task['capability']=='focus_timer.start' else 'scheduled',now)
                db.execute("UPDATE desktop_tasks SET status='succeeded',version=version+1 WHERE id=? AND version=? AND status='awaiting_approval'",(task_id,task['version']))
                event(db,task_id,'task','succeeded',now)
            else:
                if data.get('confirmDuplicate') is not True:raise portal.PortalError('再次投递可能重复，请先明确确认',409,'DUPLICATE_CONFIRMATION_REQUIRED')
                row=db.execute('SELECT d.* FROM desktop_deliveries d JOIN desktop_effects e ON e.id=d.effect_id WHERE d.id=? AND e.task_id=?',(data.get('deliveryId'),task_id)).fetchone()
                if not row or row['state'] not in ('unknown','failed','missed') or row['cancel_requested']:raise portal.PortalError('此通知不能再次投递',409,'RETRY_UNAVAILABLE')
                latest=db.execute('SELECT MAX(attempt) FROM desktop_deliveries WHERE effect_id=?',(row['effect_id'],)).fetchone()[0]
                if row['attempt']!=latest or latest>=5:raise portal.PortalError('已有更新的投递尝试或达到重试上限',409,'RETRY_UNAVAILABLE')
                db.execute("INSERT INTO desktop_deliveries(id,effect_id,attempt,state,version,created) VALUES (?,?,?,'pending',1,?)",(secrets.token_hex(16),row['effect_id'],latest+1,now))
                event(db,task_id,'delivery','manual_retry',now)
        db.execute('INSERT INTO desktop_tool_requests VALUES (?,?,?,?,?,?,?)',(*key,payload_hash,task_id))
        return dict(task=public(owned(t,task_id)),duplicate=False)


def claim(t,auth):
    db=get_db()
    with db:
        db.execute('BEGIN IMMEDIATE')
        now=time.time();tick_locked(db,now)
        trip=db.execute('SELECT * FROM portal_trips WHERE id=?',(t['id'],)).fetchone()
        if not enabled() or not live(trip,now):return dict(delivery=None)
        row=db.execute("SELECT d.*,t.params,t.id AS task_id FROM desktop_deliveries d JOIN desktop_effects e ON e.id=d.effect_id JOIN desktop_tasks t ON t.id=e.task_id WHERE t.trip=? AND d.state='pending' AND d.cancel_requested=0 ORDER BY d.created LIMIT 1",(t['id'],)).fetchone()
        if not row:return dict(delivery=None)
        token=secrets.token_urlsafe(32)
        db.execute("UPDATE desktop_deliveries SET state='attempting',version=version+1,claimed=?,token_hash=?,auth_hash=? WHERE id=? AND state='pending'",(now,portal.digest(token),portal.digest(auth),row['id']))
        event(db,row['task_id'],'delivery','attempting',now)
        return dict(delivery=dict(id=row['id'],token=token,title=json.loads(row['params'])['title'],taskId=row['task_id']))


def acknowledge(auth,data):
    validate_fields(data,('deliveryId','token','state','evidence'))
    state=data.get('state');evidence=data.get('evidence')
    evidence_for={'delivered':'os-show','failed':'unsupported','unknown':'unconfirmed','suppressed':'not-called'}
    if not isinstance(state,str) or state not in evidence_for or evidence!=evidence_for[state] or not isinstance(data.get('token'),str) or not isinstance(data.get('deliveryId'),str):raise portal.PortalError('通知回执无效')
    db=get_db()
    with db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT * FROM desktop_deliveries WHERE id=?',(data.get('deliveryId'),)).fetchone()
        if not row or not secrets.compare_digest(row['token_hash'] or '',portal.digest(data['token'])) or not secrets.compare_digest(row['auth_hash'] or '',portal.digest(auth)):
            raise portal.PortalError('通知回执不属于此行程',403,'RECEIPT_FORBIDDEN')
        # A late positive receipt can refine unknown, including after recall.
        # Delivered and confirmed-not-called are terminal facts, never overwritten.
        if row['state'] in ('attempting','unknown'):delivery_state(db,row,state,time.time(),evidence)
        return dict(ok=True,state=db.execute('SELECT state FROM desktop_deliveries WHERE id=?',(row['id'],)).fetchone()[0])
