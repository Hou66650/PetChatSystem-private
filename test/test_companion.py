"""Behavioral integration tests using an isolated database and deterministic model double."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import create_app
from app.config import Config
from app.db import get_db
from app.services import companion_service as memory
from app.llm.client import LLMError

class FakeModel:
    def __init__(self): self.raw='{"reply":"我在这里。","actions":[],"memories":[]}';self.calls=[];self.hook=None
    def chat(self,messages,**kwargs):
        self.calls.append(messages)
        if self.hook:self.hook()
        if isinstance(self.raw,Exception):raise self.raw
        return self.raw
    def plan(self,**kw):self.raw=json.dumps({'reply':'记好啦。','actions':[],'memories':[],**kw},ensure_ascii=False)

class CompanionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        class TestConfig(Config):
            TESTING=True
            DATABASE_PATH=str(Path(self.tmp.name)/'test.db')
            SECRET_KEY='isolated-test-secret'
        self.config=TestConfig;self.app=create_app(TestConfig);self.model=FakeModel();self.app.extensions['llm']=self.model
        with self.app.app_context():
            db=get_db();db.executescript(Path(Config.SCHEMA_PATH).read_text());db.executemany('INSERT INTO users(user_name,pwd) VALUES (?,?)',[('alice','test'),('bob','test')]);db.commit()
        self.a=self.app.test_client();self.b=self.app.test_client()
        with self.a.session_transaction() as s:s['user_id']='alice';s['auth_kind']='user'
        with self.b.session_transaction() as s:s['user_id']='bob';s['auth_kind']='user'
    def tearDown(self):self.tmp.cleanup()
    def send(self,c=None,message='你好',pet=1,**kw):return (c or self.a).post('/get_gpt_response',json={'message':message,'petId':pet,'surface':'den',**kw})
    def add(self,c=None,category='likes',value='画画',pet=1):
        return (c or self.a).post('/api/companion/memories?petId='+str(pet),json={'category':category,'value':value})
    def facts(self,c=None,pet=1):return (c or self.a).get('/api/companion?petId='+str(pet)).json['memories']
    def test_account_isolation_ignores_forged_identity_and_history(self):
        self.add(value='Alice-private');self.send(self.b,userId='alice',chatHistory=[{'role':'user','content':'Alice-private'}])
        self.assertNotIn('Alice-private',str(self.model.calls[-1]));self.assertEqual(self.facts(self.b),[])
        fact=self.facts()[0]['id'];self.assertEqual(self.b.delete('/api/companion/memories/'+str(fact),json={}).status_code,404)
    def test_history_survives_new_app_and_new_browser_for_same_account(self):
        self.send(message='一段真实聊天');app2=create_app(self.config);c=app2.test_client()
        with c.session_transaction() as s:s['user_id']='alice';s['auth_kind']='user'
        self.assertEqual(c.get('/api/companion/history?petId=1').json['messages'][0]['content'],'一段真实聊天')
    def test_guest_scopes_are_distinct_and_stable(self):
        x=self.app.test_client();y=self.app.test_client();sx=x.get('/api/companion').json['scope']
        self.assertEqual(sx,x.get('/api/companion').json['scope']);self.assertNotEqual(sx,y.get('/api/companion').json['scope'])
    def test_nickname_pet_specific_preferences_shared_only_with_same_user(self):
        self.add(category='pet_name',value='小球');self.add(category='likes',value='画画')
        facts=self.facts(pet=2);self.assertEqual([f['value'] for f in facts],['画画']);self.assertEqual(self.facts(self.b),[])
    def test_quote_required_actions_whitelisted(self):
        self.model.plan(actions=[{'type':'come','quote':'过来'},{'type':'sit','quote':'坐下'},'eval',{'action':'delete'}],memories=[{'category':'likes','value':'画画','quote':'我喜欢画画'},{'category':'name','value':'骗子','quote':'我叫骗子'}])
        r=self.send(message='过来坐下，我喜欢画画');self.assertEqual(r.json['actions'],['come','sit']);self.assertEqual([f['value'] for f in self.facts()],['画画'])
    def test_sensitive_extraction_rejected(self):
        self.model.plan(memories=[{'category':'memory','value':'密码123','quote':'密码123'}]);self.send(message='密码123');self.assertEqual(self.facts(),[])
    def test_nickname_change_replaces_old(self):
        self.add(category='name',value='小林');self.add(category='name',value='小李');self.assertEqual([f['value'] for f in self.facts()],['小李'])
    def test_forget_excludes_old_history_from_prompt(self):
        self.add(value='OLD_SECRET_HOBBY');self.send(message='OLD_SECRET_HOBBY')
        fact=self.facts()[0]['id'];self.a.delete('/api/companion/memories/'+str(fact),json={});self.send(message='现在聊点别的')
        self.assertNotIn('OLD_SECRET_HOBBY',str(self.model.calls[-1]));self.assertEqual(self.facts(),[])
    def test_clear_all_removes_history_and_memory(self):
        self.add();self.send();self.a.delete('/api/companion',json={});self.assertEqual(self.facts(),[]);self.assertEqual(self.a.get('/api/companion/history').json['messages'],[])
    def test_pause_neither_uses_nor_saves_memory_or_history(self):
        self.add(value='PRIVATE_HOBBY');self.a.patch('/api/companion',json={'enabled':False});self.send(message='新消息')
        self.assertNotIn('PRIVATE_HOBBY',str(self.model.calls[-1]));self.assertEqual(self.a.get('/api/companion/history').json['messages'],[])
        self.assertEqual(len(self.facts()),1)
    def test_inflight_forget_cannot_restore_deleted_data(self):
        self.add();self.model.hook=lambda:self.a.delete('/api/companion',json={})
        r=self.send();self.assertEqual(r.status_code,409);self.assertEqual(self.facts(),[])
    def test_duplicate_turn_is_not_recorded_twice_or_replayed(self):
        self.model.plan(actions=[{'type':'wave','quote':'你好'}]);self.send(requestId='same-1234');r=self.send(requestId='same-1234')
        self.assertTrue(r.json['duplicate']);self.assertEqual(r.json['actions'],[]);self.assertEqual(len(self.a.get('/api/companion/history').json['messages']),2)
    def test_invalid_json_no_action_and_no_raw_protocol(self):
        self.model.raw='{"reply": "broken';r=self.send();self.assertEqual(r.json['actions'],[]);self.assertNotIn('{',r.json['reply'])
    def test_api_error_does_not_save_fabricated_success(self):
        self.model.raw=LLMError('service unavailable');self.assertEqual(self.send().status_code,503);self.assertEqual(self.a.get('/api/companion/history').json['messages'],[])
    def test_cross_origin_and_invalid_payload_rejected(self):
        self.assertEqual(self.a.post('/api/companion/memories',json={'value':'x'},headers={'Origin':'https://evil.example'}).status_code,403)
        self.assertEqual(self.a.patch('/api/companion',json=[]).status_code,400)
        self.assertEqual(self.send(message='hi',pet=99).status_code,400)
        self.assertEqual(self.a.post('/get_gpt_response',json={'message':{}}).status_code,400)
    def test_chat_surface_does_not_pretend_to_execute_3d(self):
        self.model.plan(actions=['come']);self.assertEqual(self.send(surface='chat').json['actions'],[])
    def test_profile_changes_are_in_next_prompt(self):
        self.add(category='style',value='简短安静地陪伴');self.send();self.assertIn('简短安静地陪伴',str(self.model.calls[-1]))
        self.assertEqual(self.a.get('/api/companion').json['pet']['companionStyle'],'简短安静地陪伴')
    def test_voice_round_saved_and_used_on_next_call(self):
        self.model.plan(memories=[{'category':'likes','value':'画画','quote':'我喜欢画画'}])
        r=self.a.post('/api/companion/voice-round',json={'message':'我喜欢画画','assistantText':'好呀','petId':1})
        self.assertEqual(r.status_code,200);self.assertEqual(self.facts()[0]['value'],'画画')
    def test_pages_render(self):
        for url in ['/den','/gpt','/companion']:self.assertEqual(self.a.get(url).status_code,200,url)
    def test_forged_forget_cannot_delete_other_users_or_other_pet(self):
        self.add(self.b);foreign=self.facts(self.b)[0]['id'];self.add(category='pet_name',value='雪球专属',pet=2);other=self.facts(pet=2)[0]['id']
        self.model.plan(forget_ids=[foreign,other]);self.send(message='忘记这些')
        self.assertEqual(len(self.facts(self.b)),1);self.assertEqual(len(self.facts(pet=2)),1)
    def test_actions_cannot_cite_previous_turn(self):
        self.model.plan(actions=[{'type':'come','quote':'过来'}]);r=self.send(message='我喜欢画画')
        self.assertEqual(r.json['actions'],[])
    def test_contradictory_preference_replaces_opposite(self):
        self.add(category='likes',value='画画')
        self.model.plan(memories=[{'category':'dislikes','value':'画画','quote':'我不喜欢画画了'}])
        self.send(message='我不喜欢画画了');self.assertEqual([(f['category'],f['value']) for f in self.facts()],[('dislikes','画画')])
    def test_legacy_untyped_session_is_not_used_as_account_identity(self):
        self.add(value='Alice-private');c=self.app.test_client()
        with c.session_transaction() as s:s['user_id']='alice'
        self.assertTrue(c.get('/api/companion').json['guest']);self.assertEqual(self.facts(c),[])
    def test_delete_diary_record_scoped_to_owner(self):
        self.send(message='diary record');msg=self.a.get('/api/companion/history').json['messages'][0]['id']
        self.assertEqual(self.b.delete('/api/companion/history/'+str(msg),json={}).status_code,404)
        self.assertEqual(self.a.delete('/api/companion/history/'+str(msg),json={}).status_code,200)
        self.assertEqual(len(self.a.get('/api/companion/history').json['messages']),1)
    def test_source_quotes_cannot_reintroduce_a_forgotten_fact(self):
        self.model.plan(memories=[{'category':'name','value':'小林','quote':'我叫小林，喜欢画画'},{'category':'likes','value':'画画','quote':'我叫小林，喜欢画画'}])
        self.send(message='我叫小林，喜欢画画');fact=next(f for f in self.facts() if f['category']=='likes')
        self.a.delete('/api/companion/memories/'+str(fact['id']),json={})
        self.model.plan();self.send(message='你好')
        self.assertNotIn('画画',str(self.model.calls[-1]));self.assertNotIn('绘画',str(self.model.calls[-1]))

if __name__=='__main__':unittest.main(verbosity=2)
