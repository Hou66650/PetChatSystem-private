import unittest, uuid
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from test_companion import CompanionTests as Base
from test_farm import FarmTests as Helpers
from app.db import get_db
from app.services import farm_service as farm, farm_placement_service as placement

class FlowerCollectionTests(unittest.TestCase):
    setUp=Base.setUp
    tearDown=Base.tearDown
    post=Helpers.post
    mature=Helpers.mature

    def plant(self,bed='bed-1',species='rose'):
        self.post('start')
        r=self.post('plant',dict(bed=bed,species=species))
        self.assertEqual(r.status_code,200)
        return next(b['plant']['id'] for b in r.json['beds'] if b['id']==bed)

    def test_catalog_and_no_variant_seed_purchase(self):
        state=self.post('start').json
        self.assertEqual(len(farm.FLOWERS),10)
        for flower in farm.FLOWERS:
            self.assertEqual(state['inventory']['seed:'+flower['id']],2)
            self.assertNotIn('seed:'+flower['id']+'-dream',state['inventory'])
            self.assertEqual(len(farm.SPECIES[flower['id']]['stages']),10)
        self.assertEqual(self.post('plant',dict(bed='bed-1',species='rose-dream')).status_code,400)
        self.assertEqual(self.post('buy',dict(item='seed:rose-dream')).status_code,400)

    def test_one_roll_and_durable_variant_lifecycle(self):
        pid=self.plant()
        with patch.object(farm.secrets,'randbelow',return_value=0) as roll:
            self.a.get('/api/farm');self.assertEqual(roll.call_count,0)
            self.mature()
            s=self.a.get('/api/farm').json
            self.assertEqual(s['beds'][0]['plant']['species'],'rose-dream')
            self.a.get('/api/farm');self.a.get('/api/cat-agent/scene')
            self.assertEqual(roll.call_count,1)
        s=self.post('harvest',dict(bed='bed-1',plant=pid)).json
        self.assertEqual(s['inventory']['rose-dream'],1)
        p=next(dict(species='rose-dream',container='pot',x=x/5,z=z/5,yaw=0) for x in range(-25,25) for z in range(-25,25) if not placement.validate(dict(species='rose-dream',container='pot',x=x/5,z=z/5,yaw=0)))
        saved=self.post('arrange',p).json['arrangements'][0]
        self.assertEqual(saved['species'],'rose-dream')
        self.assertEqual(self.b.get('/api/farm').json['arrangements'],[])
        self.assertEqual(self.post('recover-arrangement',dict(id=saved['id'],revision=1)).json['inventory']['rose-dream'],1)
        self.assertEqual(self.a.get('/api/farm').json['inventory']['pot'],1)

    def test_normal_bloom_never_rerolls_and_parallel_reads_resolve_once(self):
        self.plant();self.mature()
        with self.app.app_context():owner=get_db().execute('SELECT owner FROM farm_accounts').fetchone()[0]
        def read(_):
            with self.app.app_context():return farm.state(owner)
        with patch.object(farm.secrets,'randbelow',return_value=7) as roll:
            with ThreadPoolExecutor(max_workers=2) as pool:states=list(pool.map(read,range(2)))
            self.assertEqual(roll.call_count,1)
        with patch.object(farm.secrets,'randbelow',side_effect=AssertionError('must not reroll')):
            self.assertEqual(self.a.get('/api/farm').json['beds'][0]['plant']['species'],'rose')

    def test_agent_targets_specific_plants_and_only_remembers_completed_subject(self):
        self.plant();self.plant('bed-2','tulip')
        world=self.a.get('/api/cat-agent/scene').json['world']
        self.assertEqual(len(world['places']),2)
        target=world['places'][0];self.assertTrue(target['approaches']);self.assertEqual(target['actions'],['observe','sniff'])
        self.assertNotIn(target['id'],[p['id'] for p in self.b.get('/api/cat-agent').json['catalog']])
        scope=self.a.get('/api/cat-agent').json['scope']
        def report(action='observe',result='completed'):
            return self.a.post('/api/cat-agent/report',json=dict(target=target['id'],action=action,result=result,event=uuid.uuid4().hex,worldRevision=world['revision']),headers={'X-Profile-Scope':scope})
        self.assertEqual(report('nibble').status_code,400)
        self.assertEqual(report(result='blocked').status_code,200)
        self.assertEqual(len(self.a.get('/api/cat-agent/scene').json['world']['attention']),2)
        self.assertEqual(report().status_code,200)
        attention=self.a.get('/api/cat-agent/scene').json['world']['attention']
        self.assertEqual([p['target'] for p in attention],['garden:bed-2'])
        experiences=self.a.get('/api/cat-agent/monitor').json['scene']['experiences']
        self.assertIn('玫瑰',experiences[0]['summary'])
        with patch.object(farm.secrets,'randbelow',return_value=0):
            self.mature();world=self.a.get('/api/cat-agent/scene').json['world']
        self.assertEqual(len(world['attention']),2)
        self.assertTrue(world['beds'][0]['plant']['variant'])
        captured=[]
        def model(messages):
            captured.append(messages);return '{"target":"garden:bed-1","action":"observe"}'
        self.model.plan_once=model
        r=self.a.post('/api/cat-agent/decide',json=dict(candidates=['garden:bed-1'],energy=.9),headers={'X-Profile-Scope':scope})
        self.assertEqual(r.status_code,200);self.assertEqual(r.json['source'],'model');self.assertIn('月雾玫瑰',str(captured))

if __name__=='__main__':unittest.main()
