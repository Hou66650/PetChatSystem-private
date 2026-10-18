import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from test_desktop_agent import DesktopAgentTests as Base
from app.db import get_db
from app.services import desktop_task_service as tasks,portal_service as portal


class DesktopTaskTests(unittest.TestCase):
    setUp=Base.setUp
    tearDown=Base.tearDown
    start=Base.start
    post=Base.post
    pair=Base.pair
    call=Base.call

    def op(self,op,data=None,client=None):return (client or self.a).post('/api/desktop/v1/'+op,json=data or {},headers=self.auth)
    def propose(self,rid='proposal-0001',cap='reminder.create',seconds=30):
        return self.op('propose',dict(requestId=rid,contextVersion=self.version,capability=cap,title='喝水',seconds=seconds))
    def approve(self,task,rid='approval-0001'):
        return self.op('approve',dict(requestId=rid,taskId=task['id'],taskVersion=task['version'],paramsHash=task['params_hash']))
    def cancel(self,task):return self.op('cancel',dict(requestId='cancel-'+task['id'],taskId=task['id']))
    def advance(self,task,seconds=31):
        now=task['created']+seconds
        with patch.object(tasks.time,'time',return_value=now):
            with self.app.app_context():tasks.tick()
        return now
    def due(self):
        task=self.propose().json['task'];self.approve(task);self.advance(task)
        return task
    def ack(self,item,state,evidence,auth=None):
        return self.a.post('/api/desktop/v1/ack',headers=auth or self.auth,json=dict(deliveryId=item['id'],token=item['token'],state=state,evidence=evidence))

    def test_explicit_approval_effect_and_notification_are_separate(self):
        self.pair();p=self.propose();self.assertEqual(p.status_code,200);task=p.json['task']
        self.assertEqual(task['status'],'awaiting_approval');self.assertIsNone(task['effect'])
        self.assertEqual(self.propose().json['task']['id'],task['id'])
        changed=self.op('propose',dict(requestId='proposal-0001',contextVersion=self.version,capability='reminder.create',title='不同',seconds=30))
        self.assertEqual(changed.json['code'],'REQUEST_CONFLICT')
        r=self.approve(task);self.assertEqual(r.status_code,200);self.assertEqual(r.json['task']['status'],'succeeded');self.assertEqual(r.json['task']['effect']['state'],'scheduled')
        self.assertTrue(self.approve(task).json['duplicate']);self.advance(task)
        state=self.op('state').json['tasks'][0];self.assertEqual(state['effect']['state'],'due');self.assertEqual(state['effect']['deliveries'][0]['state'],'pending')
        item=self.op('claim').json['delivery'];self.assertTrue(item);self.assertIsNone(self.op('claim').json['delivery'])
        self.assertEqual(self.ack(item,'unknown','unconfirmed').json['state'],'unknown')
        state=self.op('state').json['tasks'][0];self.assertEqual(state['status'],'succeeded');self.assertEqual(state['effect']['state'],'due')

    def test_parallel_approval_creates_one_effect(self):
        self.pair();task=self.propose().json['task']
        body=dict(requestId='approval-0001',taskId=task['id'],taskVersion=1,paramsHash=task['params_hash'])
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(lambda _:self.op('approve',body,self.app.test_client()),range(4)))
        self.assertTrue(all(r.status_code==200 for r in results));self.assertEqual(sum(not r.json['duplicate'] for r in results),1)
        with self.app.app_context():self.assertEqual(get_db().execute('SELECT count(*) FROM desktop_effects').fetchone()[0],1)

    def test_focus_conflict_is_owner_wide_and_not_recall(self):
        self.pair();a=self.propose(cap='focus_timer.start').json['task'];self.approve(a)
        first_auth=self.auth
        d=self.post('depart',dict(pet='1',kind='desktop',confirmed=True)).json
        self.trip=d['trip'];paired=self.a.post('/api/portals/desktop/pair',json={'code':d['code']}).json;self.auth={'Authorization':'Bearer '+paired['token']}
        self.call('ready');self.post('depart-complete',{'trip':self.trip});self.call('arrived');self.version=self.call('manifest').json['version']
        b=self.propose('proposal-0002','focus_timer.start').json['task'];r=self.approve(b,'approval-0002')
        self.assertEqual(r.json['code'],'FOCUS_CONFLICT');self.assertEqual(self.call('state').json['phase'],'roaming')
        self.auth=first_auth;self.cancel(a)
        self.auth={'Authorization':'Bearer '+paired['token']};self.assertEqual(self.approve(b,'approval-0002').status_code,200)

    def test_expiry_parameter_and_context_binding(self):
        self.pair();task=self.propose(seconds=600).json['task']
        self.assertEqual(self.op('approve',dict(requestId='approval-0001',taskId=task['id'],taskVersion=1,paramsHash='wrong')).json['code'],'APPROVAL_CHANGED')
        self.a.patch('/api/companion',json={'enabled':False})
        self.assertEqual(self.op('state').json['tasks'][0]['status'],'cancelled')
        self.version=self.call('manifest').json['version'];task=self.propose('proposal-0002',seconds=600).json['task']
        now=task['approval_expires']
        with self.app.app_context():
            db=get_db();db.execute('UPDATE portal_trips SET updated=? WHERE id=?',(now,self.trip));db.commit()
        with patch.object(tasks.time,'time',return_value=now):
            self.assertEqual(self.op('state').json['tasks'][0]['status'],'expired')
            self.assertEqual(self.approve(task).json['code'],'APPROVAL_CLOSED')
        self.assertEqual(self.propose('deadline-0001',seconds=1800).json['code'],'TRIP_DEADLINE')

    def test_recall_cancels_pending_but_preserves_completed_and_late_receipts(self):
        self.pair();task=self.due();item=self.op('claim').json['delivery']
        self.post('return',{'trip':self.trip})
        state=self.a.get('/api/desktop/v1/tasks').json['tasks'][0]
        self.assertEqual(state['status'],'succeeded');self.assertEqual(state['effect']['state'],'due');self.assertEqual(state['effect']['deliveries'][0]['state'],'unknown')
        self.assertEqual(self.ack(item,'delivered','os-show').json['state'],'delivered')
        self.assertEqual(self.ack(item,'suppressed','not-called').json['state'],'delivered')
        self.assertEqual(self.ack(item,'delivered','os-show',{'Authorization':'Bearer another'}).status_code,403)

    def test_waiting_for_write_lock_cannot_extend_approval_deadline(self):
        self.pair();task=self.propose().json['task']
        with self.app.app_context(),patch.object(tasks,'tick'),patch.object(tasks.time,'time',return_value=task['created']) as clock:
            db=get_db();trip=db.execute('SELECT * FROM portal_trips WHERE id=?',(self.trip,)).fetchone()
            class AfterLock:
                def __enter__(self):db.__enter__();return self
                def __exit__(self,*args):return db.__exit__(*args)
                def execute(self,sql,*args):
                    result=db.execute(sql,*args)
                    if sql=='BEGIN IMMEDIATE':clock.return_value=task['approval_expires']
                    return result
            with patch.object(tasks,'get_db',return_value=AfterLock()):
                with self.assertRaises(portal.PortalError) as caught:
                    tasks.mutate(trip,'approve',dict(requestId='approval-after-lock',taskId=task['id'],taskVersion=1,paramsHash=task['params_hash']))
            self.assertEqual(caught.exception.code,'APPROVAL_CLOSED')
            self.assertEqual(db.execute('SELECT count(*) FROM desktop_effects').fetchone()[0],0)

    def test_recall_before_claim_suppresses_and_cancel_before_due_wins(self):
        self.pair();task=self.due();self.post('return',{'trip':self.trip})
        self.assertEqual(self.a.get('/api/desktop/v1/tasks').json['tasks'][0]['effect']['deliveries'][0]['state'],'suppressed')
        self.pair();task=self.propose('proposal-new1').json['task'];self.approve(task);self.cancel(task);self.advance(task)
        current=self.op('state').json['tasks'][0]
        self.assertEqual(current['status'],'succeeded');self.assertEqual(current['effect']['state'],'cancelled');self.assertEqual(current['effect']['deliveries'],[])

    def test_unknown_never_auto_retries_and_manual_retry_is_audited(self):
        self.pair();task=self.due();item=self.op('claim').json['delivery']
        with patch.object(tasks.time,'time',return_value=time.time()+16):
            state=self.op('state').json['tasks'][0]
        self.assertEqual(state['effect']['deliveries'][0]['state'],'unknown');self.assertIsNone(self.op('claim').json['delivery'])
        payload=dict(requestId='retry-000001',taskId=task['id'],deliveryId=item['id'])
        self.assertEqual(self.op('retry',payload).json['code'],'DUPLICATE_CONFIRMATION_REQUIRED')
        payload['confirmDuplicate']=True
        self.assertEqual(self.op('retry',payload).status_code,200);self.assertTrue(self.op('retry',payload).json['duplicate'])
        deliveries=self.op('state').json['tasks'][0]['effect']['deliveries'];self.assertEqual([d['state'] for d in deliveries],['unknown','pending'])
        self.assertNotEqual(self.op('claim').json['delivery']['id'],item['id'])

    def test_read_only_cookies_and_cross_owner_isolation(self):
        self.pair();self.propose()
        self.assertEqual(len(self.a.get('/api/desktop/v1/tasks').json['tasks']),1)
        self.assertEqual(self.b.get('/api/desktop/v1/tasks').json['tasks'],[])
        self.assertEqual(self.a.post('/api/desktop/v1/propose',json={}).status_code,401)
        self.assertEqual(self.a.post('/api/desktop/v1/approve',json={},headers={**self.auth,'Origin':'https://evil.example'}).status_code,403)

    def test_flag_rollback_and_restart_do_not_repeat_effects(self):
        self.pair();task=self.propose().json['task'];self.approve(task)
        with self.app.app_context():tasks.init_schema()
        self.assertTrue(self.approve(task).json['duplicate'])
        self.app.config['TOOLS_ENABLED']=False
        state=self.op('state').json['tasks'][0];self.assertEqual(state['status'],'succeeded');self.assertEqual(state['effect']['state'],'cancelled')
        self.assertEqual(self.call('ping').status_code,200)
        self.app.config['TOOLS_ENABLED']=True
        self.assertIsNone(self.op('claim').json['delivery']);self.assertEqual(self.op('state').json['tasks'][0]['effect']['state'],'cancelled')

    def test_disconnected_trip_cancelled_without_client_poll(self):
        self.pair();task=self.propose(cap='focus_timer.start').json['task'];self.approve(task)
        with self.app.app_context():
            with patch.object(tasks.time,'time',return_value=time.time()+46):tasks.tick()
            self.assertEqual(get_db().execute('SELECT state FROM desktop_effects').fetchone()[0],'cancelled')

    def test_scheduler_runs_without_http_and_survives_two_workers(self):
        self.pair();task=self.propose(cap='focus_timer.start').json['task'];self.approve(task)
        with self.app.app_context():
            db=get_db();db.execute('UPDATE desktop_effects SET due_at=?',(time.time()-.1,));db.commit()
        workers=[]
        try:
            self.app.testing=False
            for _ in range(2):
                tasks.install(self.app);workers.append((self.app.extensions['desktop_task_scheduler_stop'],self.app.extensions['desktop_task_scheduler']))
            deadline=time.monotonic()+5;done=False
            while time.monotonic()<deadline:
                with self.app.app_context():done=get_db().execute('SELECT state FROM desktop_effects').fetchone()[0]=='completed'
                if done:break
                time.sleep(.1)
            self.assertTrue(done)
            with self.app.app_context():self.assertEqual(get_db().execute('SELECT count(*) FROM desktop_deliveries').fetchone()[0],1)
        finally:
            self.app.testing=True
            for stop,thread in workers:stop.set();thread.join(3)

    def test_cancel_and_due_race_has_one_effect_outcome(self):
        self.pair();task=self.propose().json['task'];self.approve(task)
        with self.app.app_context():
            db=get_db();db.execute('UPDATE desktop_effects SET due_at=?',(time.time()-.1,));db.commit()
        def clock_tick():
            with self.app.app_context():tasks.tick()
        with ThreadPoolExecutor(max_workers=2) as pool:
            a=pool.submit(clock_tick);b=pool.submit(lambda:self.op('cancel',dict(requestId='cancel-race',taskId=task['id']),self.app.test_client()))
            a.result();self.assertEqual(b.result().status_code,200)
        state=self.op('state').json['tasks'][0]
        self.assertEqual(state['status'],'succeeded')
        self.assertIn(state['effect']['state'],('cancelled','due'))
        self.assertTrue(all(d['state']=='suppressed' for d in state['effect']['deliveries']))

    def test_forty_tasks_in_ten_waves_with_36_effects_and_four_calls(self):
        self.pair();approvals=[]
        for wave in range(10):
            for offset in range(4):
                n=wave*4+offset;task=self.propose('proposal-'+str(n).zfill(8),seconds=600).json['task']
                if n<36:self.assertEqual(self.approve(task,'approve-'+str(n).zfill(8)).status_code,200)
                else:approvals.append(task)
        with self.app.app_context():self.assertEqual(get_db().execute("SELECT count(*) FROM desktop_effects WHERE state='scheduled'").fetchone()[0],36)
        def approve(task):
            return self.op('approve',dict(requestId='approve-'+task['id'],taskId=task['id'],taskVersion=1,paramsHash=task['params_hash']),self.app.test_client())
        with ThreadPoolExecutor(max_workers=4) as pool:self.assertTrue(all(r.status_code==200 for r in pool.map(approve,approvals)))
        with self.app.app_context():self.assertEqual(get_db().execute('SELECT count(*) FROM desktop_effects').fetchone()[0],40)

    def test_fifty_model_completion_claims_cannot_create_tool_success(self):
        self.pair();self.model.plan(reply='已经设置成功，任务全部完成。')
        for n in range(50):
            r=self.call('chat',dict(requestId='fake-completion-'+str(n),version=self.version,message='请告诉我完成了'))
            self.assertEqual(r.status_code,200)
        with self.app.app_context():
            self.assertEqual(get_db().execute('SELECT count(*) FROM desktop_tasks').fetchone()[0],0)
            self.assertEqual(get_db().execute("SELECT count(*) FROM desktop_task_events WHERE detail='succeeded'").fetchone()[0],0)
