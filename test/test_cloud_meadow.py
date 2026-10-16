import unittest
from test_companion import CompanionTests as Base
from test_farm import FarmTests

class CloudMeadowTests(unittest.TestCase):
    setUp=Base.setUp
    tearDown=Base.tearDown
    post=FarmTests.post
    planted=FarmTests.planted

    def test_young_transplant_new_meadow_persists_and_is_private(self):
        pid=self.planted()
        r=self.post('arrange',dict(x=11.5,z=8,yaw=.2,container='soil',species='cosmos',bed='bed-1',plant=pid))
        self.assertEqual(r.status_code,200,r.json)
        plant=r.json['arrangements'][0]
        self.assertEqual(plant['stage'],1)
        self.assertEqual(plant['x'],11.5)
        self.assertEqual(self.a.get('/api/farm').json['arrangements'][0]['id'],plant['id'])
        self.assertEqual(self.b.get('/api/farm').json['arrangements'],[])
        world=self.a.get('/api/cat-agent/scene').json['world']
        self.assertIn('云上原野',world['scene'])
        self.assertEqual({p['id'] for p in world['regions']},{'cloud_meadow','woodland_clearing','meadow_walk'})
        self.assertTrue(any(p['x']==11.5 for p in world['places']))
        self.assertIn('FARM_MAP_LAYOUT',self.a.get('/cat-agent-monitor').get_data(as_text=True))

    def test_reject_path_and_outside_without_losing_inventory(self):
        pid=self.planted()
        for x,z in [(7,6.4),(20,8),(15,-4),(13,-1.15)]:
            r=self.post('arrange',dict(x=x,z=z,yaw=0,container='pot',species='cosmos',bed='bed-1',plant=pid))
            self.assertEqual(r.status_code,409,r.json)
        s=self.a.get('/api/farm').json
        self.assertEqual(s['beds'][0]['plant']['id'],pid)
        self.assertEqual(s['inventory']['pot'],1)
