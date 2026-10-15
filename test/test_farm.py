import unittest,uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from test_companion import CompanionTests as Base
from app.services import farm_service as farm
from app.db import get_db

class FarmTests(unittest.TestCase):
    setUp=Base.setUp
    tearDown=Base.tearDown
    def post(self,op,data=None,c=None):
        c=c or self.a;scope=c.get('/api/farm').json['scope']
        return c.post('/api/farm/'+op,json={'token':uuid.uuid4().hex,**(data or {})},headers={'X-Profile-Scope':scope})
    def planted(self,species='cosmos',bed='bed-1'):
        self.post('start');s=self.post('plant',dict(species=species,bed=bed)).json
        return next(b['plant']['id'] for b in s['beds'] if b['id']==bed)
    def mature(self):
        with self.app.app_context():
            with get_db() as db:db.execute('UPDATE farm_plants SET planted=planted-?',(48*3600,))
    def test_starter_inventory_and_account_isolation(self):
        d=self.post('start').json;self.assertEqual(d['inventory']['pot'],1)
        self.post('start');self.assertEqual(self.a.get('/api/farm').json['inventory']['seed:cosmos'],2)
        self.assertEqual(self.b.get('/api/farm').json['inventory'],{})
        self.assertEqual(self.post('plant',dict(bed='bed-1',species='birch')).status_code,400)
        self.assertEqual(self.post('plant',dict(bed='nursery-1',species='pumpkin')).status_code,400)
        self.assertEqual(self.post('plant',dict(bed='bed-1',species='cosmos',owner='user:bob')).json['inventory']['seed:cosmos'],1)
        self.assertFalse(any(b['plant'] for b in self.b.get('/api/farm').json['beds']))
    def test_ten_stages_server_clock_water_and_offline_growth(self):
        pid=self.planted();data=dict(bed='bed-1',plant=pid)
        self.assertEqual(self.post('harvest',data).status_code,409)
        self.assertEqual(self.post('water',data).status_code,200)
        self.assertEqual(self.post('water',data).status_code,409)
        with self.app.app_context():
            row=get_db().execute('SELECT * FROM farm_plants').fetchone();r=dict(row,bonus=0)
            for stage in range(1,11):
                age=(stage-1)*farm.SPECIES['cosmos']['hours']*3600/9
                self.assertEqual(farm.growth(r,r['planted']+age+.01)['stage'],stage)
        self.mature();d=self.post('harvest',data).json;self.assertEqual(d['inventory']['cosmos'],1)
        self.assertEqual(self.post('harvest',data).status_code,409)
    def test_full_flower_pot_recover_tree_and_food_cycle(self):
        p=self.planted();self.mature();self.post('harvest',dict(bed='bed-1',plant=p))
        d=self.post('place',dict(species='cosmos',slot='pot-1')).json
        self.assertEqual(d['inventory']['pot'],0);self.assertEqual(d['decorations'][0]['slot'],'pot-1')
        d=self.post('recover',dict(slot='pot-1')).json;self.assertEqual(d['inventory']['pot'],1);self.assertEqual(d['inventory']['cosmos'],1)
        p=self.planted('birch','nursery-1');self.mature();self.post('harvest',dict(bed='nursery-1',plant=p))
        self.assertEqual(self.post('place',dict(species='birch',slot='pot-1')).status_code,400)
        self.assertEqual(self.post('place',dict(species='birch',slot='tree-1')).status_code,200)
        p=self.planted('pumpkin','bed-2');self.mature();self.post('harvest',dict(bed='bed-2',plant=p))
        self.assertEqual(self.post('cook').json['inventory']['pumpkin'],1)
        self.assertEqual(self.a.get('/api/supplies').json['inventory']['treat'],1)
    def test_idempotent_parallel_purchase_and_no_overdraft(self):
        self.post('start');data=dict(token='stable-purchase-001',item='pot',quantity=2)
        with self.app.app_context():owner=get_db().execute('SELECT owner FROM farm_accounts').fetchone()[0]
        def buy(_):
            with self.app.app_context():return farm.operate(owner,'buy',data)
        with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(buy,range(2)))
        d=self.post('buy',data).json;self.assertEqual(d['balance'],130);self.assertEqual(d['inventory']['pot'],3)
        self.assertEqual(self.post('buy',{**data,'quantity':1}).status_code,409)
        self.assertEqual(self.post('buy',dict(item='pot',quantity=20)).status_code,409)
        self.assertEqual(self.post('buy',dict(item='pot',quantity=True)).status_code,400)
    def test_old_plant_id_cannot_water_or_harvest_replacement(self):
        old=self.planted();self.mature();self.post('harvest',dict(bed='bed-1',plant=old));self.planted()
        self.assertEqual(self.post('water',dict(bed='bed-1',plant=old)).status_code,409)
        self.assertEqual(self.post('harvest',dict(bed='bed-1',plant=old)).status_code,409)
    def test_guests_scope_origin_and_malformed_payloads(self):
        c=self.app.test_client();self.assertEqual(self.post('start',c=c).status_code,403)
        self.assertEqual(self.a.post('/api/farm/start',json={'token':'some-request'}).status_code,409)
        scope=self.a.get('/api/farm').json['scope']
        self.assertEqual(self.a.post('/api/farm/start',json={'token':'some-request'},headers={'X-Profile-Scope':scope,'Origin':'https://bad.invalid'}).status_code,403)
        self.post('start')
        for data in [dict(species=[],bed='bed-1'),dict(species='cosmos',bed={})]:self.assertEqual(self.post('plant',data).status_code,400)

if __name__=='__main__':unittest.main()
