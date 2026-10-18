"""Public/native interoperability on a temporary DB; no production accounts."""
import math
import unittest
from unittest.mock import patch
from test_mobile import MobileTests
from test_native import NativeTests
from app.db import get_db
from app.services import park_service as park, park_navigation as nav
from app.services.native_park_navigation import route

class NativeParkTests(unittest.TestCase):
    setUpClass=classmethod(MobileTests.setUpClass.__func__)
    setUp=MobileTests.setUp
    tearDown=MobileTests.tearDown
    auth=NativeTests.auth

    def test_public_presence_shared_and_owner_bound(self):
        alice,bob=self.auth(),self.auth('bob')
        self.assertEqual(self.client.get('/api/native/v1/park').status_code,401)
        joined=self.client.post('/api/native/v1/park/join',json={'pet':3},headers=alice)
        self.assertEqual(joined.status_code,200,joined.json)
        token=joined.json['token']
        visible=self.client.get('/api/native/v1/park',headers=bob).json
        self.assertEqual(visible['count'],1)
        self.assertFalse(visible['players'][0]['mine'])
        self.assertNotIn('token',str(visible['players']))
        self.assertEqual(self.client.post('/api/native/v1/park/leave',json={'token':token},headers=bob).status_code,409)
        with self.app.app_context():
            # Same snapshot function consumed by Web/Harmony; no separate client room.
            self.assertEqual(park.snapshot('user:another')['count'],1)
        self.assertEqual(self.client.post('/api/native/v1/park/leave',json={'token':token},headers=alice).status_code,200)
        self.assertEqual(self.client.get('/api/native/v1/park',headers=bob).json['count'],0)

    def test_native_routes_avoid_all_authored_obstacles(self):
        for start,end in [((-5,0),(5,0)),((0,4),(0,-4)),((-6,2.4),(6,-2)),((5,3),(-5,-3))]:
            points=route(start,end);self.assertTrue(points)
            last=start
            for point in points:
                target=(point['x'],point['z']);self.assertTrue(nav.segment(*last,*target));last=target
            self.assertEqual(last,end)
        auth=self.auth();joined=self.client.post('/api/native/v1/park/join',json={'pet':3},headers=auth).json
        bad=self.client.post('/api/native/v1/park/route',json={'token':joined['token'],'x':.3,'z':-.8},headers=auth)
        self.assertEqual(bad.status_code,400)
        self.assertEqual(self.client.post('/api/native/v1/park/route',json={'token':'wrong','x':5,'z':0},headers=auth).status_code,409)

    def test_facility_progress_is_authoritative_and_survives_native_transport(self):
        auth=self.auth()
        with patch.object(park,'clock',return_value=1000):
            joined=self.client.post('/api/native/v1/park/join',json={'pet':3},headers=auth).json
        token=joined['token'];owner='user:'+str(self.client.get('/api/native/v1/account',headers=auth).json['accountId'])
        with self.app.app_context():
            db=get_db();db.execute('UPDATE park_presence SET x=-6,z=2.4 WHERE owner=?',(owner,));db.commit()
        def update(now,progress):
            with patch.object(park,'clock',return_value=now):
                return self.client.post('/api/native/v1/park/sync',headers=auth,json=dict(token=token,x=-6,z=2.4,yaw=0,action='idle',behavior=dict(activity='facility',autonomous=True,facility=dict(id='bridge',progress=progress))))
        self.assertEqual(update(1001,0).status_code,200)
        self.assertEqual(update(1002,8).status_code,422)
        progress=0;now=1001;length=nav.facility_length(nav.FACILITIES['bridge'])
        while progress<length:
            now+=1;progress=min(length,progress+.8);response=update(now,progress)
            self.assertEqual(response.status_code,200,response.json)
            p=response.json['players'][0];expected=nav.facility_sample(nav.FACILITIES['bridge'],progress)
            self.assertAlmostEqual(p['x'],expected['x']);self.assertAlmostEqual(p['z'],expected['z'])
        # A completed facility must first publish its return to grass before a
        # different facility can acquire the shared lane (native regression).
        body=dict(token=token,x=-6,z=2.4,yaw=0,action='idle',behavior=dict(activity='facility',autonomous=True,facility=dict(id='tunnel',progress=0)))
        with patch.object(park,'clock',return_value=now+1):
            self.assertEqual(self.client.post('/api/native/v1/park/sync',json=body,headers=auth).status_code,422)
            ground={**body,'behavior':dict(activity='explore',autonomous=True)}
            self.assertEqual(self.client.post('/api/native/v1/park/sync',json=ground,headers=auth).status_code,200)
        with patch.object(park,'clock',return_value=now+2):
            self.assertEqual(self.client.post('/api/native/v1/park/sync',json=body,headers=auth).status_code,200)
        with patch.object(park,'clock',return_value=now+15):
            self.assertEqual(self.client.get('/api/native/v1/park',headers=auth).json['count'],0)

if __name__=='__main__':unittest.main()
