"""Isolated storage, decision boundaries and speaker prompt tests (no real identities)."""
import json
import unittest
from unittest.mock import patch
import numpy as np
from test_companion import CompanionTests
from app.services import voiceprint_service as v


class VoiceprintTests(unittest.TestCase):
    setUp = CompanionTests.setUp
    tearDown = CompanionTests.tearDown

    def enroll(self, client=None, name='小林'):
        with patch.object(v,'samples',return_value=np.zeros(96000)), patch.object(v,'embeddings',return_value=np.tile([1.,0.,0.],(3,1))):
            return (client or self.a).post('/api/voiceprint/enroll?name='+name,data=b'00'*16000,content_type='application/octet-stream')

    def test_scoped_enrollment_delete_and_toggle(self):
        a=self.enroll();self.assertEqual(a.status_code,200);self.assertTrue(a.json['enabled'])
        self.assertNotIn('vectors',str(a.json));self.assertEqual(self.b.get('/api/voiceprint').json['profiles'],[])
        pid=a.json['profiles'][0]['id'];self.b.delete('/api/voiceprint/'+pid)
        self.assertEqual(len(self.a.get('/api/voiceprint').json['profiles']),1)
        self.assertFalse(self.a.patch('/api/voiceprint',json={'enabled':False}).json['enabled'])
        self.a.delete('/api/voiceprint/'+pid);self.assertEqual(self.a.get('/api/voiceprint').json['profiles'],[])

    def test_limits_and_validation(self):
        self.assertEqual(self.a.patch('/api/voiceprint',json=['bad']).status_code,400)
        self.assertEqual(self.a.patch('/api/voiceprint',json={'enabled':True},headers={'Origin':'https://elsewhere.test'}).status_code,403)
        self.assertEqual(self.a.post('/api/voiceprint/enroll?name=bad%0Ainstruction',data=b'00').status_code,400)
        for _ in range(5):self.assertEqual(self.enroll().status_code,200)
        self.assertEqual(self.enroll().status_code,400)

    def test_similarity_uncertainty_and_ambiguous_match(self):
        row={'name':'A','vectors':json.dumps([[1,0,0]]*3)}
        self.assertEqual(v.match(np.array([1,0,0]),[row])['kind'],'familiar')
        self.assertEqual(v.match(np.array([0,1,0]),[row])['kind'],'unfamiliar')
        self.assertEqual(v.match(np.array([.7,.714,0]),[row])['kind'],'uncertain')
        self.assertEqual(v.match(np.array([1,0,0]),[row,dict(row,name='B')])['kind'],'uncertain')
        with self.assertRaises(ValueError):v.samples(bytes(16000*2))

    def test_same_turn_instructions_and_scope(self):
        scope=self.enroll().json['scope']
        self.assertEqual(self.a.post('/api/voiceprint/identify',data=b'00'*16000,content_type='application/octet-stream').status_code,409)
        self.a.post('/api/companion/memories',json={'category':'likes','value':'PRIVATE_HOBBY'})
        with patch.object(v,'identify',return_value={'kind':'familiar','name':'小林'}):
            r=self.a.post('/api/voiceprint/identify?petId=1&surface=den',headers={'X-Profile-Scope':scope},data=b'00'*16000,content_type='application/octet-stream')
        self.assertEqual(r.status_code,200);self.assertIn('小林',r.json['instructions']);self.assertNotIn('PRIVATE_HOBBY',r.json['instructions'])
        self.assertEqual(self.a.get('/api/companion/history').json['messages'],[])

    def test_short_voice_is_neutral_and_disabled_skips_encoder(self):
        self.enroll()
        with self.app.test_request_context():
            from flask import session
            from app.services.companion_service import owner_key
            session['user_id']='alice';session['auth_kind']='user'
            with patch.object(v,'embeddings') as encode:
                self.assertEqual(v.identify(owner_key(),b'00')['kind'],'uncertain');encode.assert_not_called()
                v.set_enabled(owner_key(),False)
                self.assertEqual(v.identify(owner_key(),bytes(64000))['kind'],'uncertain');encode.assert_not_called()

if __name__=='__main__':unittest.main(verbosity=2)
