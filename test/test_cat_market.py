import unittest
from concurrent.futures import ThreadPoolExecutor
from test_companion import CompanionTests as Base
from app.services import cat_market_service as market,portal_service as portal,cat_agent_service as agent
from app.db import get_db
class CatMarketTests(unittest.TestCase):
 setUp=Base.setUp
 tearDown=Base.tearDown
 def post(self,op,data=None,c=None):
  c=c or self.a;scope=c.get('/api/cat-market').json['scope']
  return c.post('/api/cat-market/'+op,json=data or {},headers={'X-Profile-Scope':scope})
 def test_starter_guest_and_account_isolation(self):
  for _ in range(3):self.assertEqual(self.a.get('/api/cat-market').json['balance'],160)
  self.assertEqual(self.post('buy',{'coat':'ginger','price':0,'owner':'user:2'}).json['balance'],40)
  self.assertEqual(self.b.get('/api/cat-market').json['balance'],160)
  guest=self.app.test_client();self.assertEqual(guest.get('/cat-market').status_code,200)
  self.assertEqual(guest.get('/api/cat-market').json['balance'],0)
  self.assertEqual(self.post('daily',c=guest).status_code,403)
  self.assertEqual(self.a.post('/api/cat-market/buy',json={'coat':'ginger'}).status_code,409)
 def test_buy_equip_and_identity(self):
  self.assertEqual(self.post('equip',{'coat':'ragdoll'}).status_code,403)
  self.assertEqual(self.post('buy',{'coat':'ragdoll'}).status_code,400)
  self.assertEqual(self.post('buy',{'coat':'missing'}).status_code,404)
  self.post('buy',{'coat':'ginger'})
  self.assertEqual(self.post('buy',{'coat':'ginger'}).json['balance'],40)
  self.assertEqual(self.post('equip',{'coat':'ginger'}).json['active'],'ginger')
  with self.app.app_context():self.assertTrue(portal.pet_spec('user:1','3')['model'].endswith('ginger.glb'))
  html=self.a.get('/den?pet=3').data.decode();self.assertIn('ginger.glb',html)
  scope=self.a.get('/api/portals').json['scope'];trip=self.a.post('/api/portals/depart',json=dict(pet='3',kind='desktop',confirmed=True),headers={'X-Profile-Scope':scope}).json
  self.assertEqual(self.post('equip',{'coat':'tabby'}).status_code,409)
  pair=self.a.post('/api/portals/desktop/pair',json={'code':trip['code']}).json;self.assertTrue(pair['pet']['model'].endswith('ginger.glb'))
  self.a.post('/api/portals/return',json={'trip':trip['trip']},headers={'X-Profile-Scope':scope})
  self.assertEqual(self.post('equip',{'coat':'tabby'}).json['active'],'tabby')
 def test_daily_and_earned_caps(self):
  for _ in range(3):self.assertEqual(self.post('daily').json['balance'],190)
  with self.app.app_context():
   target=next(iter(agent.TARGETS))
   for i in range(9):agent.record('user:1',dict(target=target,result='completed',event='market-event-'+str(i)))
   agent.record('user:1',dict(target=target,result='completed',event='market-event-0'))
   with get_db():
    for i in range(8):market.reward('user:1','journey','journey-'+str(i))
  self.assertEqual(self.a.get('/api/cat-market').json['balance'],245)
 def test_concurrent_duplicate_purchase_charges_once(self):
  def buy(_):
   with self.app.app_context():return market.operate('user:1','buy',{'coat':'ginger'})
  with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(buy,range(2)))
  state=self.a.get('/api/cat-market').json;self.assertEqual(state['balance'],40)
  self.assertEqual(len([r for r in state['ledger'] if r['kind']=='purchase']),1)
 def test_home_shortcuts(self):
  html=self.a.get('/').data.decode();self.assertIn('href="/cat-agent-monitor"',html);self.assertIn('href="/cat-market"',html)
if __name__=='__main__':unittest.main()
