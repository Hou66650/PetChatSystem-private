import json
import unittest
from unittest.mock import patch
from test_companion import CompanionTests as Base
from app.services import portal_service as portal
from app.db import get_db

class PortalTests(unittest.TestCase):
    setUp=Base.setUp
    tearDown=Base.tearDown
    def post(self,op,data,c=None):
        c=c or self.a;scope=c.get('/api/portals').json['scope']
        return c.post('/api/portals/'+op,json=data,headers={'X-Profile-Scope':scope})
    def friends(self):
        code=self.post('invite',{},self.b).json['code'];self.assertEqual(self.post('friend',{'code':code}).status_code,200)
        self.post('settings',{'pet':'1','allow':True},self.b)
        return self.b.get('/api/portals').json['islands'][0]['id']
    def start(self,kind='desktop',**kw):return self.post('depart',dict(pet='3',kind=kind,confirmed=True,**kw))
    def test_friend_and_journey_public_ids(self):
        self.assertEqual(self.a.get('/api/portals').json['userId'],'1')
        self.assertEqual(self.b.get('/api/portals').json['userId'],'2')
        guest=self.app.test_client().get('/api/portals').json
        self.assertIsNone(guest['userId'])
        self.assertEqual(guest['friends'],[])
        dest=self.friends()
        self.assertEqual({f['userId'] for f in self.a.get('/api/portals').json['friends']},{'2'})
        self.assertEqual({f['userId'] for f in self.b.get('/api/portals').json['friends']},{'1'})
        tid=self.start('neighbor',destination=dest).json['trip']
        for client in (self.a,self.b):
            trip=client.get('/api/portals/trip/'+tid).json
            self.assertEqual((trip['visitorId'],trip['hostId']),('1','2'))
        self.assertEqual(self.app.test_client().get('/api/portals/trip/'+tid).status_code,404)

    def test_consent_csrf_and_exclusive_world(self):
        self.assertEqual(self.a.post('/api/portals/depart',json={}).status_code,409)
        self.assertEqual(self.post('depart',dict(pet='3',kind='desktop',confirmed=False)).status_code,400)
        first=self.start();self.assertEqual(first.status_code,200)
        self.assertEqual(self.start().status_code,409)
        self.assertEqual(self.post('return',{'trip':first.json['trip']},self.b).status_code,404)
        self.assertEqual(self.post('return',{'trip':first.json['trip']}).status_code,200)
        self.assertEqual(self.a.get('/api/portals').json['rewards'],[],'unpaired trip earns nothing')
    def test_pair_once_scoped_token_and_idempotent_reward(self):
        d=self.start().json
        r=self.a.post('/api/portals/desktop/pair',json={'code':d['code']});self.assertEqual(r.status_code,200)
        self.assertEqual(self.a.post('/api/portals/desktop/pair',json={'code':d['code']}).status_code,403)
        auth={'Authorization':'Bearer '+r.json['token']}
        self.a.post('/api/portals/desktop/ready',json={},headers=auth)
        self.post('depart-complete',{'trip':d['trip']})
        self.a.post('/api/portals/desktop/arrived',json={},headers=auth)
        self.assertEqual(self.b.get('/api/portals/trip/'+d['trip']).status_code,404)
        payload={'snapshot':{'visitor':{'x':.5,'z':.8,'action':'walk'}},'events':[{'id':'event-000001','kind':'walk','x':.5,'z':.8}]}
        for _ in range(2):self.assertEqual(self.a.post('/api/portals/desktop/sample',json=payload,headers=auth).status_code,200)
        trip=self.a.get('/api/portals/trip/'+d['trip']).json;self.assertEqual(len(trip['events']),1)
        self.assertEqual(self.post('sample',dict(trip=d['trip'],**payload)).status_code,403)
        self.a.post('/api/portals/desktop/return',json={},headers=auth)
        self.post('return',{'trip':d['trip']})
        self.assertEqual(len(self.a.get('/api/portals').json['rewards']),1)
        self.assertEqual(self.a.get('/api/portals/desktop/state',headers=auth).status_code,409)
    def test_visitors_default_closed_revocation_and_host_permissions(self):
        dest=self.friends();self.post('settings',{'pet':'1','allow':False},self.b)
        self.assertEqual(self.start('neighbor',destination=dest).status_code,403)
        self.post('settings',{'pet':'1','allow':True},self.b)
        d=self.start('neighbor',destination=dest).json
        self.assertEqual(self.b.get('/api/portals/trip/'+d['trip']).status_code,200)
        self.assertEqual(self.post('depart',dict(pet='1',kind='desktop',confirmed=True),self.b).status_code,409)
        self.assertEqual(self.post('message',dict(trip=d['trip'],text='<script>hello</script>'),self.b).status_code,200)
        self.assertEqual(self.post('sample',dict(trip=d['trip']),self.b).status_code,404)
        self.post('settings',{'pet':'1','allow':False},self.b)
        self.assertEqual(self.a.get('/api/portals/trip/'+d['trip']).json['status'],'returned')

    def test_desktop_transfer_order_retries_and_timeout(self):
        import time
        d=self.start().json
        paired=self.a.post('/api/portals/desktop/pair',json={'code':d['code']}).json
        self.assertEqual(paired['protocol'],2)
        auth={'Authorization':'Bearer '+paired['token']}
        def call(op):return self.a.post('/api/portals/desktop/'+op,json={},headers=auth)
        self.assertEqual(call('state').json['phase'],'preparing')
        self.assertEqual(call('arrived').status_code,425)
        self.assertEqual(call('sample').status_code,425)
        self.assertEqual(self.post('depart-complete',{'trip':d['trip']}).status_code,425)
        self.assertEqual(call('ready').json['phase'],'entering')
        self.assertEqual(call('ready').json['phase'],'entering')
        self.assertEqual(self.post('depart-complete',{'trip':d['trip']},self.b).status_code,404)
        self.assertEqual(self.post('depart-complete',{'trip':d['trip']}).json['phase'],'emerging')
        self.assertEqual(self.post('depart-complete',{'trip':d['trip']}).json['phase'],'emerging')
        self.assertEqual(call('arrived').json['phase'],'roaming')
        self.assertEqual(call('ready').json['phase'],'roaming')
        call('return')
        self.assertEqual(call('ready').status_code,409)
        self.assertEqual(self.a.get('/api/portals').json['rewards'],[])
        d=self.start().json
        paired=self.a.post('/api/portals/desktop/pair',json={'code':d['code']}).json
        auth={'Authorization':'Bearer '+paired['token']}
        with self.app.app_context():
            db=get_db();db.execute('UPDATE portal_trips SET phase_started=? WHERE id=?',(time.time()-100,d['trip']));db.commit()
        self.assertEqual(call('ping').status_code,409,'keepalive cannot keep a stuck preparation alive')
        for phase in ('entering','emerging'):
            d=self.start().json
            paired=self.a.post('/api/portals/desktop/pair',json={'code':d['code']}).json
            auth={'Authorization':'Bearer '+paired['token']}
            call('ready')
            if phase=='emerging':self.post('depart-complete',{'trip':d['trip']})
            with self.app.app_context():
                db=get_db();db.execute('UPDATE portal_trips SET phase_started=? WHERE id=?',(time.time()-21,d['trip']));db.commit()
            self.assertEqual(call('state').status_code,409)
            self.assertEqual(call('arrived').status_code,409,'late completion cannot resurrect a timed-out journey')
    def test_disconnect_and_energy_return(self):
        d=self.start().json
        r=self.a.post('/api/portals/desktop/pair',json={'code':d['code']})
        with self.app.app_context():
            db=get_db();db.execute('UPDATE portal_trips SET updated=0 WHERE id=?',(d['trip'],));db.commit()
        state=self.a.get('/api/portals').json
        self.assertEqual(state['trips'][0]['status'],'returned');self.assertIn('连接中断',state['trips'][0]['reason'])
        self.assertEqual(len(state['rewards']),0,'no souvenir for a connection without actual exploration')

    def test_desktop_deadline_is_fixed_and_error_codes_distinguish_lifecycle(self):
        d=self.start().json
        paired=self.a.post('/api/portals/desktop/pair',json={'code':d['code']}).json
        auth={'Authorization':'Bearer '+paired['token']}
        def call(op):return self.a.post('/api/portals/desktop/'+op,json={},headers=auth)
        state=call('state').json
        deadline=state['created']+1800
        self.assertEqual(paired['expiresAt'],deadline)
        self.assertEqual(state['expiresAt'],deadline)
        self.assertLess(paired['serverTime'],deadline)
        self.assertEqual(call('arrived').json['code'],'TRIP_NOT_READY')
        self.assertEqual(call('sample').json['code'],'TRIP_NOT_READY')
        self.assertEqual(self.start().json['code'],'PORTAL_ERROR')
        call('ready');self.post('depart-complete',{'trip':d['trip']});call('arrived')
        # A recent heartbeat cannot renew the absolute lifetime, including at equality.
        with self.app.app_context():
            db=get_db();db.execute('UPDATE portal_trips SET updated=? WHERE id=?',(deadline-10,d['trip']));db.commit()
        with patch.object(portal.time,'time',return_value=deadline-1):
            self.assertEqual(call('ping').json['expiresAt'],deadline)
            self.assertEqual(call('state').json['expiresAt'],deadline)
        with patch.object(portal.time,'time',return_value=deadline):
            ended=call('ping')
            self.assertEqual((ended.status_code,ended.json['code']),(409,'TRIP_ENDED'))
            self.assertEqual(call('arrived').json['code'],'TRIP_ENDED')
        self.assertEqual(self.a.get('/api/portals/trip/'+d['trip']).json['status'],'returned')
    def test_custom_memorial_contract_and_no_public_discovery(self):
        with self.app.app_context():portal.register_custom_pet('user:1','custom-test','纪念猫','/static/models/custom/test.glb')
        state=self.a.get('/api/portals').json;island=next(i for i in state['islands'] if i['pet']=='custom-test')
        self.assertFalse(island['allow_visitors']);self.assertTrue(island['memorial'])
        self.assertEqual(self.b.get('/api/portals').json['friends'],[])
        self.assertEqual(self.post('depart',dict(pet='custom-test',kind='desktop',confirmed=True)).status_code,200)
        self.assertEqual(self.post('depart',dict(pet='custom-test',kind='desktop',confirmed=True),self.b).status_code,404)
    def test_bad_samples_no_state_corruption_and_brief_state(self):
        dest=self.friends();d=self.start('neighbor',destination=dest).json
        for value in [float('nan'),101,'bad',True]:
            self.assertEqual(self.post('sample',{'trip':d['trip'],'snapshot':{'visitor':{'x':value,'z':0}}}).status_code,400)
        self.assertEqual(self.a.get('/api/portals?brief=1').json['trips'][0]['events'],[])
        self.assertEqual(self.a.get('/visit/'+d['trip']).status_code,200)
        self.assertEqual(self.a.get('/journeys').status_code,200)

    def private_pet(self,owner,task):
        import time
        import hashlib
        from pet_quality_helpers import approve_quality
        raw=b'glTF-private-animation-'+task.encode()
        with self.app.app_context():
            db=get_db()
            db.execute('INSERT INTO pet_studio_tasks VALUES (?,?,?,?,?,?,?,?)',(task,owner,'私人猫','companion','approved','',time.time(),time.time()))
            db.execute('INSERT INTO pet_studio_adaptations VALUES (?,?,?,?,?,?)',(task,'rig-'+task,hashlib.sha256(raw).hexdigest(),'reviewed','{}',time.time()))
            db.execute('INSERT INTO pet_studio_assets VALUES (?,?,?,?)',(task,'adapted','model/gltf-binary',raw))
            db.execute('INSERT INTO pet_studio_assets VALUES (?,?,?,?)',(task,'model','model/gltf-binary',raw))
            approve_quality(task)
            db.execute('INSERT INTO pet_studio_equipped VALUES (?,?)',(owner,task));db.commit()
        return raw

    def test_private_desktop_model_requires_active_paired_token(self):
        raw=self.private_pet('user:1','private-a')
        d=self.start().json
        paired=self.a.post('/api/portals/desktop/pair',json={'code':d['code']}).json
        self.assertTrue(paired['pet']['custom'])
        self.assertEqual(paired['pet']['model'],'/api/portals/desktop/model')
        url=paired['pet']['model'];auth={'Authorization':'Bearer '+paired['token']}
        self.assertEqual(self.a.get(url).status_code,401)
        self.assertEqual(self.b.get(url,headers={'Authorization':'Bearer wrong'}).status_code,409)
        response=self.app.test_client().get(url,headers=auth)
        self.assertEqual(response.data,raw);self.assertEqual(response.headers['Cache-Control'],'no-store')
        with self.app.app_context():
            db=get_db();db.execute("DELETE FROM pet_studio_quality WHERE task=? AND stage='motion'",('private-a',));db.commit()
        self.assertNotEqual(self.a.get(url,headers=auth).status_code,200)
        self.assertEqual(self.b.get('/api/pet-studio/private-a/assets/adapted').status_code,404)
        self.post('return',{'trip':d['trip']})
        self.assertEqual(self.a.get(url,headers=auth).status_code,409)

    def test_private_neighbor_models_only_shared_with_active_participants(self):
        visitor=self.private_pet('user:1','private-a');host=self.private_pet('user:2','private-b')
        self.friends()
        self.assertEqual(self.post('settings',{'pet':'3','allow':True},self.b).status_code,200)
        dest=next(i['id'] for i in self.b.get('/api/portals').json['islands'] if i['pet']=='3')
        tid=self.start('neighbor',destination=dest).json['trip']
        t=self.a.get('/api/portals/trip/'+tid).json
        self.assertTrue(t['petSpec']['custom']);self.assertTrue(t['hostPet']['custom'])
        for spec,raw in [(t['petSpec'],visitor),(t['hostPet'],host)]:
            for client in (self.a,self.b):self.assertEqual(client.get(spec['model']).data,raw)
            self.assertEqual(self.app.test_client().get(spec['model']).status_code,404)
        self.assertEqual(self.a.get('/api/pet-studio/private-b/assets/front').status_code,404)
        self.assertEqual(self.a.get('/api/portals/trip/'+tid+'/model/front').status_code,404)
        self.post('settings',{'pet':'3','allow':False},self.b)
        for spec in [t['petSpec'],t['hostPet']]:self.assertEqual(self.a.get(spec['model']).status_code,409)

if __name__=='__main__':unittest.main()
