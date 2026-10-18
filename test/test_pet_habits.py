import io
import json
import math
import array
import unittest
from unittest.mock import Mock, patch

from app.db import get_db
from app.services import pet_habit_service as habits, habit_media
import test_studio_memories as base


class HabitTests(unittest.TestCase):
    setUp=base.StudioMemoryTests.setUp
    tearDown=base.StudioMemoryTests.tearDown
    photo=base.StudioMemoryTests.photo
    upload=base.StudioMemoryTests.upload
    state=base.StudioMemoryTests.state
    equip_model=base.StudioMemoryTests.equip_model

    def analyze(self, media, **data):
        return self.a.post(self.url+'/habits/'+media+'/analyze',json=(dict(part=0,consent=True)|data),headers=self.headers)

    def observation(self):
        self.model.observe_pet_memory=Mock(return_value=json.dumps(dict(subject='single',events=[dict(first=1,last=1,action='sit',observation='坐在地面上')]),ensure_ascii=False))

    def review(self, e, **data):
        return self.a.post(self.url+'/habit-events/'+e['id']+'/review',json=dict(revision=e['revision'],confirmed=True,
            subjectConfirmed=True,kind=e['kind'],value=e['value'],captureGroup='同次拍摄',observation=e['observation'])|data,headers=self.headers)

    def apply(self, **data):
        state=self.state();c=state['habits']['candidates'][0]
        return self.a.post(self.url+'/habit-rules',json=dict(kind=c['kind'],value=c['value'],events=c['evidence'],
            revision=state['revision'],confirmed=True)|data,headers=self.headers)

    def test_explicit_consent_cached_jobs_and_boundaries(self):
        self.observation();media=self.upload()
        self.assertEqual(self.analyze(media,consent=False).status_code,400)
        self.assertEqual(self.analyze(media,part=True).status_code,400)
        result=self.analyze(media);self.assertEqual(result.status_code,200,result.json)
        self.assertEqual(len(result.json['habits']['events']),1)
        self.assertFalse(result.json['habits']['candidates'])
        self.analyze(media);self.model.observe_pet_memory.assert_called_once()
        self.assertEqual(self.b.post(self.url+'/habits/'+media+'/analyze',json={'part':0,'consent':True},headers={'X-Profile-Scope':self.b.get('/api/pet-studio').json['scope']}).status_code,404)

    def test_review_apply_switch_revoke_and_delete(self):
        self.observation();media=self.upload();event=self.analyze(media).json['habits']['events'][0]
        self.assertEqual(self.review(event,subjectConfirmed=False).status_code,400)
        self.assertEqual(self.review(event).status_code,200)
        self.assertEqual(self.review(event).status_code,409)
        self.assertEqual(self.apply().status_code,200)
        self.assertNotIn('rest',self.a.get('/api/pet-imprint/3').json['policy']['responses'])
        self.equip_model(self.task)
        policy=self.a.get('/api/pet-imprint/3').json['policy']
        self.assertEqual(policy['responses']['rest']['plan'],['sit'])
        self.assertNotIn('rest',self.b.get('/api/pet-imprint/3').json['policy']['responses'])
        self.a.patch('/api/companion',json={'enabled':False})
        self.assertNotIn('rest',self.a.get('/api/pet-imprint/3').json['policy']['responses'])
        self.a.patch('/api/companion',json={'enabled':True})
        event=self.state()['habits']['events'][0]
        self.assertEqual(self.review(event,confirmed=False).status_code,200)
        self.assertNotIn('rest',self.a.get('/api/pet-imprint/3').json['policy']['responses'])
        self.a.post(self.url+'/memories/'+media+'/delete',json={},headers=self.headers)
        self.assertFalse(self.state()['habits']['events'])

    def test_groups_conflicts_and_photo_limits(self):
        self.observation()
        for color in ('red','blue'):
            media=self.upload(self.photo(color));e=self.analyze(media).json['habits']['events'][-1]
            self.assertEqual(self.review(e).status_code,200)
        c=self.state()['habits']['candidates'][0]
        self.assertEqual(c['groups'],1);self.assertEqual(len(c['evidence']),2)
        e=self.state()['habits']['events'][0]
        self.assertEqual(self.review(e,kind='recall',value='observe_come').status_code,400)
        self.assertEqual(self.review(e,kind='recall',value='observe_come',ownerContext=True).status_code,200)

    def test_invalid_model_data_never_publishes_or_retries(self):
        media=self.upload();self.model.observe_pet_memory=Mock(return_value='{"subject":"single","events":[{"first":999}]}')
        self.assertEqual(self.analyze(media).status_code,502)
        self.assertFalse(self.state()['habits']['events']);self.model.observe_pet_memory.assert_called_once()
        self.assertEqual(self.state()['habits']['jobs'][0]['status'],'failed')
        raw=json.dumps(dict(subject='multiple',events=[dict(first=1,last=1,action='sit',observation='两只猫')]))
        self.assertEqual(habits.parse_observations(raw,[0],0,True),[])

    def test_late_result_after_delete_cannot_restore_events(self):
        media=self.upload();self.observation()
        def deleted(*args):
            self.a.post(self.url+'/memories/'+media+'/delete',json={},headers=self.headers)
            return '{"subject":"single","events":[]}'
        self.model.observe_pet_memory=Mock(side_effect=deleted)
        self.assertEqual(self.analyze(media).status_code,404)
        self.assertFalse(self.state()['habits']['events'])

    def test_audio_is_local_reviewable_and_revocable(self):
        samples=array.array('h',(int(5000*math.sin(2*math.pi*440*i/habit_media.RATE)) if habit_media.RATE//2<i<habit_media.RATE else 0 for i in range(habit_media.RATE*2)))
        media=self.upload(habit_media.wav(samples.tobytes()),'example.wav')
        self.model.observe_pet_memory=Mock(side_effect=AssertionError('No audio cloud call'))
        result=self.analyze(media);self.assertEqual(result.status_code,200,result.json)
        e=result.json['habits']['events'][0];self.assertEqual(e['provenance'],'audio_energy')
        self.assertEqual(self.review(e,kind='rest',value='sit').status_code,400)
        self.assertEqual(self.review(e).status_code,200);self.apply();self.equip_model(self.task)
        state=self.a.get('/api/pet-imprint/3').json
        self.assertTrue(state['originalCalls']['enabled'])
        response=self.a.get('/api/pet-imprint/3/call/greeting?revision='+str(state['revision']))
        self.assertEqual(response.status_code,200);self.assertEqual(response.data[:4],b'RIFF')
        e=self.state()['habits']['events'][0];self.review(e,confirmed=False)
        self.assertEqual(self.a.get('/api/pet-imprint/3/call/greeting?revision='+str(state['revision'])).status_code,409)
        self.model.observe_pet_memory.assert_not_called()

    def test_dense_window_real_decode_and_timestamp_validation(self):
        import tempfile,subprocess,imageio_ffmpeg
        from pathlib import Path
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'test.mp4'
            subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-v','error','-f','lavfi','-i','color=c=blue:s=320x240:r=12','-t','2','-y',str(path)],check=True)
            sheet,times=habit_media.window(path.read_bytes(),0,2)
            self.assertEqual(len(times),6);self.assertEqual(times[-1],1.667)
            self.assertTrue(sheet.startswith(b'\xff\xd8'))
            self.observation();media=self.upload(path.read_bytes(),'silent.mp4')
            result=self.analyze(media)
            self.assertEqual(result.status_code,200,result.json)
            self.assertTrue(result.json['habits']['events'])
        raw=json.dumps(dict(subject='single',events=[dict(first=1,last=3,action='approach_sit',observation='向前走后坐下')]))
        result=habits.parse_observations(raw,[8,8.333,8.667],9)
        self.assertEqual(result[0]['start'],8);self.assertLessEqual(result[0]['end'],9)

    def test_quota_cache_and_profile_switch(self):
        self.app.config['HABIT_VISION_DAILY_LIMIT']=1
        self.observation();media=self.upload();event=self.analyze(media).json['habits']['events'][0]
        self.analyze(media);self.assertEqual(self.model.observe_pet_memory.call_count,1)
        another=self.upload(self.photo('green'))
        self.assertEqual(self.analyze(another).status_code,429)
        self.assertEqual(self.model.observe_pet_memory.call_count,1)
        self.review(event);self.apply();first=self.task;self.equip_model(first)
        self.assertIn('rest',self.a.get('/api/pet-imprint/3').json['policy']['responses'])
        second=self.a.post('/api/pet-studio',json={'name':'不同伙伴','mode':'memory'},headers=self.headers).json['tasks'][0]['id']
        self.equip_model(second)
        self.assertNotIn('rest',self.a.get('/api/pet-imprint/3').json['policy']['responses'])


if __name__=='__main__': unittest.main()
