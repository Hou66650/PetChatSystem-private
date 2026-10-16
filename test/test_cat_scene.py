"""Shared scene contract, real farm transactions and model-boundary integration."""
import json
import unittest
import uuid
from test_companion import CompanionTests as Base
from app.db import get_db
from app.services import realtime_service


class CatSceneTests(unittest.TestCase):
    setUp = Base.setUp
    tearDown = Base.tearDown

    def post(self, area, op, data=None, client=None):
        client = client or self.a
        scope = client.get('/api/'+area).json['scope']
        return client.post('/api/'+area+'/'+op, json={'token':uuid.uuid4().hex, **(data or {})}, headers={'X-Profile-Scope':scope})

    def world(self, client=None):
        return (client or self.a).get('/api/cat-agent/scene').json['world']

    def test_all_arrangements_are_available_not_only_latest_sixteen(self):
        from unittest.mock import patch
        plants=[dict(id='fixture-'+str(i),species='cosmos',container='soil',x=i*.1,z=8,
                     stage=3,ready=False,watered=False,fertilized=False,revision=1) for i in range(24)]
        with patch('app.services.farm_service.arrangements',return_value=plants):
            world=self.world()
            targets={p['id'] for p in world['places']}
            self.assertTrue({'plant:fixture-'+str(i) for i in range(24)} <= targets)
            self.assertEqual(len([p for p in world['places'] if p['dynamic']]),24)

    def plant(self):
        self.post('farm','start')
        response = self.post('farm','plant',dict(bed='bed-1',species='cosmos',token='stable-plant-request'))
        self.assertEqual(response.status_code,200)
        return response.json['beds'][0]['plant']['id']

    def report(self, world, result='completed', event='observed-garden-1', client=None):
        return self.post('cat-agent','report',dict(target='farm_path',action='observe',worldRevision=world['revision'],result=result,event=event),client)

    def test_authoritative_stable_snapshots_growth_and_isolation(self):
        empty=self.world();pid=self.plant();planted=self.world()
        self.assertNotEqual(empty['revision'],planted['revision'])
        self.assertEqual(planted['revision'],self.world()['revision'])
        self.assertEqual(planted['beds'][0]['plant']['stage'],1)
        self.assertIsNone(self.world(self.b)['beds'][0]['plant'])
        self.assertEqual(self.world(self.b)['recentChanges'],[])
        self.post('farm','water',dict(bed='bed-1',plant=pid))
        watered=self.world();self.assertTrue(watered['beds'][0]['plant']['wateredToday'])
        self.assertNotEqual(watered['revision'],planted['revision'])
        with self.app.app_context():
            with get_db() as db:db.execute('UPDATE farm_plants SET planted=planted-?',(48*3600,))
        mature=self.world();self.assertEqual(mature['beds'][0]['plant']['stage'],10)
        self.assertTrue(mature['beds'][0]['plant']['ready'])
        self.post('farm','harvest',dict(bed='bed-1',plant=pid))
        self.post('farm','place',dict(species='cosmos',slot='pot-1'))
        self.assertEqual(self.world()['decorations'][0]['plant'],'波斯菊')
        self.assertEqual(self.world(self.b)['decorations'],[])

    def test_events_commit_once_and_roll_back_with_operations(self):
        pid=self.plant()
        self.post('farm','plant',dict(bed='bed-1',species='cosmos',token='stable-plant-request'))
        self.assertEqual(len(self.world()['recentChanges']),1)
        self.assertEqual(self.post('farm','harvest',dict(bed='bed-1',plant=pid)).status_code,409)
        self.assertEqual(len(self.world()['recentChanges']),1)
        self.post('farm','water',dict(bed='bed-1',plant=pid,token='water-garden-once'))
        self.post('farm','water',dict(bed='bed-1',plant=pid,token='water-garden-once'))
        self.assertEqual([e['kind'] for e in self.world()['recentChanges']],['water','plant'])

    def test_only_completed_known_own_snapshots_become_experiences(self):
        self.plant();world=self.world()
        self.report(world,'blocked','blocked-garden-1')
        self.report(dict(revision='unknown'),'completed','unknown-garden-1')
        self.report(world,client=self.b)
        self.assertEqual(self.a.get('/api/cat-agent/monitor').json['scene']['experiences'],[])
        self.assertEqual(self.b.get('/api/cat-agent/monitor').json['scene']['experiences'],[])
        self.report(world);self.report(world)
        experiences=self.a.get('/api/cat-agent/monitor').json['scene']['experiences']
        self.assertEqual(len(experiences),1);self.assertIn('波斯菊',experiences[0]['summary'])
        self.assertEqual(self.world()['attention'],[])
        with self.app.app_context():
            with get_db() as db:db.execute('UPDATE farm_plants SET planted=planted-?',(48*3600,))
        self.assertTrue(self.world()['attention'],'new growth must restore curiosity')

    def test_model_receives_server_scene_and_audit_matches_actual_input(self):
        self.plant();captured=[]
        def plan(messages):
            captured.append(json.loads(messages[1]['content']))
            return '{"target":"farm_path","action":"observe"}'
        self.model.plan_once=plan
        r=self.post('cat-agent','decide',dict(stream='cat-stream-01',candidates=['farm_path','bridge'],world={'plant':'FORGED'}))
        self.assertEqual(r.json['source'],'model');self.assertNotIn('FORGED',str(captured))
        self.assertEqual(captured[0]['scene']['beds'][0]['plant']['name'],'波斯菊')
        audit=self.a.get('/api/cat-agent/monitor').json['scene']['decisions'][0]
        self.assertEqual(audit['inputs'],captured[0]);self.assertTrue(audit['modelUsed'])
        self.assertEqual(audit['result']['worldRevision'],r.json['worldRevision'])
        self.assertEqual(self.b.get('/api/cat-agent/monitor').json['scene']['decisions'],[])
        care=self.post('cat-agent','decide',dict(stream='cat-stream-02',candidates=['farm_path','home'],energy=.1))
        self.assertEqual(care.json['action'],'sleep');self.assertEqual(len(captured),1)

    def test_chat_and_voice_share_facts_but_preserve_private_context_boundary(self):
        self.plant();world=self.world();self.report(world)
        r=self.a.post('/get_gpt_response',json={'message':'花园有什么','petId':3,'surface':'den'})
        self.assertEqual(r.status_code,200)
        prompt=self.model.calls[-1][0]['content']
        self.assertIn('波斯菊',prompt);self.assertIn('猫咪完成种植园观察',prompt)
        self.assertIn('区分主人操作',prompt)
        self.b.post('/get_gpt_response',json={'message':'花园有什么','petId':3,'surface':'den'})
        self.assertNotIn('波斯菊',str(self.model.calls[-1]))
        self.a.patch('/api/companion',json={'enabled':False})
        self.a.post('/get_gpt_response',json={'message':'现在呢','petId':3,'surface':'den'})
        self.assertIn('波斯菊',self.model.calls[-1][0]['content'])
        self.assertNotIn('猫咪完成种植园观察',self.model.calls[-1][0]['content'])
        with self.app.test_request_context('/'):
            from flask import session
            session['user_id']='alice';session['auth_kind']='user'
            self.assertIn('波斯菊',realtime_service.build_instructions(3))
            self.assertNotIn('波斯菊',realtime_service.build_instructions(3,private_context=False))
            self.assertNotIn('波斯菊',realtime_service.build_instructions(1))

    def test_monitor_distinguishes_used_revision_from_new_server_state(self):
        pid=self.plant();world=self.world()
        self.post('cat-agent','telemetry',dict(stream='cat-stream-01',snapshot={'worldRevision':world['revision'],'enabled':True}))
        self.post('farm','water',dict(bed='bed-1',plant=pid))
        d=self.a.get('/api/cat-agent/monitor').json['scene']
        self.assertEqual(d['used']['cat-stream-01']['revision'],world['revision'])
        self.assertNotEqual(d['current']['revision'],world['revision'])
        self.assertFalse(d['used']['cat-stream-01']['beds'][0]['plant']['wateredToday'])
        self.assertTrue(d['current']['beds'][0]['plant']['wateredToday'])
        self.assertEqual(self.b.get('/api/cat-agent/monitor').json['scene']['used'],{})

    def test_forgetting_clears_completed_experiences_without_removing_garden(self):
        self.plant();self.report(self.world())
        self.a.delete('/api/companion',json={})
        self.a.post('/get_gpt_response',json={'message':'花园有什么','petId':3,'surface':'den'})
        prompt=self.model.calls[-1][0]['content']
        self.assertIn('波斯菊',prompt)
        self.assertNotIn('猫咪完成种植园观察',prompt)
        self.assertEqual(self.a.get('/api/cat-agent/monitor').json['scene']['experiences'],[])


if __name__=='__main__':unittest.main()
