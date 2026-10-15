import unittest,uuid
from types import SimpleNamespace
from unittest.mock import patch
from test_companion import CompanionTests as Base
class RelationshipTests(unittest.TestCase):
 setUp=Base.setUp
 tearDown=Base.tearDown
 def post(self,kind,target='',event=None,c=None):
  c=c or self.a;scope=c.get('/api/cat-agent').json['scope']
  return c.post('/api/cat-agent/relationship-event',json=dict(kind=kind,target=target,event=event or uuid.uuid4().hex),headers={'X-Profile-Scope':scope})
 def test_facts_idempotency_and_no_offline_story(self):
  event=uuid.uuid4().hex
  with patch('app.services.cat_relationship_service.time',SimpleNamespace(time=lambda:1800000000)):
   a=self.post('play','ball',event).json
   self.assertEqual(a['counts']['play'],1)
   self.assertEqual(self.post('play','ball',event).json['counts']['play'],1)
   self.assertEqual(self.post('play','ball').json['counts']['play'],1)
  with patch('app.services.cat_relationship_service.time',SimpleNamespace(time=lambda:1800086400)):
   b=self.a.get('/api/cat-agent/relationship').json
   self.assertEqual(b['counts']['play'],0);self.assertEqual(a['familiarity'],b['familiarity']);self.assertEqual(b['favoriteToy'],'ball')
  self.assertIsNone(self.b.get('/api/cat-agent/relationship').json['favoriteToy'])
 def test_passive_care_does_not_farm_relationship(self):
  self.post('meal');self.post('sip');self.post('explore','garden')
  d=self.a.get('/api/cat-agent/relationship').json
  self.assertEqual(d['familiarity'],0);self.assertEqual(d['days'],0)
  self.assertEqual(d['counts']['feed'],1);self.assertEqual(d['counts']['drink'],1)
 def test_progression_schedule_clear_and_validation(self):
  for day in range(7):
   for n in range(9):
    with patch('app.services.cat_relationship_service.time',SimpleNamespace(time=lambda:1800000000+86400*day+n*60)):
     if n==0:self.post('visit')
     self.post('pet','garden')
  d=self.a.get('/api/cat-agent/relationship').json
  self.assertEqual(d['days'],7);self.assertEqual(d['familiarity'],1);self.assertEqual(d['preferredPlace'],'garden');self.assertIsNotNone(d['regularWindow'])
  self.assertEqual(self.post('play','unknown').status_code,400);self.assertEqual(self.post('invent_story').status_code,400);self.assertEqual(self.post([]).status_code,400);self.assertEqual(self.post('pet','unknown-place').status_code,400)
  scope=self.a.get('/api/cat-agent').json['scope']
  self.assertEqual(self.a.post('/api/cat-agent/relationship-clear',json={}).status_code,409)
  cleared=self.a.post('/api/cat-agent/relationship-clear',json={},headers={'X-Profile-Scope':scope}).json
  self.assertEqual(cleared['days'],0);self.assertEqual(cleared['personality'],d['personality'])
if __name__=='__main__':unittest.main()
