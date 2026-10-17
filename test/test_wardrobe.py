"""Real database contracts for wallet safety, ownership, and pet-specific outfits."""
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
import test_companion as fixtures
from app.db import get_db
from app.services import wardrobe_service as wardrobe, portal_service, pet_generation_service

class WardrobeTests(unittest.TestCase):
    setUp = fixtures.CompanionTests.setUp
    tearDown = fixtures.CompanionTests.tearDown

    def post(self, op, client=None, **data):
        client = client or self.a
        scope = client.get('/api/wardrobe').json['scope']
        return client.post('/api/wardrobe/'+op, json={'petId':1, **data}, headers={'X-Profile-Scope':scope})

    def test_buy_once_wallet_is_shared_and_account_isolated(self):
        for _ in range(2):
            r = self.post('buy', item='moss-bow', price=0, owner='user:2')
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.json['balance'], 100)
            self.assertEqual(r.json['equipped'], {})
        self.assertEqual(self.a.get('/api/cat-market').json['balance'], 100)
        self.assertNotIn('moss-bow', self.b.get('/api/wardrobe').json['owned'])
        with self.app.app_context():
            self.assertEqual(get_db().execute("SELECT count(*) FROM cat_coin_ledger WHERE kind='wardrobe_purchase'").fetchone()[0], 1)

    def test_slots_replace_independently_and_share_owned_items(self):
        self.post('buy', item='moss-bow');self.post('buy', item='daisy')
        self.post('equip', item='moss-bow');r=self.post('equip', item='daisy')
        self.assertEqual(r.json['equipped'], {'head':'daisy', 'neck':'moss-bow'})
        self.assertEqual(self.post('equip', petId=2, item='moss-bow').json['equipped'], {'neck':'moss-bow'})
        self.assertEqual(self.post('unequip', slot='head').json['equipped'], {'neck':'moss-bow'})
        self.assertEqual(self.post('unequip', slot='all').json['equipped'], {})
        self.assertEqual(self.a.get('/api/wardrobe?petId=2').json['equipped'], {'neck':'moss-bow'})

    def test_failed_purchase_and_unknown_inputs_do_not_change_balance(self):
        self.assertEqual(self.post('equip', item='daisy').status_code,403)
        self.post('buy', item='blue-beret')
        self.assertEqual(self.post('buy', item='daisy').status_code,400)
        for item in ('missing', [], {}, None):
            self.assertEqual(self.post('buy', item=item).status_code,404)
        for pet in (True, 0, 5, '1', []):
            self.assertEqual(self.post('buy', petId=pet, item='moss-bow').status_code,400)
        self.assertEqual(self.post('unequip', slot=[]).status_code,400)
        self.assertEqual(self.a.get('/api/wardrobe').json['balance'],60)

    def test_guest_scope_and_origin_guard(self):
        guest=self.app.test_client()
        self.assertEqual(guest.get('/pet-shop').status_code,200)
        self.assertTrue(guest.get('/api/wardrobe').json['guest'])
        self.assertEqual(self.post('buy', client=guest, item='daisy').status_code,403)
        self.assertEqual(self.a.post('/api/wardrobe/buy',json={'petId':1,'item':'daisy'}).status_code,409)
        scope=self.a.get('/api/wardrobe').json['scope']
        self.assertEqual(self.a.post('/api/wardrobe/buy',json={},headers={'X-Profile-Scope':scope,'Origin':'https://bad.test'}).status_code,403)
        self.assertEqual(self.a.post('/api/wardrobe/buy',json=[],headers={'X-Profile-Scope':scope}).status_code,400)
        self.assertEqual(self.a.get('/api/wardrobe?petId=x').status_code,400)

    def test_concurrent_buy_charges_once(self):
        def buy(_):
            with self.app.app_context():
                return wardrobe.operate('user:1','buy',{'petId':1,'item':'daisy'})
        with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(buy,range(2)))
        self.assertEqual(self.a.get('/api/wardrobe').json['balance'],80)

    def test_old_coats_and_private_identity_are_preserved(self):
        self.post('buy', petId=3, item='coat:ginger')
        self.assertIn('ginger', self.a.get('/api/cat-market').json['owned'])
        self.assertEqual(self.post('equip',petId=3,item='coat:ginger').json['activeCoat'],'coat:ginger')
        self.assertEqual(self.post('equip',petId=1,item='coat:ginger').status_code,400)
        self.post('daily');self.post('buy',item='moss-bow')
        private=dict(id='private',model='/private.glb',name='汤圆',custom=True,task='private')
        with patch.object(pet_generation_service,'appearance',return_value=private):
            d=self.a.get('/api/wardrobe?petId=3').json
            self.assertFalse(d['compatible']);self.assertEqual(d['pet']['model'],'/private.glb')
            self.assertEqual(self.post('equip',petId=3,item='moss-bow').status_code,409)
            self.assertEqual(self.post('unequip',petId=3,slot='all').status_code,200)

    def test_travel_and_public_park_outfit(self):
        self.post('buy',item='moss-bow');self.post('equip',item='moss-bow')
        with self.app.app_context():
            self.assertEqual(portal_service.pet_spec('user:1','1')['wardrobe'][0]['id'],'moss-bow')
        scope=self.a.get('/api/portals').json['scope']
        trip=self.a.post('/api/portals/depart',json={'pet':'1','kind':'desktop','confirmed':True},headers={'X-Profile-Scope':scope}).json
        self.assertEqual(self.post('unequip',slot='all').status_code,409)
        self.a.post('/api/portals/return',json={'trip':trip['trip']},headers={'X-Profile-Scope':scope})
        joined=self.a.post('/api/park/join',json={'pet':1},headers={'X-Profile-Scope':scope})
        self.assertEqual(joined.status_code,200)
        self.assertEqual(joined.json['players'][0]['spec']['wardrobe'][0]['id'],'moss-bow')
        self.assertEqual(self.post('unequip',slot='all').status_code,409)

    def test_legacy_cycle_removed(self):
        html=self.a.get('/den?pet=1').data.decode()
        self.assertNotIn('function buildAccessories',html)
        self.assertNotIn('ps.accessory',html)
        self.assertIn('/pet-shop?pet=',html)
        self.assertIn('PetWardrobe.Controller',html)

if __name__=='__main__':unittest.main()
