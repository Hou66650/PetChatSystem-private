"""Two signed-in owners, isolated SQLite; never touches production presence."""
import unittest
from unittest.mock import patch
import test_companion as fixtures
from app.services import park_service as park

class ParkTests(unittest.TestCase):
    setUp = fixtures.CompanionTests.setUp
    tearDown = fixtures.CompanionTests.tearDown
    def post(self, op, data, client=None):
        c = client or self.a
        scope = c.get('/api/park').json['scope']
        return c.post('/api/park/'+op, json=data, headers={'X-Profile-Scope':scope})
    def sample(self, joined, **kw):
        p = next(p for p in joined['players'] if p['mine'])
        return dict(token=joined['token'], x=p['x'], z=p['z'], yaw=0, **kw)
    def test_two_accounts_sync_leave_and_no_private_identity(self):
        with patch.object(park, 'clock', return_value=100):
            a=self.post('join', {'pet':1}).json
            b=self.post('join', {'pet':2}, self.b).json
            self.assertEqual(b['count'],2)
            self.assertEqual(sum(p['mine'] for p in b['players']),1)
            self.assertNotIn('owner',str(b['players']))
            self.assertNotIn('token',str(b['players']))
        with patch.object(park,'clock',return_value=101):
            self.assertEqual(self.post('sync',self.sample(a,action='happy')).status_code,200)
            state=self.b.get('/api/park').json
            self.assertEqual(next(p['action'] for p in state['players'] if not p['mine']),'happy')
            self.assertEqual(self.post('leave',{'token':a['token']},self.b).status_code,409)
            self.assertEqual(self.post('leave',{'token':'猫'*48}).status_code,409)
            self.assertEqual(self.post('leave',{'token':a['token']}).status_code,200)
            self.assertEqual(self.b.get('/api/park').json['count'],1)
    def test_expiry_duplicate_tab_and_restart(self):
        with patch.object(park,'clock',return_value=100):
            a=self.post('join',{'pet':1}).json
            fresh=self.post('join',{'pet':2}).json
            self.assertEqual(fresh['count'],1)
            self.assertEqual(self.post('leave',{'token':a['token']}).status_code,409)
        with patch.object(park,'clock',return_value=113):
            self.assertEqual(self.a.get('/api/park').json['count'],0)
            self.assertEqual(self.post('sync',self.sample(fresh)).status_code,409)
    def test_guests_csrf_schema_and_private_assets(self):
        self.assertEqual(self.app.test_client().post('/api/park/join',json={'pet':1}).status_code,401)
        self.assertEqual(self.a.post('/api/park/join',json={'pet':1}).status_code,409)
        self.assertEqual(self.a.post('/api/park/join',json={'pet':1},headers={'Origin':'https://bad.test'}).status_code,403)
        for pet in (True,0,5,'1',[]):
            self.assertEqual(self.post('join',{'pet':pet}).status_code,400)
        with patch.object(park.portal_service,'pet_spec',return_value={'custom':True,'model':'/private'}):
            self.assertEqual(self.post('join',{'pet':3}).status_code,409)
        self.assertEqual(self.a.get('/park').status_code,200)
    def test_position_validation_rate_and_capacity(self):
        with patch.object(park,'clock',return_value=100):
            a=self.post('join',{'pet':1}).json
            self.assertEqual(self.post('sync',self.sample(a)).status_code,429)
        with patch.object(park,'clock',return_value=101):
            for value in (float('nan'),float('inf'),True,'x'):
                data=self.sample(a);data['x']=value
                self.assertEqual(self.post('sync',data).status_code,400)
            data=self.sample(a);data['x']=100
            self.assertEqual(self.post('sync',data).status_code,400)
            self.assertEqual(self.post('sync',self.sample(a,action=[])).status_code,400)
            with patch.object(park,'CAPACITY',1):
                self.assertEqual(self.post('join',{'pet':2},self.b).status_code,409)
    def test_growth_stage_is_server_resolved(self):
        scope=self.a.get('/api/companion').json['scope']
        self.a.post('/api/growth/1',json={'mode':'adopt','name':'小球','personality':'gentle'},headers={'X-Profile-Scope':scope})
        result=self.post('join',{'pet':1,'model':'https://bad.test/a.glb','owner':'user:2'}).json
        p=next(p for p in result['players'] if p['mine'])
        self.assertEqual(p['spec']['name'],'小球')
        self.assertTrue(p['spec']['model'].startswith('/static/models/pet-growth-'))

if __name__=='__main__':unittest.main()
