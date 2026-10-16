"""Persistent juvenile plants: time, care, recovery and mutation are server-owned."""
import unittest
from unittest.mock import patch
import test_farm_direct as direct
from app.db import get_db
from app.services import farm_service as farm


class TransplantGrowthTests(unittest.TestCase):
    setUp = direct.DirectGardenTests.setUp
    tearDown = direct.DirectGardenTests.tearDown
    post = direct.DirectGardenTests.post
    planted = direct.DirectGardenTests.planted
    point = direct.DirectGardenTests.point

    def transplant(self, species='cosmos', container='soil', bed='bed-1'):
        pid = self.planted(species, bed)
        result = self.post('arrange', dict(**self.point(container, species), bed=bed, plant=pid))
        self.assertEqual(result.status_code, 200, result.json)
        return result.json['arrangements'][0]

    def test_juvenile_soil_and_pot_keep_stage_and_grow_offline(self):
        for container in ['soil', 'pot']:
            with self.subTest(container=container):
                pid = self.planted()
                self.post('water', dict(bed='bed-1', plant=pid))
                before = self.a.get('/api/farm').json['beds'][0]['plant']
                others = self.a.get('/api/farm').json['arrangements']
                d = self.post('arrange', dict(**self.point(container, others=others), bed='bed-1', plant=pid)).json
                p = d['arrangements'][-1]
                self.assertEqual(p['stage'], before['stage'])
                self.assertAlmostEqual(p['progress'], before['progress'], places=4)
                self.assertFalse(p['ready']);self.assertTrue(p['watered'])
                self.assertEqual(p['growthRate'], .25)
                self.assertIsNone(d['beds'][0]['plant'])
                self.assertEqual(self.b.get('/api/farm').json['arrangements'], [])
                with self.app.app_context():
                    with get_db() as db:
                        db.execute('UPDATE farm_arrangements SET planted=planted-3600 WHERE id=?', (p['id'],))
                q = next(r for r in self.a.get('/api/farm').json['arrangements'] if r['id']==p['id'])
                self.assertAlmostEqual(q['progress']-p['progress'], .25/18, places=4)
                world = self.a.get('/api/cat-agent/scene').json['world']
                self.assertTrue(any(x['slot']==p['id'] and not x['ready'] for x in world['decorations']))
                self.assertTrue(any(x['id']=='plant:'+p['id'] and '缓慢生长' in x['description'] for x in world['places']))

    def test_care_is_daily_idempotent_and_scoped_and_moves_do_not_reset(self):
        p = self.transplant(container='pot')
        args = dict(id=p['id'], revision=p['revision'], token='care-transplant-once')
        d = self.post('fertilize', args).json
        q = d['arrangements'][0]
        self.assertAlmostEqual(q['progress']-p['progress'], .06, places=4)
        self.assertEqual(d['inventory']['fertilizer'], 2)
        self.assertEqual(self.post('fertilize', args).json['inventory']['fertilizer'], 2)
        self.assertEqual(self.post('water', dict(id=q['id'], revision=q['revision']), c=self.b).status_code, 409)
        self.assertEqual(self.post('fertilize', dict(id=q['id'], revision=q['revision'])).status_code, 409)
        self.assertEqual(self.post('water', dict(id=q['id'], revision=1)).status_code, 409)
        moved = self.post('arrange', dict(**self.point('pot'), id=q['id'], revision=q['revision'])).json['arrangements'][0]
        self.assertAlmostEqual(moved['progress'], q['progress'], places=4)
        q = self.post('water', dict(id=moved['id'], revision=moved['revision'])).json['arrangements'][0]
        self.assertAlmostEqual(q['progress']-moved['progress'], .08, places=4)
        self.assertTrue(q['watered']);self.assertTrue(q['fertilized'])
        self.assertEqual(self.post('water', dict(id=q['id'], revision=q['revision'])).status_code, 409)

    def test_recover_juvenile_cannot_create_mature_inventory_or_double_care(self):
        p = self.transplant(container='pot')
        p = self.post('water', dict(id=p['id'], revision=p['revision'])).json['arrangements'][0]
        d = self.post('recover-arrangement', dict(id=p['id'], revision=p['revision'])).json
        self.assertEqual(d['arrangements'], []);self.assertEqual(d['inventory']['pot'], 1)
        self.assertEqual(d['inventory'].get('cosmos', 0), 0)
        q = d['beds'][0]['plant']
        self.assertAlmostEqual(q['progress'], p['progress'], places=4)
        self.assertTrue(q['watered']);self.assertFalse(q['ready'])
        self.assertEqual(self.post('harvest', dict(bed='bed-1', plant=q['id'])).status_code, 409)
        self.assertEqual(self.post('water', dict(bed='bed-1', plant=q['id'])).status_code, 409)
        next_p = self.post('arrange', dict(**self.point(), bed='bed-1', plant=q['id'])).json['arrangements'][0]
        self.assertNotEqual(p['id'], next_p['id'])  # stale old placement cannot address a new one

    def test_full_beds_reject_recovery_without_losing_plant_or_pot(self):
        p = self.transplant(container='pot')
        with self.app.app_context():
            with get_db() as db:
                for key, bed in farm.BEDS.items():
                    if not bed.get('nursery'):
                        db.execute('INSERT INTO farm_plants(owner,bed,id,species,planted) SELECT owner,?,?,species,planted FROM farm_arrangements WHERE id=?', (key,'filler-'+key,p['id']))
        self.assertEqual(self.post('recover-arrangement', dict(id=p['id'], revision=p['revision'])).status_code, 409)
        d = self.a.get('/api/farm').json
        self.assertEqual(d['inventory']['pot'], 0);self.assertEqual(d['arrangements'][0]['id'], p['id'])

    def test_mutation_occurs_once_on_island_and_survives_recovery(self):
        p = self.transplant('rose')
        with self.app.app_context():
            with get_db() as db:db.execute('UPDATE farm_arrangements SET planted=planted-?', (farm.SPECIES['rose']['hours']*3600*4+1,))
        with patch.object(farm.secrets, 'randbelow', return_value=0) as roll:
            d = self.a.get('/api/farm').json;p = d['arrangements'][0]
            self.assertTrue(p['ready']);self.assertEqual(p['stage'], 10);self.assertEqual(p['species'], 'rose-dream')
            self.a.get('/api/cat-agent/scene');self.a.get('/api/farm')
            self.assertEqual(roll.call_count, 1)
        d = self.post('recover-arrangement', dict(id=p['id'], revision=p['revision'])).json
        self.assertEqual(d['inventory']['rose-dream'], 1)

    def test_food_and_tree_can_transplant_with_pots(self):
        for species,bed in [('birch','nursery-1'),('pumpkin','bed-1')]:
            p = self.transplant(species, 'pot', bed)
            self.assertFalse(p['ready'])
            d = self.post('recover-arrangement', dict(id=p['id'], revision=p['revision'])).json
            self.assertEqual(d['inventory']['pot'], 1)
            self.assertTrue(any(b['plant'] and b['plant']['species']==species for b in d['beds'] if bool(b.get('nursery'))==(species=='birch')))

    def test_legacy_arrangements_remain_mature_after_migration(self):
        self.post('start')
        with self.app.app_context():
            with get_db() as db:
                owner=db.execute('SELECT owner FROM farm_accounts').fetchone()[0]
                db.execute('INSERT INTO farm_arrangements(owner,id,species,container,x,z,yaw,created) VALUES (?,?,?,?,?,?,?,?)',(owner,'legacy','cosmos','soil',0,4,0,1))
            farm.init_schema()
        p = self.a.get('/api/farm').json['arrangements'][0]
        self.assertTrue(p['ready']);self.assertEqual(p['stage'], 10)
        self.assertEqual(self.post('fertilize', dict(id=p['id'], revision=p['revision'])).status_code, 409)


if __name__ == '__main__':unittest.main()
