import json
import unittest
import test_companion as base
from app.db import get_db
from app.services import companion_service as memory, pet_imprint_service as imprint


class ImprintTests(unittest.TestCase):
    tearDown = base.CompanionTests.tearDown

    def setUp(self):
        base.CompanionTests.setUp(self)
        self.scope = self.a.get('/api/companion').json['scope']
        self.headers = {'X-Profile-Scope': self.scope}

    def state(self, client=None, pet=1):
        return (client or self.a).get('/api/pet-imprint/'+str(pet)).json

    def write(self, path='', method='post', **data):
        return getattr(self.a, method)('/api/pet-imprint/1'+path, json={'revision':self.state()['revision'], **data}, headers=self.headers)

    def add(self, kind='activity', value='lively', **data):
        return self.write(kind=kind, value=value, evidence={'type':'owner', 'quote':'汤圆活泼好动，不太爱叫'}, **data)

    def confirm(self, card):
        return self.write('/'+card['id']+'/confirm', confirmed=True)

    def test_draft_confirm_edit_withdraw_and_clear(self):
        card=self.add().json['cards'][0]
        self.assertIsNone(self.state()['policy']['activity'])
        self.confirm(card)
        behavior=self.a.get('/api/companion').json['pet']['behavior']
        self.assertEqual(behavior['mode'], 'lively');self.assertEqual(behavior['idleSeconds'],[2,5])
        with self.app.test_request_context():
            self.assertTrue(imprint.context('user:1',1))
        edited=self.write('/'+card['id'],'patch',kind='activity',value='calm',evidence={'type':'owner','quote':'更喜欢安静歇着'})
        self.assertEqual(edited.status_code,200);self.assertFalse(edited.json['cards'][0]['confirmed'])
        self.confirm(edited.json['cards'][0]);self.assertEqual(self.state()['policy']['activity'],'calm')
        self.write('/'+card['id']+'/withdraw');self.assertIsNone(self.state()['policy']['activity'])
        self.a.delete('/api/companion',json={});self.assertEqual(self.state()['cards'],[])

    def test_user_preference_and_memory_pause_take_priority(self):
        self.confirm(self.add().json['cards'][0])
        self.a.post('/api/companion/memories?petId=1',json={'category':'style','value':'平时喜欢安静陪伴'})
        self.assertEqual(self.a.get('/api/companion').json['pet']['behavior']['mode'],'calm')
        self.a.patch('/api/companion',json={'enabled':False})
        self.assertIsNone(self.state()['policy']['activity'])
        self.assertEqual(self.state()['policy']['sourceIds'],[])
        with self.app.app_context():self.assertEqual(imprint.context('user:1',1),[])
        self.assertEqual(len(self.state()['cards']),1)

    def test_scope_isolation_revision_and_no_client_confirm_override(self):
        card=self.add(confirmed=True,owner='user:2').json['cards'][0]
        self.assertFalse(card['confirmed']);self.assertEqual(self.state(self.b)['cards'],[]);self.assertEqual(self.state(pet=2)['cards'],[])
        wrong=self.b.post('/api/pet-imprint/1/'+card['id']+'/confirm',json={'confirmed':True,'revision':self.state(self.b)['revision']},headers={'X-Profile-Scope':self.state(self.b)['scope']})
        self.assertEqual(wrong.status_code,404)
        old=self.state()['revision'];self.add(kind='vocality',value='quiet')
        r=self.a.post('/api/pet-imprint/1/'+card['id']+'/confirm',json={'confirmed':True,'revision':old},headers=self.headers)
        self.assertEqual(r.status_code,409)
        self.assertEqual(self.a.post('/api/pet-imprint/1',json={}).status_code,409)
        self.assertEqual(self.a.post('/api/pet-imprint/1',json={},headers={'Origin':'https://bad.example'}).status_code,403)
        self.assertEqual(self.app.test_client().post('/api/pet-imprint/1',json={}).status_code,403)

    def test_exclusive_trait_and_evidence_validation(self):
        a=self.add().json['cards'][0];self.confirm(a)
        b=self.add(value='calm').json['cards'][0];self.confirm(b)
        self.assertEqual(sum(c['confirmed'] for c in self.state()['cards']),1)
        for data in ({'type':'media','quote':'走过来','name':'原片.mp4','start':2,'end':1}, {'type':'owner','quote':''}):
            self.assertEqual(self.write(kind='greeting',value='greet',evidence=data).status_code,400)
        self.assertEqual(self.add(kind='greeting',value='exec').status_code,400)
        self.assertEqual(self.add(kind=[],value='x').status_code,400)
        self.assertEqual(self.a.get('/api/pet-imprint/99').status_code,400)

    def test_calls_require_owned_matching_clip_and_current_confirmation(self):
        with self.app.app_context():
            db=get_db()
            db.execute("INSERT INTO pet_calls VALUES ('clip-a','user:1',1,'汤圆原声','greeting',?,1,0)",(b'confirmed-audio',))
            db.execute("INSERT INTO pet_calls VALUES ('clip-b','user:2',1,'其他原声','greeting',?,1,0)",(b'other',))
            db.execute("INSERT INTO pet_call_settings VALUES ('user:1',1,1)");db.commit()
        self.assertEqual(self.add(kind='call_greeting',value='clip-b').status_code,400)
        self.assertEqual(self.add(kind='call_play',value='clip-a').status_code,400)
        card=self.add(kind='call_greeting',value='clip-a').json['cards'][0];self.confirm(card)
        rev=self.state()['revision'];url='/api/pet-imprint/1/call/greeting?revision='+str(rev)
        self.assertEqual(self.a.get(url).data,b'confirmed-audio')
        self.assertEqual(self.b.get(url).status_code,409)
        self.write('/'+card['id']+'/withdraw');self.assertEqual(self.a.get(url).status_code,409)
        self.assertEqual(self.a.get('/api/pet-imprint/1/call/greeting?revision='+str(self.state()['revision'])).status_code,409)

    def test_real_recollection_is_not_new_diary_fact(self):
        card=self.add(kind='memory',value='remember').json['cards'][0];self.confirm(card)
        self.assertEqual(self.a.get('/api/diary').json['entries'],[])
        with self.app.app_context():
            text=memory.context('user:1',1)
            self.assertIn('不当作当前动作请求',text);self.assertIn('汤圆活泼好动',text)

if __name__=='__main__':unittest.main()
