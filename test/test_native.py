"""Isolated native sessions and durable business writes, never production data."""
import unittest
from unittest.mock import patch
from test_mobile import MobileTests
from app.db import get_db


class NativeTests(unittest.TestCase):
    setUpClass = classmethod(MobileTests.setUpClass.__func__)
    setUp = MobileTests.setUp
    tearDown = MobileTests.tearDown

    def test_realtime_ticket_is_bound_to_session_and_voice(self):
        from app.services import companion_service, voiceprint_service
        from app.routes.realtime import _rate_hits
        _rate_hits.clear()
        alice, bob = self.auth(), self.auth('bob')
        owner = 'user:' + str(self.client.get('/api/native/v1/account', headers=alice).json['accountId'])
        payload = dict(profileRevision=0, customVoice=None, token='fake-short-token',
                       config={}, wsBaseUrl='wss://example.invalid')
        with self.app.app_context():
            payload['profileRevision'] = companion_service.settings(owner)['revision']
        with patch('app.services.realtime_service.build_realtime_session', return_value=payload):
            response = self.client.post('/api/native/v1/realtime/session', json={'petId': 3}, headers=alice)
        self.assertEqual(response.status_code, 200)
        ticket = response.json['ticket']
        def check(headers, value=ticket):
            return self.client.post('/api/native/v1/realtime/check', json={'ticket': value}, headers=headers)
        self.assertEqual(check(alice).status_code, 200)
        self.assertEqual(check(bob).status_code, 409)
        self.assertEqual(check(alice, 'tampered').status_code, 409)
        again = self.auth()
        self.assertEqual(check(again).status_code, 409)
        with patch('app.services.pet_voice_service.active', return_value={'id':'new-voice'}):
            self.assertEqual(check(alice).status_code, 409)
        with patch.object(voiceprint_service, 'requested_enabled', return_value=True):
            self.assertEqual(check(alice).status_code, 409)
            self.assertEqual(self.client.post('/api/native/v1/realtime/session', json={'petId':3}, headers=alice).status_code,409)
        body = dict(ticket=ticket, message='你好', assistantText='我在这里', requestId='native-live-round-001', petId=4)
        first = self.client.post('/api/native/v1/realtime/round', json=body, headers=alice)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json['pet']['id'], 3)
        repeat = self.client.post('/api/native/v1/realtime/round', json=body, headers=alice)
        self.assertTrue(repeat.json['duplicate'])
        self.assertEqual(self.client.post('/api/native/v1/realtime/round', json=body, headers=bob).status_code,409)
        with self.app.app_context():
            db=get_db();db.execute('UPDATE companion_owners SET revision=revision+1 WHERE owner=?',(owner,));db.commit()
        self.assertEqual(check(alice).status_code, 409)

    def auth(self, name='alice'):
        response = self.client.post('/api/native/v1/session', json={
            'username': name, 'password': 'tablet-test-password'})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('Set-Cookie', response.headers)
        return {'Authorization': 'Bearer ' + response.json['token']}

    def test_account_bowls_commit_and_refill_are_idempotent(self):
        alice = self.auth()
        def post(op, **body):
            return self.client.post('/api/native/v1/supplies/'+op, json=body, headers=alice)
        self.assertEqual(post('daily',token='care-daily-0001').status_code,200)
        eaten=post('bowl-consume',pet='3',kind='food',token='care-meal-00001')
        self.assertEqual(eaten.status_code,200)
        self.assertEqual(eaten.json['bowls']['3']['food'],75)
        repeated=post('bowl-consume',pet='3',kind='food',token='care-meal-00001')
        self.assertEqual(repeated.json['bowls']['3']['food'],75)
        self.assertEqual(post('bowl-consume',pet='3',kind='water',token='care-meal-00001').status_code,409)
        filled=post('bowl-refill',pet='3',kind='food',token='care-refill-001')
        self.assertEqual(filled.json['bowls']['3']['food'],100)
        self.assertEqual(filled.json['inventory']['kibble'],2)
        repeat=post('bowl-refill',pet='3',kind='food',token='care-refill-001')
        self.assertEqual(repeat.json['inventory']['kibble'],2)
        self.assertEqual(post('bowl-refill',pet='3',kind='food',token='care-refill-002').status_code,409)
        self.assertEqual(post('bowl-consume',pet='4',kind='food',token='care-wrong-pet').status_code,400)

    def test_identity_cookie_isolation_revoke_and_expire(self):
        self.assertEqual(self.client.get('/api/native/v1/account').status_code, 401)
        self.client.post('/api/mobile/v1/session', json={'username': 'alice', 'password': 'tablet-test-password'})
        self.assertEqual(self.client.get('/api/native/v1/account').status_code, 401)
        alice, bob = self.auth(), self.auth('bob')
        self.assertEqual(self.client.get('/api/native/v1/account', headers=alice).json['username'], 'alice')
        self.assertEqual(self.client.get('/api/native/v1/account', headers=bob).json['username'], 'bob')
        self.assertEqual(self.client.post('/api/native/v1/farm/start', json={'owner':'user:2'}, headers=alice).status_code, 400)
        self.assertEqual(self.client.delete('/api/native/v1/session', json={}, headers=alice).status_code, 200)
        self.assertEqual(self.client.get('/api/native/v1/account', headers=alice).status_code, 401)
        self.assertEqual(self.client.get('/api/native/v1/account', headers=bob).status_code, 200)
        with self.app.app_context():
            db = get_db(); db.execute('UPDATE native_sessions SET expires=0'); db.commit()
        self.assertEqual(self.client.get('/api/native/v1/account', headers=bob).status_code, 401)

    def test_inventory_transactions_retry_and_account_isolation(self):
        alice, bob = self.auth(), self.auth('bob')
        def post(op, **data):
            return self.client.post('/api/native/v1/supplies/'+op, json=data, headers=alice)
        self.assertEqual(post('daily', token='native-daily-0001').status_code, 200)
        first = post('buy', token='native-buy-00001', item='kibble', quantity=1)
        self.assertEqual(first.status_code, 200)
        again = post('buy', token='native-buy-00001', item='kibble', quantity=1)
        self.assertEqual(first.json['balance'], again.json['balance'])
        self.assertEqual(first.json['inventory'], again.json['inventory'])
        self.assertEqual(post('buy', token='native-buy-00001', item='kibble', quantity=2).status_code, 409)
        self.assertEqual(self.client.get('/api/native/v1/supplies', headers=bob).json['inventory'], {})

    def test_farm_persists_and_rejects_legacy_map_placement(self):
        alice = self.auth()
        first = self.client.post('/api/native/v1/farm/start', json={'token':'native-farm-start'}, headers=alice)
        self.assertEqual(first.status_code, 200)
        self.assertTrue(first.json['started'])
        self.assertEqual(self.client.post('/api/native/v1/farm/place', json={'token':'native-place-000'}, headers=alice).status_code, 409)
        self.client.delete('/api/native/v1/session', json={}, headers=alice)
        self.assertTrue(self.client.get('/api/native/v1/farm', headers=self.auth()).json['started'])
        self.assertFalse(self.client.get('/api/native/v1/farm', headers=self.auth('bob')).json['started'])

    def test_chat_and_voice_owner_validation(self):
        alice = self.auth()
        response = self.client.post('/api/native/v1/chat', headers=alice, json={
            'petId':3,'message':'你好','requestId':'native-chat-0001'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get('/api/native/v1/voices?petId=3', headers=alice).status_code, 200)
        self.assertEqual(self.client.post('/api/native/v1/voices/selection', headers=alice,
            json={'petId':3, 'id':'another-account-voice'}).status_code, 404)
        self.assertEqual(self.client.post('/api/native/v1/voices', headers=alice, data={}).status_code, 413)

    def test_plant_care_uses_identity_and_does_not_double_apply(self):
        alice = self.auth()
        def post(op, **data):
            return self.client.post('/api/native/v1/farm/'+op, headers=alice, json=data)
        post('start', token='native-garden-start')
        planted = post('plant', token='native-garden-plant', bed='bed-1', species='cosmos')
        self.assertEqual(planted.status_code, 200)
        plant = planted.json['beds'][0]['plant']['id']
        self.assertEqual(post('water',token='native-water-invalid',bed='bed-1',plant='stale').status_code,409)
        water = post('water',token='native-water-current',bed='bed-1',plant=plant)
        self.assertEqual(water.status_code,200)
        again = post('water',token='native-water-current',bed='bed-1',plant=plant)
        self.assertEqual(again.status_code,200)
        self.assertEqual(post('water',token='native-water-again00',bed='bed-1',plant=plant).status_code,409)
        self.assertEqual(post('fertilize',token='native-fertilize-001',bed='bed-1',plant=plant).status_code,200)
        self.assertEqual(post('harvest',token='native-harvest-young',bed='bed-1',plant=plant).status_code,409)

    def test_voice_snapshot_including_default_voice(self):
        from unittest.mock import patch
        alice=self.auth()
        with patch('app.routes.native.voices.active',return_value={'id':'owned-new','voice':'provider-id'}), patch('app.routes.native.voices.synthesize',return_value=b'RIFFmock') as synth:
            for expected in (None,'old-profile'):
                response=self.client.post('/api/native/v1/tts',headers=alice,json={'petId':3,'text':'你好','voiceProfileId':expected})
                self.assertEqual(response.status_code,409)
            synth.assert_not_called()
            response=self.client.post('/api/native/v1/tts',headers=alice,json={'petId':3,'text':'你好','voiceProfileId':'owned-new'})
            self.assertEqual(response.status_code,200)
            synth.assert_called_once_with('你好','provider-id')

    def test_native_registration_uses_existing_users_table(self):
        body={'username':'native-new-user','password':'native-test-pass','password2':'native-test-pass'}
        self.assertEqual(self.client.post('/api/native/v1/registration',json=body).status_code,201)
        self.assertEqual(self.client.post('/api/native/v1/registration',json=body).status_code,409)
        response=self.client.post('/api/native/v1/session',json={'username':body['username'],'password':body['password']})
        self.assertEqual(response.status_code,200)
        self.assertNotIn('Set-Cookie',response.headers)
        with self.app.app_context():
            row=get_db().execute('SELECT pwd FROM users WHERE user_name=?',(body['username'],)).fetchone()
            self.assertNotEqual(row['pwd'],body['password'])


if __name__ == '__main__':
    unittest.main()
