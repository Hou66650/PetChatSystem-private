"""Daily journal integration, isolated DB: no real account records or model calls."""
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from app import create_app
from app.config import Config
from app.db import get_db
from app.services import diary_service as diary, cat_agent_service as agent


class DiaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        class TestConfig(Config):
            TESTING=True
            SECRET_KEY='diary-isolated-test'
            DATABASE_PATH=str(Path(self.tmp.name)/'diary.db')
        self.config=TestConfig;self.app=create_app(TestConfig)
        with self.app.app_context():
            db=get_db();db.executescript(Path(Config.SCHEMA_PATH).read_text(encoding='utf-8'))
            db.executemany('INSERT INTO users(user_name,pwd) VALUES (?,?)',[('alice','x'),('bob','x')]);db.commit()
            self.owner='user:'+str(db.execute("SELECT user_id FROM users WHERE user_name='alice'").fetchone()[0])
        self.a=self.app.test_client();self.b=self.app.test_client()
        for c,name in [(self.a,'alice'),(self.b,'bob')]:
            with c.session_transaction() as s:s['user_id']=name;s['auth_kind']='user'
            c.get('/api/companion')
        self.scope=self.a.get('/api/companion').json['scope']

    def tearDown(self):self.tmp.cleanup()

    def event(self,kind='pet',pet=3,**extra):
        return self.a.post('/api/diary/events',json=dict(kind=kind,petId=pet,**extra),headers={'X-Profile-Scope':self.scope})

    def pair(self,date='2026-10-16T16:30:00Z',request='chat-one',pet=3):
        with self.app.app_context():
            db=get_db()
            with db:
                for role,text in [('user','今天工作很开心，私密原句不要复制'),('assistant','我陪你呀')]:
                    db.execute('INSERT INTO companion_messages(owner,pet_id,role,content,request_id,created_at) VALUES (?,?,?,?,?,?)', (self.owner,pet,role,text,request,date))

    def test_daily_first_person_timezone_pet_isolation_and_restart(self):
        self.pair()
        with self.app.app_context():
            db=get_db()
            with db:
                diary.record(db,self.owner,3,'completed-1','explore','窗边',datetime.fromisoformat('2026-10-17T02:00:00+00:00').timestamp())
                diary.record(db,self.owner,3,'completed-2','explore','花园步道',datetime.fromisoformat('2026-10-17T03:00:00+00:00').timestamp())
                diary.record(db,self.owner,1,'dog-1','visit',now=datetime.fromisoformat('2026-10-17T03:00:00+00:00').timestamp())
        entries=self.a.get('/api/diary').json['entries'];self.assertEqual(len(entries),2)
        cat=next(e for e in entries if e['petId']==3)
        self.assertEqual(cat['day'],'2026-10-17');self.assertIn('我是团子',cat['body']);self.assertIn('窗边、花园步道',cat['body']);self.assertIn('聊了1轮',cat['body']);self.assertNotIn('私密原句',cat['body'])
        self.assertNotIn('花园步道',next(e for e in entries if e['petId']==1)['body'])
        self.assertEqual(self.a.get('/api/diary').json['entries'],entries,'refresh is idempotent')
        self.assertEqual(self.b.get('/api/diary').json['entries'],[])
        c=create_app(self.config).test_client()
        with c.session_transaction() as s:s['user_id']='alice';s['auth_kind']='user'
        self.assertEqual(c.get('/api/diary').json['entries'],entries)

    def test_completed_exploration_only_and_duplicate_reports(self):
        target=next(iter(agent.TARGETS));action=agent.TARGETS[target]['actions'][0]
        data=dict(target=target,action=action,event='test-event-001',result='blocked')
        self.a.post('/api/cat-agent/report',json=data,headers={'X-Profile-Scope':self.scope})
        self.assertEqual(self.a.get('/api/diary').json['entries'],[])
        data.update(event='test-event-002',result='completed')
        for _ in range(2):
            r=self.a.post('/api/cat-agent/report',json=data,headers={'X-Profile-Scope':self.scope});self.assertEqual(r.status_code,200,r.json)
        page=self.a.get('/api/diary').json['entries'];self.assertEqual(len(page),1);self.assertIn(agent.TARGETS[target]['name'],page[0]['body'])
        with self.app.app_context():self.assertEqual(get_db().execute("SELECT COUNT(*) FROM pet_diary_facts WHERE kind='explore'").fetchone()[0],1)

    def test_delete_diary_keeps_chat_and_does_not_regenerate(self):
        self.pair();entry=self.a.get('/api/diary').json['entries'][0];url=f"/api/diary/3/{entry['day']}"
        self.assertEqual(self.b.delete(url,json={}).status_code,404)
        self.assertEqual(self.a.delete(url,json={}).status_code,200)
        self.assertEqual(len(self.a.get('/api/companion/history').json['messages']),2)
        self.assertEqual(self.a.get('/api/diary').json['entries'],[])
        with self.app.app_context():
            with get_db():self.assertFalse(diary.record(get_db(),self.owner,3,'new-that-day','explore','秘密角落',datetime.fromisoformat('2026-10-17T06:00:00+00:00').timestamp()))

    def test_interactions_validation_optout_and_forget(self):
        self.assertEqual(self.event().status_code,200);self.event();self.event(kind='feed',owner='user:bob')
        body=self.a.get('/api/diary').json['entries'][0]['body'];self.assertEqual(body.count('轻轻摸了摸我'),1);self.assertIn('亲手喂了我',body)
        self.assertEqual(self.event(kind='<script>').status_code,400)
        self.assertEqual(self.event(pet=True).status_code,400)
        self.assertEqual(self.a.post('/api/diary/events',json={'petId':3,'kind':'pet'},headers={'Origin':'https://evil.test'}).status_code,403)
        self.a.patch('/api/companion',json={'enabled':False})
        self.event(kind='game');self.assertNotIn('小游戏',self.a.get('/api/diary').json['entries'][0]['body'])
        self.a.delete('/api/companion',json={});self.assertEqual(self.a.get('/api/diary').json['entries'],[])

    def test_history_deletion_removes_derived_chat_but_keeps_other_facts(self):
        self.pair();self.a.get('/api/diary')
        message=self.a.get('/api/companion/history').json['messages'][0]['id']
        self.a.delete('/api/companion/history/'+str(message),json={})
        self.assertEqual(self.a.get('/api/diary').json['entries'],[])

    def test_pagination_keeps_whole_days_and_unknown_dates_are_not_invented(self):
        with self.app.app_context():
            db=get_db()
            with db:
                for i in range(32):
                    for pet in (1,3):diary.record(db,self.owner,pet,f'page-{i}-{pet}','visit',now=1700000000+i*86400)
        first=self.a.get('/api/diary').json;self.assertEqual(len(first['entries']),60)
        second=self.a.get('/api/diary?before='+first['nextBefore']).json;self.assertEqual(len(second['entries']),4)
        self.assertFalse({(e['day'],e['petId']) for e in first['entries']} & {(e['day'],e['petId']) for e in second['entries']})
        self.pair(date='not-a-date',request='undated');self.assertEqual(len(self.a.get('/api/diary').json['entries']),60)
        self.assertEqual(self.a.get('/api/diary?before=nonsense').status_code,400)
        export=self.a.post('/get-diary',json={'chatHistory':[{'message':'FORGED'}]}).json
        self.assertNotIn('FORGED',export['text']);self.assertIn('我的',export['text'])

    def test_deleted_assistant_does_not_leave_completed_chat_in_diary(self):
        self.pair();self.a.get('/api/diary')
        message=next(m for m in self.a.get('/api/companion/history').json['messages'] if m['role']=='assistant')
        self.a.delete('/api/companion/history/'+str(message['id']),json={})
        self.assertEqual(self.a.get('/api/diary').json['entries'],[])

    def test_new_chat_uses_nickname_from_same_turn(self):
        from app.services import companion_service as memory
        with self.app.app_context():
            plan={'reply':'记住啦','forget_ids':[],'memories':[{'category':'pet_name','value':'小棉花','quote':'叫你小棉花'}]}
            self.assertTrue(memory.save_turn(self.owner,3,'rename-turn','叫你小棉花',plan,memory.settings(self.owner)['revision']))
        self.assertIn('我是小棉花',self.a.get('/api/diary').json['entries'][0]['body'])


if __name__=='__main__':unittest.main()
