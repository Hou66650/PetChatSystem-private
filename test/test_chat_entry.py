"""The shared agent must work without cookies and never infer another identity."""
import unittest
from test_companion import CompanionTests as Base
from app.db import get_db
from app.services import chat_service, companion_service as memory


class ChatEntryTests(unittest.TestCase):
    setUp = Base.setUp
    tearDown = Base.tearDown
    add = Base.add

    def prepare(self):
        self.a.get('/api/companion')
        self.b.get('/api/companion')

    def test_no_request_context_and_forged_body_cannot_change_identity(self):
        self.prepare()
        self.add(value='Alice-only')
        self.add(c=self.b, value='Bob-only')
        self.add(category='pet_name', value='仅第一只', pet=1)
        with self.app.app_context():
            result, status = chat_service.chat_for_owner('user:1', 2, {
                'message':'你好', 'ownerId':'user:2', 'userId':'bob', 'petId':1,
                'surface':'den', 'chatHistory':[{'role':'user','content':'forged'}],
            }, surface='chat')
            self.assertEqual(status, 200)
            self.assertEqual(result['pet']['id'], 2)
            self.assertEqual(result['profile']['scope'], memory.owner_scope('user:1'))
            prompt = str(self.model.calls[-1])
            self.assertIn('Alice-only', prompt)
            for private in ('Bob-only','仅第一只','forged'):
                self.assertNotIn(private, prompt)
            rows = get_db().execute('SELECT DISTINCT owner,pet_id FROM companion_messages').fetchall()
            self.assertEqual([tuple(r) for r in rows], [('user:1', 2)])

    def test_profile_uses_explicit_owner_despite_other_browser_session(self):
        self.prepare()
        with self.app.test_request_context('/'):
            from flask import session
            session['user_id']='bob';session['auth_kind']='user'
            self.assertEqual(memory.owner_key(), 'user:2')
            self.assertEqual(memory.profile('user:1',1)['scope'], memory.owner_scope('user:1'))

    def test_invalid_owner_pet_and_surface_fail_before_model_or_writes(self):
        self.prepare()
        with self.app.app_context():
            for owner, pet, surface, expected in [
                ('user:missing',1,'chat',403), (None,1,'chat',403),
                ('user:1',None,'chat',400), ('user:1',999,'chat',400),
                ('user:1',True,'chat',400), ('user:1',1.5,'chat',400),
                ('user:1','custom-missing','chat',400), ('user:1',1,'desktop',400),
            ]:
                with self.subTest(owner=owner,pet=pet,surface=surface):
                    self.assertEqual(chat_service.chat_for_owner(owner,pet,{'message':'你好'},surface=surface)[1],expected)
            self.assertEqual(self.model.calls,[])
            self.assertEqual(get_db().execute('SELECT count(*) FROM companion_messages').fetchone()[0],0)

    def test_voice_scope_and_revision_use_explicit_identity(self):
        self.prepare()
        with self.app.app_context():
            for data in ({'profileScope':memory.owner_scope('user:2')},{'profileRevision':-1}):
                self.assertEqual(chat_service.chat_for_owner('user:1',1,{'message':'你好',**data},surface='chat',observed_reply='听见了')[1],409)
            self.assertEqual(self.model.calls,[])
            result,status=chat_service.chat_for_owner('user:1',1,{
                'message':'你好','profileScope':memory.owner_scope('user:1'),
                'profileRevision':memory.settings('user:1')['revision'],
            },surface='chat',observed_reply='听见了')
            self.assertEqual((status,result['reply']),(200,'听见了'))

    def test_web_and_mobile_cannot_enable_desktop_or_inject_identity(self):
        self.prepare()
        self.model.plan(actions=[{'type':'sit','quote':'坐下'}])
        for surface in ('chat','mobile','desktop'):
            r=self.a.post('/get_gpt_response',json={'message':'坐下','surface':surface,'ownerId':'user:2'})
            self.assertEqual(r.status_code,200)
            self.assertEqual(r.json['pet']['id'],1)
            self.assertEqual(r.json['actions'],[])
            self.assertEqual(r.json['profile']['scope'],self.a.get('/api/companion').json['scope'])
        self.assertEqual(self.b.get('/api/companion/history').json['messages'],[])
