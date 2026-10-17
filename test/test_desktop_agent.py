import json
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from test_portals import PortalTests as Base
from app.db import get_db
from app.services import desktop_agent_service as agent, companion_service as memory


class DesktopAgentTests(unittest.TestCase):
    setUp=Base.setUp
    tearDown=Base.tearDown
    post=Base.post
    start=Base.start
    private_pet=Base.private_pet

    def pair(self,roaming=True):
        d=self.start().json;self.trip=d['trip']
        self.auth={'Authorization':'Bearer '+self.a.post('/api/portals/desktop/pair',json={'code':d['code']}).json['token']}
        self.version=self.call('manifest').json['version']
        if roaming:
            self.call('ready');self.post('depart-complete',{'trip':self.trip});self.call('arrived')

    def call(self,op,data=None,client=None):
        return (client or self.a).post('/api/portals/desktop/'+op,json=data or {},headers=self.auth)

    def chat(self,rid='request-0001',message='你好',client=None):
        return self.call('chat',dict(requestId=rid,version=self.version,message=message),client)

    def test_roaming_authorization_and_no_body_identity(self):
        self.pair(False)
        self.assertEqual(self.chat().json['code'],'TRIP_NOT_READY')
        self.call('ready');self.post('depart-complete',{'trip':self.trip});self.call('arrived')
        forged=self.call('chat',dict(requestId='request-0001',version=self.version,message='你好',petId=1))
        self.assertEqual(forged.status_code,400)
        self.model.plan(actions=[{'type':'happy','quote':'开心'}],reply='已完成')
        response=self.chat(message='开心',client=self.b) # Cookie B cannot override token A.
        self.assertEqual(response.status_code,200);self.assertEqual(response.json['actions'],[])
        with self.app.app_context():
            self.assertEqual([tuple(r) for r in get_db().execute('SELECT DISTINCT owner,pet_id FROM companion_messages')],[('user:1',3)])
        self.assertIn('没有提醒',self.model.calls[-1][0]['content'])

    def test_retry_conflict_and_restart_with_memory(self):
        self.pair();first=self.chat();self.assertEqual(first.status_code,200)
        self.assertTrue(self.chat().json['duplicate']);self.assertEqual(len(self.model.calls),1)
        self.assertEqual(self.chat(message='different').json['code'],'REQUEST_CONFLICT')
        with self.app.app_context():self.app.extensions['desktop_reply_cache'][1].clear()
        self.assertEqual(self.chat().json['reply'],first.json['reply']);self.assertEqual(len(self.model.calls),1)

    def test_memory_off_cache_expiry_never_regenerates_and_no_plaintext(self):
        self.a.patch('/api/companion',json={'enabled':False});self.pair()
        self.assertEqual(self.chat(message='private sentence').status_code,200)
        self.assertTrue(self.chat(message='private sentence').json['duplicate'])
        with self.app.app_context():
            db=get_db();self.assertEqual(db.execute('SELECT count(*) FROM companion_messages').fetchone()[0],0)
            self.assertNotIn('private sentence',str([tuple(r) for r in db.execute('SELECT * FROM desktop_agent_requests')]))
        with patch.object(agent.time,'monotonic',return_value=agent.time.monotonic()+601):
            self.assertEqual(self.chat(message='private sentence').json['code'],'RESULT_UNKNOWN')
        self.assertEqual(len(self.model.calls),1)

    def test_concurrent_same_request_calls_model_once(self):
        self.pair();entered=threading.Event();release=threading.Event()
        self.model.hook=lambda:(entered.set(),release.wait(10))
        with ThreadPoolExecutor(max_workers=1) as pool:
            future=pool.submit(lambda:self.chat(client=self.app.test_client()))
            self.assertTrue(entered.wait(5))
            try:self.assertEqual(self.chat().json['code'],'RESULT_UNKNOWN')
            finally:release.set()
            self.assertEqual(future.result().status_code,200)
        self.assertEqual(len(self.model.calls),1)

    def test_recall_while_model_in_flight_does_not_archive_or_respond(self):
        self.pair()
        self.model.hook=lambda:self.post('return',{'trip':self.trip})
        self.assertEqual(self.chat().json['code'],'TRIP_ENDED')
        with self.app.app_context():self.assertEqual(get_db().execute('SELECT count(*) FROM companion_messages').fetchone()[0],0)

    def test_revision_change_during_model_and_old_reply_invalidation(self):
        self.pair();self.assertEqual(self.chat().status_code,200)
        self.a.patch('/api/companion',json={'enabled':False})
        self.assertEqual(self.chat().json['code'],'CONTEXT_CHANGED')
        self.version=self.call('manifest').json['version']
        self.model.hook=lambda:self.a.patch('/api/companion',json={'enabled':True})
        self.assertEqual(self.chat('request-0002').json['code'],'CONTEXT_CHANGED')

    def test_original_voice_selection_and_speech_replay(self):
        self.app.config['GLM_API_KEY']='test-only';self.pair();self.chat()
        body=dict(requestId='speech-0001',replyRequestId='request-0001',version=self.version)
        with patch.object(agent.voice,'synthesize',return_value=b'RIFF-test') as speak:
            result=self.call('speech',body);self.assertEqual(result.status_code,200)
            speak.assert_called_once_with('我在这里。',self.app.config['PET_TTS_VOICES'][3])
            self.assertTrue(self.call('speech',body).json['duplicate']);self.assertEqual(speak.call_count,1)
            self.app.extensions['desktop_reply_cache'][1].clear()
            self.assertEqual(self.call('speech',body).json['code'],'RESULT_UNKNOWN');self.assertEqual(speak.call_count,1)

    def test_voice_change_and_late_audio_are_rejected(self):
        self.app.config['GLM_API_KEY']='test-only';self.pair();self.chat()
        def synth(*args):
            self.a.patch('/api/companion',json={'enabled':False});return b'RIFF-test'
        with patch.object(agent.voice,'synthesize',side_effect=synth):
            r=self.call('speech',dict(requestId='speech-0001',replyRequestId='request-0001',version=self.version))
            self.assertEqual(r.json['code'],'CONTEXT_CHANGED');self.assertNotIn('audio',r.json)

    def test_selected_custom_voice_is_used_and_changes_invalidate_context(self):
        self.app.config['GLM_API_KEY']='test-only';self.pair()
        with self.app.app_context():
            db=get_db()
            db.execute("INSERT INTO pet_voice_profiles VALUES ('voice-1','user:1',3,'我的声音','ready','owner-custom','','','',0,5,0,'clone-1')")
            db.execute("INSERT INTO pet_voice_selection VALUES ('user:1',3,'voice-1')");db.commit()
        self.assertEqual(self.chat().json['code'],'CONTEXT_CHANGED')
        self.version=self.call('manifest').json['version'];self.chat()
        with patch.object(agent.voice,'synthesize',return_value=b'RIFF-test') as speak:
            r=self.call('speech',dict(requestId='speech-0001',replyRequestId='request-0001',version=self.version))
            self.assertEqual(r.status_code,200);speak.assert_called_once_with('我在这里。','owner-custom')

    def test_flag_and_asset_manifest(self):
        self.pair();m=self.call('manifest').json
        self.assertRegex(m['modelSha256'],r'^[a-f0-9]{64}$');self.assertFalse(m['toolsEnabled']);self.assertFalse(m['multipetEnabled'])
        self.app.config['DESKTOP_AGENT_ENABLED']=False
        self.assertFalse(self.call('manifest').json['chatEnabled']);self.assertEqual(self.chat().json['code'],'AGENT_DISABLED')
        self.assertEqual(self.call('ping').status_code,200);self.assertEqual(self.call('return').status_code,200)

    def test_private_appearance_keeps_original_agent_identity_and_hash(self):
        import hashlib
        raw=self.private_pet('user:1','desktop-private');self.pair()
        self.assertEqual(self.call('manifest').json['modelSha256'],hashlib.sha256(raw).hexdigest())
        self.assertEqual(self.chat().status_code,200)
        with self.app.app_context():
            self.assertEqual([tuple(r) for r in get_db().execute('SELECT DISTINCT owner,pet_id FROM companion_messages')],[('user:1',3)])
