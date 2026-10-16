"""Native API contracts, real password verification and isolated account behavior."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from app import create_app
from app.config import Config
from app.db import get_db, init_db
from app.llm.client import LLMError


class FakeModel:
    def __init__(self):
        self.calls = []
        self.fail = False

    def chat(self, messages, **kwargs):
        self.calls.append(messages)
        if self.fail:
            raise LLMError('test failure')
        return json.dumps({'reply': '我在这里。', 'actions': ['come'], 'memories': []})


class MobileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password_hash = generate_password_hash('tablet-test-password')

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

        class TestConfig(Config):
            TESTING = True
            SECRET_KEY = 'isolated-mobile-test-secret'
            DATABASE_PATH = str(Path(self.tmp.name) / 'test.db')

        self.model = FakeModel()
        with patch('app.GLMClient', return_value=self.model):
            self.app = create_app(TestConfig)
        self.app.extensions['llm'] = self.model
        with self.app.app_context():
            init_db()
            db = get_db()
            with db:
                db.executemany('INSERT INTO users(user_name,pwd) VALUES (?,?)',
                               [('alice', self.password_hash), ('bob', self.password_hash)])
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def login(self, client=None, name='alice'):
        return (client or self.client).post('/api/mobile/v1/session', json={
            'username': name, 'password': 'tablet-test-password'})

    def send(self, client=None, **changes):
        data = {'petId': 1, 'message': '你好', 'requestId': 'mobile-test-1234'}
        data.update(changes)
        return (client or self.client).post('/api/mobile/v1/chat', json=data)

    def test_bootstrap_has_public_contract_and_no_secrets(self):
        result = self.client.get('/api/mobile/v1/bootstrap')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['apiVersion'], 1)
        self.assertEqual(len(result.json['pets']), 4)
        self.assertEqual(result.headers['Cache-Control'], 'no-store')
        self.assertNotIn('description', result.json['pets'][0])
        self.assertEqual(set(result.json), {'apiVersion', 'appVersion', 'pets', 'maxMessageChars', 'sessionCookieName'})

    def test_companion_auth_validation_and_account_isolation(self):
        url = '/api/mobile/v1/companion?petId=1'
        self.assertEqual(self.client.get(url).status_code, 401)
        self.login()
        result = self.client.get(url)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json['petId'], 1)
        self.assertNotIn('basePersonality', result.json)
        self.assertEqual(result.headers['Cache-Control'], 'no-store')
        # Write via the existing web API, then read the same owner-scoped data natively.
        saved = self.client.post('/api/companion/memories?petId=1',
                                 json={'category': 'pet_name', 'value': '测试伙伴'})
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(self.client.get(url).json['name'], '测试伙伴')
        paused = self.client.post(url, json={'enabled': False})
        self.assertEqual(paused.status_code, 200)
        self.assertFalse(paused.json['enabled'])
        self.assertTrue(paused.json['memories'])
        self.assertFalse(self.client.get('/api/companion?petId=2').json['enabled'])
        bob = self.app.test_client()
        self.login(bob, 'bob')
        self.assertTrue(bob.get(url).json['enabled'])
        self.assertEqual(bob.get(url).json['memories'], [])
        self.assertTrue(self.client.post(url, json={'enabled': True}).json['enabled'])
        for value in ('false', 0, None):
            self.assertEqual(self.client.post(url, json={'enabled': value}).status_code, 400)
        for value in ('', '../1', '999'):
            self.assertEqual(self.client.get('/api/mobile/v1/companion?petId=' + value).status_code, 400)
        self.assertEqual(self.client.post(url, json={'enabled': False},
                                         headers={'Origin': 'https://other.example'}).status_code, 403)

    def test_login_and_logout(self):
        response = self.login()
        self.assertEqual(response.status_code, 200)
        self.assertIn('HttpOnly', response.headers['Set-Cookie'])
        self.assertEqual(self.client.get('/api/mobile/v1/session').json, {'username': 'alice'})
        self.assertEqual(self.client.post('/api/mobile/v1/logout', json={}).status_code, 200)
        self.assertEqual(self.send().status_code, 401)

    def test_wrong_password_and_unknown_user_have_same_error(self):
        wrong = self.client.post('/api/mobile/v1/session', json={'username': 'alice', 'password': 'wrong'})
        unknown = self.login(name='nobody')
        self.assertEqual((wrong.status_code, wrong.json), (unknown.status_code, unknown.json))
        self.assertEqual(wrong.status_code, 401)

    def test_bad_login_payload(self):
        for data in ([], {}, {'username': [], 'password': 'x'}, {'username': 'a', 'password': 'x' * 1025}):
            self.assertEqual(self.client.post('/api/mobile/v1/session', json=data).status_code, 400)

    def test_login_rate_limit(self):
        for _ in range(10):
            self.client.post('/api/mobile/v1/session', json={})
        response = self.login()
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers['Retry-After'], '60')

    def test_guest_manager_and_deleted_accounts_cannot_access(self):
        self.assertEqual(self.send().status_code, 401)
        with self.client.session_transaction() as session:
            session['user_id'] = 'alice'
            session['auth_kind'] = 'manager'
        self.assertEqual(self.client.get('/api/mobile/v1/history?petId=1').status_code, 401)
        self.login()
        with self.app.app_context():
            db = get_db()
            with db:
                db.execute('DELETE FROM users WHERE user_name=?', ('alice',))
        self.assertEqual(self.send().status_code, 401)

    def test_chat_history_and_account_isolation(self):
        self.login()
        response = self.send(message='Alice private message')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['actions'], [])
        bob = self.app.test_client()
        self.login(bob, 'bob')
        self.assertEqual(bob.get('/api/mobile/v1/history?petId=1&userId=alice').json['messages'], [])
        self.send(bob, userId='alice', chatHistory=[{'role': 'user', 'content': 'forged'}])
        self.assertNotIn('Alice private message', str(self.model.calls[-1]))
        self.assertNotIn('forged', str(self.model.calls[-1]))
        history = self.client.get('/api/mobile/v1/history?petId=1').json['messages']
        self.assertEqual([m['role'] for m in history], ['user', 'assistant'])
        self.assertEqual(self.client.get('/api/mobile/v1/history?petId=2').json['messages'], [])

    def test_retry_uses_one_completed_turn(self):
        self.login()
        self.send()
        retry = self.send()
        self.assertTrue(retry.json['duplicate'])
        self.assertEqual(len(self.model.calls), 1)
        self.assertEqual(len(self.client.get('/api/mobile/v1/history?petId=1').json['messages']), 2)

    def test_model_failure_can_retry_without_fake_history(self):
        self.login()
        self.model.fail = True
        self.assertEqual(self.send().status_code, 503)
        self.assertEqual(self.client.get('/api/mobile/v1/history?petId=1').json['messages'], [])
        self.model.fail = False
        self.assertEqual(self.send().status_code, 200)

    def test_inflight_retry_does_not_call_model_twice(self):
        self.login()
        with self.app.app_context():
            gate = self.app.extensions['mobile_chat_gate']
            gate['active'].add((1, 1, 'mobile-test-1234'))
        self.assertEqual(self.send().status_code, 409)
        self.assertEqual(self.model.calls, [])
        gate['active'].clear()
        self.assertEqual(self.send().status_code, 200)

    def test_invalid_pet_and_message(self):
        self.login()
        for changes in ({'petId': True}, {'petId': 999}, {'petId': '1'}, {'message': []},
                        {'message': ''}, {'message': 'x' * 2001}, {'requestId': 'bad'}):
            self.assertEqual(self.send(**changes).status_code, 400, changes)
        for pet in ('', 'true', '-1', '1.1', '999'):
            self.assertEqual(self.client.get('/api/mobile/v1/history?petId=' + pet).status_code, 400)

    def test_cross_site_and_oversized_requests(self):
        for headers in ({'Origin': 'https://evil.example'}, {'Sec-Fetch-Site': 'cross-site'}):
            self.assertEqual(self.client.post('/api/mobile/v1/session', json={}, headers=headers).status_code, 403)
        self.assertEqual(self.client.post('/api/mobile/v1/session', data='{}').status_code, 415)
        self.assertEqual(self.client.post('/api/mobile/v1/session', json={'x': 'x' * 17000}).status_code, 413)

    def test_web_and_native_share_account_history(self):
        self.login()
        self.send(message='Tablet message')
        web = self.app.test_client()
        with web.session_transaction() as session:
            session['user_id'] = 'alice'
            session['auth_kind'] = 'user'
        self.assertEqual(web.get('/api/companion/history?petId=1').json['messages'][0]['content'], 'Tablet message')
        self.assertEqual(web.post('/get_gpt_response', json={'petId': 1, 'message': 'Web message'}).status_code, 200)
        self.assertEqual(len(self.client.get('/api/mobile/v1/history?petId=1').json['messages']), 4)


if __name__ == '__main__':
    unittest.main()
