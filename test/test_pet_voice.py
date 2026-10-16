"""Voice lifecycle with isolated SQLite and a fake provider; no billed API calls."""
import io
import math
import struct
import time
import unittest
import uuid
import wave
from unittest.mock import patch, Mock
import test_companion as base
from app.db import get_db
from app.services import pet_voice_service as voice


def wav(seconds=4, silent=False):
    out = io.BytesIO()
    with wave.open(out,'wb') as stream:
        stream.setparams((1,2,24000,0,'NONE','not compressed'))
        stream.writeframes(b''.join(struct.pack('<h',0 if silent else int(2500*math.sin(i*.09))) for i in range(int(seconds*24000))))
    return out.getvalue()


class PetVoiceTests(unittest.TestCase):
    setUpBase=base.CompanionTests.setUp
    tearDown=base.CompanionTests.tearDown

    def setUp(self):
        self.setUpBase()
        self.app.config.update(GLM_API_KEY='test.'+'x'*32,GLM_REALTIME_ENABLED=True)
        self.headers={'X-Profile-Scope':self.a.get('/api/pet-voices?petId=1').json['scope']}
        self.audio=wav()

    def provider(self,method,path,**kwargs):
        if path=='/files':return Mock(json=lambda:{'id':'sample-'+uuid.uuid4().hex})
        if path=='/voice/clone':return Mock(json=lambda:{'voice':'clone-'+uuid.uuid4().hex,'file_id':'preview-'+uuid.uuid4().hex})
        if path=='/audio/speech':return Mock(content=self.audio)
        return Mock(json=lambda:{'ok':True})

    def upload(self, pet=1, **extra):
        data=dict(petId=str(pet),name='温柔的声音',consent='true',requestId=uuid.uuid4().hex,audio=(io.BytesIO(self.audio),'audio.wav'))
        data.update(extra)
        return self.a.post('/api/pet-voices',data=data,headers=self.headers)

    def wait(self, profile, pet=1):
        for _ in range(100):
            row=next(p for p in self.a.get('/api/pet-voices?petId='+str(pet)).json['profiles'] if p['id']==profile)
            if row['status']!='creating':return row
            time.sleep(.02)
        self.fail('voice worker did not finish')

    def apply(self,profile,pet=1):
        return self.a.patch('/api/pet-voices/selection',json={'petId':pet,'id':profile},headers=self.headers)

    def test_complete_lifecycle_isolated_by_account_and_pet(self):
        with patch.object(voice,'provider',side_effect=self.provider) as upstream:
            r=self.upload();self.assertEqual(r.status_code,202);profile=r.json['id']
            self.assertEqual(self.wait(profile)['status'],'ready')
            self.assertIsNone(self.a.get('/api/pet-voices?petId=1').json['activeId'])
            self.assertEqual(self.b.get('/api/pet-voices?petId=1').json['profiles'],[])
            preview=self.a.post('/api/pet-voices/'+profile+'/preview',headers=self.headers)
            self.assertEqual(preview.data,self.audio);self.assertIn('no-store',preview.headers['Cache-Control'])
            self.assertEqual(self.apply(profile,2).status_code,409)
            self.assertEqual(self.apply(profile).status_code,200)
            self.a.post('/api/tts',json={'petId':1,'text':'新的回复','voice':'FORGED'})
            used=upstream.call_args.kwargs['json']['voice'];self.assertTrue(used.startswith('clone-'))
            self.b.post('/api/tts',json={'petId':1,'text':'新回复'})
            self.assertEqual(upstream.call_args.kwargs['json']['voice'],'tongtong')
            self.a.post('/api/tts',json={'petId':2,'text':'新回复'})
            self.assertEqual(upstream.call_args.kwargs['json']['voice'],'jam')
            session=self.a.post('/api/realtime/session',json={'petId':1}).json
            self.assertEqual(session['customVoice']['id'],profile)
            self.assertEqual(session['config']['voice'],'tongtong')
            self.assertNotIn(used,str(session));self.assertNotIn(used,str(self.a.get('/api/pet-voices?petId=1').json))
            self.assertIsNone(self.b.post('/api/realtime/session',json={'petId':1}).json['customVoice'])
            self.assertEqual(self.apply(None).status_code,200)
            self.assertEqual(self.a.post('/api/tts',json={'petId':1,'text':'旧通话','voiceProfileId':profile},headers=self.headers).status_code,409)
            self.assertEqual(self.a.delete('/api/pet-voices/'+profile,headers=self.headers).status_code,200)
            self.assertEqual(self.a.get('/api/pet-voices?petId=1').json['profiles'],[])
            self.assertTrue(any(c.args[1]=='/voice/delete' for c in upstream.call_args_list))
            self.assertEqual(sum(c.args[0]=='DELETE' for c in upstream.call_args_list),2)

    def test_switch_two_voices_routes_new_tts_and_sessions(self):
        with patch.object(voice,'provider',side_effect=self.provider) as upstream:
            ids=[]
            for name in ['声音甲','声音乙']:
                profile=self.upload(name=name).json['id'];self.wait(profile);ids.append(profile)
            used=[]
            for profile in ids+[ids[0]]:
                self.assertEqual(self.apply(profile).json['activeId'],profile)
                self.assertEqual(self.a.post('/api/tts',json={'petId':1,'text':'完全相同的一句话'}).status_code,200)
                used.append(upstream.call_args.kwargs['json']['voice'])
                self.assertEqual(self.a.post('/api/realtime/session',json={'petId':1}).json['customVoice']['id'],profile)
            self.assertNotEqual(used[0],used[1]);self.assertEqual(used[0],used[2])

    def test_duplicate_submission_creates_once(self):
        request_id=uuid.uuid4().hex
        with patch.object(voice,'provider',side_effect=self.provider) as upstream:
            first=self.upload(requestId=request_id);self.wait(first.json['id'])
            second=self.upload(requestId=request_id)
            self.assertEqual(first.json['id'],second.json['id'])
            self.assertEqual(sum(c.args[1]=='/voice/clone' for c in upstream.call_args_list),1)
            payload=next(c.kwargs['json'] for c in upstream.call_args_list if c.args[1]=='/voice/clone')
            self.assertLessEqual(len(payload['voice_name']),30)
            self.assertEqual(payload['voice_name'],voice.voice_name(first.json['id']))

    def test_voice_name_preserves_uuid_within_provider_limit(self):
        for profile in ['0'*32,'f'*32,uuid.uuid4().hex]:
            name=voice.voice_name(profile)
            self.assertLessEqual(len(name),30)
            self.assertEqual(int(name.removeprefix('pait_'),36),int(profile,16))

    def test_provider_errors_distinguish_parameters_balance_and_unknown_result(self):
        for http,body,expected,status in [
            (400,{'code':'1214','message':'voice_name:The voice name length cannot exceed 30 characters.'},'30 个字符',502),
            (429,{'code':'1113','message':'private provider data'},'余额不足',502),
            (429,{'code':'1302','message':'private provider data'},'过于频繁',502),
            (500,{'code':'1200','message':'private provider data'},'稍后查看状态',504),
        ]:
            response=Mock(ok=False,status_code=http,json=lambda:{'error':body})
            with self.app.app_context(),patch.object(voice.requests,'Session') as session:
                session.return_value.__enter__.return_value.request.return_value=response
                with self.assertRaises(voice.VoiceError) as caught:voice.provider('POST','/voice/clone')
                self.assertIn(expected,str(caught.exception));self.assertEqual(caught.exception.status,status)
                self.assertNotIn('private provider data',str(caught.exception))

    def test_rejects_invalid_audio_consent_scope_and_cross_account_access(self):
        with patch.object(voice,'provider',side_effect=self.provider) as upstream:
            self.assertEqual(self.upload(consent='false').status_code,400)
            for audio in (b'not wav',wav(1),wav(4,True)):
                self.assertEqual(self.upload(audio=(io.BytesIO(audio),'bad.wav')).status_code,400)
            upstream.assert_not_called()
            first=self.upload();profile=first.json['id'];self.wait(profile)
            headers={'X-Profile-Scope':self.b.get('/api/pet-voices?petId=1').json['scope']}
            self.assertEqual(self.b.post('/api/pet-voices/'+profile+'/preview',headers=headers).status_code,404)
            self.assertEqual(self.b.delete('/api/pet-voices/'+profile,headers=headers).status_code,404)
            self.assertEqual(self.a.patch('/api/pet-voices/selection',json={'petId':1,'id':profile}).status_code,409)
            self.assertEqual(self.a.patch('/api/pet-voices/selection',json={'petId':1,'id':profile},headers={**self.headers,'Origin':'https://elsewhere.test'}).status_code,403)
            guest=self.app.test_client();self.assertEqual(guest.patch('/api/pet-voices/selection',json={'petId':1,'id':profile}).status_code,403)

    def test_provider_failure_does_not_replace_existing_voice(self):
        with patch.object(voice,'provider',side_effect=self.provider):
            first=self.upload().json['id'];self.wait(first);self.apply(first)
        with patch.object(voice,'provider',side_effect=voice.VoiceError('服务受限',502)):
            failed=self.upload().json['id'];self.assertEqual(self.wait(failed)['status'],'failed')
        self.assertEqual(self.a.get('/api/pet-voices?petId=1').json['activeId'],first)

    def test_interrupted_job_does_not_silently_retry(self):
        with patch.object(voice,'provider',side_effect=voice.VoiceError('连接超时',504)) as upstream:
            profile=self.upload().json['id'];self.assertEqual(self.wait(profile)['status'],'uncertain')
            self.assertEqual(self.apply(profile).status_code,409)
            self.assertEqual(self.a.delete('/api/pet-voices/'+profile,headers=self.headers).status_code,409)
            self.assertEqual(upstream.call_count,1)

    def test_reconcile_matches_only_exact_server_generated_name(self):
        with patch.object(voice,'provider',side_effect=voice.VoiceError('连接超时',504)):
            profile=self.upload().json['id'];self.wait(profile)
        with patch.object(voice,'provider',return_value=Mock(json=lambda:{'voice_list':[{'voice_name':'pait_other','voice':'foreign'}]})):
            self.assertEqual(self.a.post('/api/pet-voices/'+profile+'/reconcile',headers=self.headers).status_code,409)
        with patch.object(voice,'provider',return_value=Mock(json=lambda:{'voice_list':[{'voice_name':voice.voice_name(profile),'voice':'recovered'}]})) as upstream:
            self.assertEqual(self.a.post('/api/pet-voices/'+profile+'/reconcile',headers=self.headers).json['status'],'ready')
            self.assertEqual(upstream.call_args.args[0],'GET')

    def test_delete_failure_retains_retry_record_and_deactivates_voice(self):
        with patch.object(voice,'provider',side_effect=self.provider):
            profile=self.upload().json['id'];self.wait(profile);self.apply(profile)
        with patch.object(voice,'provider',side_effect=voice.VoiceError('暂时无法删除',502)):
            self.assertEqual(self.a.delete('/api/pet-voices/'+profile,headers=self.headers).status_code,502)
        state=self.a.get('/api/pet-voices?petId=1').json
        self.assertIsNone(state['activeId']);self.assertEqual(state['profiles'][0]['id'],profile)

    def test_same_account_new_browser_keeps_selection(self):
        with patch.object(voice,'provider',side_effect=self.provider):
            profile=self.upload().json['id'];self.wait(profile);self.apply(profile)
        other=self.app.test_client()
        with other.session_transaction() as s:s['user_id']='alice';s['auth_kind']='user'
        self.assertEqual(other.get('/api/pet-voices?petId=1').json['activeId'],profile)


if __name__=='__main__':unittest.main()
