import unittest,uuid
from concurrent.futures import ThreadPoolExecutor
from test_companion import CompanionTests as Base
from app.services import supply_service as supplies
from app.db import get_db
class SupplyTests(unittest.TestCase):
 setUp=Base.setUp
 tearDown=Base.tearDown
 def post(self,op,data=None,c=None):
  c=c or self.a;scope=c.get('/api/supplies').json['scope']
  return c.post('/api/supplies/'+op,json={'token':uuid.uuid4().hex,**(data or {})},headers={'X-Profile-Scope':scope})
 def test_wallet_stock_daily_and_isolation(self):
  self.assertEqual(self.post('daily').json['inventory']['kibble'],3)
  self.assertEqual(self.post('daily').json['inventory']['kibble'],3)
  d=self.post('buy',dict(item='kibble',quantity=2,price=0,owner='user:2')).json
  self.assertEqual(d['balance'],140);self.assertEqual(d['inventory']['kibble'],5)
  self.assertEqual(self.a.get('/api/cat-market').json['balance'],140)
  self.assertEqual(self.b.get('/api/supplies').json['inventory'],{})
 def test_no_overdraft_and_permanent_toy(self):
  self.assertEqual(self.post('buy',dict(item='dinner',quantity=20)).status_code,400)
  self.assertEqual(self.post('buy',dict(item='kibble',quantity=True)).status_code,400)
  self.assertEqual(self.post('buy',dict(item='star_ball')).json['balance'],100)
  self.assertEqual(self.post('buy',dict(item='star_ball')).status_code,409)
  self.assertEqual(self.post('use',dict(item='cloud_bone',pet='3')).status_code,403)
 def test_duplicate_network_retry_and_concurrency(self):
  data=dict(token='same-request-123',item='dinner',quantity=2)
  def buy(_):
   with self.app.app_context():return supplies.operate('user:1','buy',data)
  with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(buy,range(2)))
  s=self.a.get('/api/supplies').json;self.assertEqual(s['balance'],110);self.assertEqual(s['inventory']['dinner'],2)
  self.assertEqual(self.post('buy',{**data,'quantity':1}).status_code,409)
 def test_delivery_reservation_cancel_and_lease(self):
  self.post('daily');d=self.post('use',dict(item='kibble',pet='3')).json
  self.assertEqual(d['inventory']['kibble'],2);delivery=d['deliveries'][0]['id']
  self.assertEqual(self.post('use',dict(item='water',pet='3')).status_code,409)
  self.assertIsNone(self.post('claim',dict(pet='3',client='client-B123'),c=self.b).json['delivery'])
  self.assertEqual(self.post('claim',dict(pet='3',client='client-A123')).json['delivery']['id'],delivery)
  self.assertIsNone(self.post('claim',dict(pet='3',client='client-B123')).json['delivery'])
  self.assertEqual(self.post('cancel',dict(delivery=delivery)).status_code,409)
  self.assertEqual(self.post('complete',dict(pet='3',client='client-B123',delivery=delivery)).status_code,409)
  self.assertEqual(self.post('complete',dict(pet='3',client='client-A123',delivery=delivery)).status_code,200)
  self.assertEqual(self.post('complete',dict(pet='3',client='client-A123',delivery=delivery)).status_code,200)
  s=self.a.get('/api/supplies').json;self.assertEqual(s['deliveries'][0]['status'],'completed');self.assertEqual(s['inventory']['kibble'],2)
  d=self.post('use',dict(item='kibble',pet='3')).json['deliveries'][0]['id']
  self.assertEqual(self.post('cancel',dict(delivery=d)).json['inventory']['kibble'],2)
 def test_free_water_and_guest_and_scope(self):
  self.assertEqual(self.post('use',dict(item='water',pet='1')).json['balance'],160)
  self.assertEqual(self.post('complete',dict(pet='1',client='client-A123')).status_code,400)
  guest=self.app.test_client();self.assertEqual(guest.get('/supplies').status_code,200)
  self.assertEqual(self.post('daily',c=guest).status_code,403)
  self.assertEqual(self.a.post('/api/supplies/daily',json={'token':'request-123'}).status_code,409)
  scope=self.a.get('/api/supplies').json['scope']
  self.assertEqual(self.a.post('/api/supplies/daily',json={'token':'request-123'},headers={'X-Profile-Scope':scope,'Origin':'https://elsewhere.invalid'}).status_code,403)
 def test_permanent_toy_survives_use(self):
  self.post('buy',dict(item='star_ball'));d=self.post('use',dict(item='star_ball',pet='2')).json
  self.assertEqual(d['inventory']['star_ball'],1);self.assertEqual(d['balance'],100)
 def test_lease_expiry_can_recover(self):
  d=self.post('use',dict(item='water',pet='4')).json['deliveries'][0]['id']
  self.post('claim',dict(pet='4',client='first-tab-123'))
  with self.app.app_context():
   with get_db() as db:db.execute('UPDATE supply_deliveries SET expires=0 WHERE id=?',(d,))
  self.assertEqual(self.post('claim',dict(pet='4',client='second-tab-123')).json['delivery']['id'],d)
if __name__=='__main__':unittest.main()
