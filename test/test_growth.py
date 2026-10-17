"""Growth lifecycle uses an isolated DB and virtual time, never real owner records."""
import base64
import io
import tempfile
import time
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from app import create_app
from app.config import Config
from app.db import get_db
from app.services import growth_service as growth, diary_service as diary

class GrowthTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        class C(Config):
            TESTING=True
            DATABASE_PATH=str(Path(self.tmp.name)/'growth.sqlite')
            SECRET_KEY='growth-test'
        self.config=C;self.app=create_app(C)
        with self.app.app_context():
            db=get_db();db.executescript(Path(Config.SCHEMA_PATH).read_text(encoding='utf-8'))
        self.a=self.app.test_client();self.b=self.app.test_client()
        self.scope=self.a.get('/api/companion').json['scope'];self.b.get('/api/companion')
        with self.a.session_transaction() as s:self.owner='guest:'+s['companion_guest']
    def tearDown(self):self.tmp.cleanup()
    def call(self,path='',method='get',data=None,pet=3):
        return getattr(self.a,method)('/api/growth/'+str(pet)+path,json=data,headers={'X-Profile-Scope':self.scope})
    def enroll(self,pet=3,**extra):
        return self.call(method='post',pet=pet,data={'mode':'adopt','name':'小棉花','personality':'careful',**extra})
    def test_adoption_calendar_certificate_and_existing_pet_optin(self):
        self.assertFalse(self.call().json['enrolled'])
        d=self.enroll().json
        self.assertEqual(d['profile']['birthday'],growth.months_after(growth.today(),-3).isoformat())
        self.assertNotEqual(d['profile']['birthday'],d['profile']['adopted'])
        self.assertEqual(d['appearance']['stage'],'幼年');self.assertGreaterEqual(d['appearance']['scale'],.72)
        self.assertEqual(len(d['memories']),1);self.assertEqual(d['traits']['trustDays'],0)
        self.assertEqual(self.enroll().status_code,400)
        dog=self.enroll(pet=1).json;self.assertNotEqual(dog['profile']['certificate'],d['profile']['certificate'])
        self.assertEqual(len(self.a.get('/api/diary').json['entries']),2)
        self.assertIn('我是小棉花',self.a.get('/api/diary').json['entries'][0]['body'])
    def test_real_dates_edit_and_leap_calendar(self):
        d=self.enroll(mode='real',birthday='2020-02-29',adopted='2020-05-01',estimated=True,likes='喜欢纸箱',breed='英短').json
        self.assertEqual(d['appearance']['stage'],'成年');self.assertEqual(d['appearance']['scale'],1)
        self.assertEqual(len(d['memories']),1,'do not fabricate earlier memories')
        self.assertEqual(growth.months_after(date(2020,2,29),12),date(2021,2,28))
        payload={**d['profile'],'name':'小白','estimated':True}
        self.assertEqual(self.call(method='patch',data=payload).json['profile']['certificate'],d['profile']['certificate'])
        self.assertEqual(self.a.get('/api/companion?petId=3').json['pet']['name'],'小白')
        self.assertEqual(self.call(method='patch',data={**payload,'personality':'curious'}).status_code,400)
    def test_invalid_input_scope_and_account_isolation(self):
        self.assertEqual(self.enroll(personality=[]).status_code,400)
        self.assertEqual(self.enroll(name='<x>'*20).status_code,400)
        self.assertEqual(self.enroll(mode='real',birthday='2999-01-01',adopted='2026-01-01').status_code,400)
        self.assertEqual(self.a.post('/api/growth/3',json={}).status_code,409)
        self.assertEqual(self.a.post('/api/growth/3',json={},headers={'Origin':'https://evil.test'}).status_code,403)
        d=self.enroll().json
        self.assertFalse(self.b.get('/api/growth/3').json['enrolled'])
        self.assertEqual(self.b.get(d['memories'][0]['image']).status_code,404)
        self.assertEqual(self.call(pet=99).status_code,400)
    def test_factual_firsts_daily_learning_and_inactivity_no_penalty(self):
        d=self.enroll().json;now=time.time()+2
        with self.app.app_context():
            db=get_db()
            with db:
                for i in range(12):diary.record(db,self.owner,3,'touch:'+str(i),'interaction','pet',now=now)
            self.assertEqual(growth.state(self.owner,3)['traits']['trustDays'],1)
            with db:
                for i in (1,2):diary.record(db,self.owner,3,'next:'+str(i),'interaction','pet',now=now+i*86400)
                for i in range(3):diary.record(db,self.owner,3,'place:'+str(i),'explore','温室窗边',now=now+i*86400)
            current=growth.state(self.owner,3)
            self.assertEqual(current['traits']['trustDays'],3);self.assertEqual(current['traits']['favoritePlace'],'温室窗边')
            self.assertEqual(len([m for m in current['memories'] if m['key']=='first:pet']),1)
            with patch.object(growth,'today',return_value=growth.today()+timedelta(days=60)):
                later=growth.state(self.owner,3)
            self.assertEqual(later['traits']['trustDays'],3)
            self.assertGreater(later['appearance']['scale'],current['appearance']['scale'])
    def test_anniversary_idempotency_and_diary_shared_event(self):
        self.enroll();future=growth.today()+timedelta(days=101)
        with self.app.app_context(),patch.object(growth,'today',return_value=future):
            first=growth.state(self.owner,3);second=growth.state(self.owner,3)
            self.assertEqual(first['memories'],second['memories'])
            m=next(m for m in first['memories'] if m['key']=='node:100')
            page=get_db().execute('SELECT body FROM pet_diary_days WHERE owner=? AND day=?',(self.owner,m['day'])).fetchone()
            self.assertIn(m['story'],page['body'])
    def test_optout_and_forget_cover_growth_and_photos(self):
        self.enroll();self.a.patch('/api/companion',json={'enabled':False})
        self.a.post('/api/diary/events',json={'petId':3,'kind':'pet'},headers={'X-Profile-Scope':self.scope})
        self.assertEqual(len(self.call().json['memories']),1)
        self.a.delete('/api/companion',json={});self.assertFalse(self.call().json['enrolled'])
        with self.app.app_context():self.assertEqual(get_db().execute('SELECT COUNT(*) FROM pet_growth_memories').fetchone()[0],0)
    def test_photo_validation_preferences_and_age_limit(self):
        d=self.enroll().json;m=d['memories'][0];path='/memories/'+str(m['id'])+'/photo'
        self.assertEqual(self.call(path,'post',{'image':'invalid'}).status_code,400)
        b=io.BytesIO();Image.new('RGB',(600,400),'green').save(b,'JPEG');image=base64.b64encode(b.getvalue()).decode()
        self.call('/preferences','patch',{'autoPhoto':False})
        self.assertEqual(self.call(path,'post',{'image':image}).status_code,409)
        self.call('/preferences','patch',{'autoPhoto':True,'haptics':2,'ambient':'rain'})
        self.assertEqual(self.call(path,'post',{'image':image}).status_code,200)
        self.assertEqual(self.a.get(m['image']).mimetype,'image/jpeg')
        self.assertEqual(self.call('/preferences','patch',{'haptics':99}).status_code,400)
        self.assertEqual(self.call('/preferences','patch',{'sound':'yes'}).status_code,400)
    def test_growth_page_and_explicit_preference_wins(self):
        self.assertEqual(self.a.get('/growth').status_code,200);self.enroll()
        self.assertEqual(self.a.get('/api/companion?petId=3').json['pet']['behavior']['mode'],'calm')
        self.a.post('/api/companion/memories?petId=3',json={'category':'style','value':'活泼一点，多走动'})
        self.assertEqual(self.a.get('/api/companion?petId=3').json['pet']['behavior']['mode'],'lively')

if __name__=='__main__':unittest.main()
