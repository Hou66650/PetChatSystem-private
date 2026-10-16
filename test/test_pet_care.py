import io
import math
import struct
import unittest
import wave
from datetime import datetime
from unittest.mock import patch
import test_companion as base
from app.db import get_db
from app.services import pet_care_service as care, pet_call_service as calls


class PetCareTests(unittest.TestCase):
    tearDown=base.CompanionTests.tearDown

    def setUp(self):
        base.CompanionTests.setUp(self)
        self.scope=self.a.get('/api/pet-care?petId=3').json['scope']
        self.h={'X-Profile-Scope':self.scope}
        self.now=datetime(2026,10,16,10,tzinfo=care.TZ).timestamp()

    def send(self,message):
        return self.a.post('/get_gpt_response',json={'petId':3,'surface':'den','message':message})

    def create(self,client=None,pet=3,**overrides):
        client=client or self.a
        h={'X-Profile-Scope':client.get('/api/pet-care?petId='+str(pet)).json['scope']}
        data=dict(title='面试',event_at=self.now+7200,remind_at=self.now-1,**overrides)
        return client.post('/api/pet-care/events?petId='+str(pet),json=data,headers=h)

    def test_plan_needs_confirmation_and_duplicate_turn_does_not_duplicate(self):
        with patch.object(care,'clock',return_value=self.now):
            response=self.send('我明天下午三点面试');self.assertEqual(response.status_code,200)
            e=response.json['care']['event'];self.assertEqual(e['state'],'draft')
            self.assertEqual(datetime.fromtimestamp(e['event_at'],care.TZ).isoformat(),'2026-10-17T15:00:00+08:00')
            self.assertIsNone(self.a.post('/api/pet-care/claim?petId=3',json={},headers=self.h).json['notice'])
            self.assertEqual(self.a.patch('/api/pet-care/events/'+e['id']+'?petId=3',json={'event_at':e['event_at'],'remind_at':self.now},headers=self.h).status_code,200)
            first=self.a.post('/api/pet-care/claim?petId=3',json={},headers=self.h).json['notice'];self.assertEqual(first['title'],'面试')
            self.assertIsNone(self.a.post('/api/pet-care/claim?petId=3',json={},headers=self.h).json['notice'])

    def test_update_cancels_old_schedule_then_cancel_and_forget(self):
        with patch.object(care,'clock',return_value=self.now):
            e=self.send('我明天下午三点面试').json['care']['event']
            self.a.patch('/api/pet-care/events/'+e['id']+'?petId=3',json={'event_at':e['event_at'],'remind_at':self.now},headers=self.h)
            changed=self.send('我的面试改到下周一上午十点了').json['care']['event']
            self.assertEqual(datetime.fromtimestamp(changed['event_at'],care.TZ).day,19)
            self.assertIsNone(self.a.post('/api/pet-care/claim?petId=3',json={},headers=self.h).json['notice'])
            self.send('取消面试，不用提醒我')
            self.assertFalse(any(e['state'] in ('draft','scheduled') for e in self.a.get('/api/pet-care?petId=3').json['events']))
            self.send('我明天要考试');self.a.delete('/api/companion',json={})
            self.assertEqual(self.a.get('/api/pet-care?petId=3').json['events'],[])

    def test_same_plan_not_repeated_and_history_forget_removes_sourced_event(self):
        with patch.object(care,'clock',return_value=self.now):
            self.send('我明天下午三点面试')
            self.assertIsNone(self.send('我明天下午三点面试').json['care']['event'])
            self.create()
            self.a.delete('/api/companion/history?petId=3',json={})
            remaining=self.a.get('/api/pet-care?petId=3').json['events']
            self.assertEqual(len(remaining),1)
            self.assertEqual(remaining[0]['source'],'用户手动确认')

    def test_quiet_hours_expiry_daily_limit_and_account_isolation(self):
        with patch.object(care,'clock',return_value=self.now):
            self.assertEqual(self.create().status_code,200);self.assertEqual(self.create(pet=1).status_code,200)
            self.assertEqual(self.b.get('/api/pet-care?petId=3').json['events'],[])
            self.a.patch('/api/pet-care?petId=3',json={'quiet_start':9,'quiet_end':11},headers=self.h)
            self.assertIsNone(self.a.post('/api/pet-care/claim?petId=3',json={},headers=self.h).json['notice'])
            self.a.patch('/api/pet-care?petId=3',json={'quiet_start':0,'quiet_end':0},headers=self.h)
            self.assertIsNotNone(self.a.post('/api/pet-care/claim?petId=3',json={},headers=self.h).json['notice'])
            self.assertIsNone(self.a.post('/api/pet-care/claim?petId=1',json={},headers=self.h).json['notice'])
        with patch.object(care,'clock',return_value=self.now+3*86400):
            self.assertIsNone(self.a.post('/api/pet-care/claim?petId=1',json={},headers=self.h).json['notice'])

    def test_memory_pause_and_revision_guard(self):
        with patch.object(care,'clock',return_value=self.now):
            self.create();self.a.patch('/api/companion',json={'enabled':False})
            self.assertEqual(self.a.get('/api/pet-care?petId=3').json['events'],[])
            self.assertIsNone(self.a.post('/api/pet-care/claim?petId=3',json={},headers=self.h).json['notice'])
            self.assertIsNone(self.send('我明天有考试').json['care']['event'])
            self.a.patch('/api/companion',json={'enabled':True})
            self.model.hook=lambda:self.a.delete('/api/companion',json={})
            self.assertEqual(self.send('我明天有面试').status_code,409)
            self.assertEqual(self.a.get('/api/pet-care?petId=3').json['events'],[])

    def test_ambiguous_or_other_people_plans_not_scheduled(self):
        with patch.object(care,'clock',return_value=self.now):
            for text in ('假如我明天有面试','我朋友明天要考试','我明天没有面试','我可能明天有比赛','明天考试和面试','我明天25点面试'):
                self.assertIsNone(self.send(text).json['care']['event'],text)

    def test_emotion_local_and_off_switch(self):
        for text in ('我今天有点难过','我现在很累了','我好紧张','今天考试考砸了'):
            self.assertEqual(care.emotion_cue(text)['action'],'company',text)
        for text in ('我朋友今天很难过','电影让我很难过','如果我很难过','我不难过','我没有很累','你难过吗'):
            self.assertIsNone(care.emotion_cue(text),text)
        self.assertEqual(care.emotion_cue('让我静一静')['action'],'space')
        self.a.patch('/api/pet-care?petId=3',json={'emotion':False},headers=self.h)
        self.assertIsNone(self.send('我很难过').json['care']['emotion'])

    def test_guards_and_invalid_times(self):
        self.assertEqual(self.a.patch('/api/pet-care?petId=3',json={'emotion':False}).status_code,409)
        self.assertEqual(self.a.patch('/api/pet-care?petId=3',json={'emotion':False},headers={**self.h,'Origin':'https://evil.example'}).status_code,403)
        with patch.object(care,'clock',return_value=self.now):
            for at in (float('nan'),float('inf'),self.now-1):
                self.assertEqual(self.a.post('/api/pet-care/events?petId=3',json={'title':'面试','event_at':at,'remind_at':self.now},headers=self.h).status_code,400)


def audio_sample():
    pcm=b''.join(struct.pack('<h',int(3500*math.sin(i*.11)) if 2400<i<48000 else 0) for i in range(72000))
    return calls.wav_bytes(pcm)


class PetCallsTests(unittest.TestCase):
    tearDown=base.CompanionTests.tearDown

    def setUp(self):
        base.CompanionTests.setUp(self);self.h={'X-Profile-Scope':self.a.get('/api/pet-care?petId=3').json['scope']}

    def upload(self):
        return self.a.post('/api/pet-calls/source?petId=3',headers=self.h,data={'consent':'true','media':(io.BytesIO(audio_sample()),'cat.wav')})

    def test_real_ffmpeg_extract_clip_private_playback_and_delete(self):
        response=self.upload();self.assertEqual(response.status_code,200,response.json);source=response.json
        self.assertTrue(source['candidates']);self.assertAlmostEqual(source['duration'],3)
        self.assertEqual(self.b.get('/api/pet-calls/source/'+source['id']).status_code,400)
        data=dict(sourceId=source['id'],start=.2,end=1.7,kind='greeting',name='它的声音',confirmed=True)
        saved=self.a.post('/api/pet-calls?petId=3',json=data,headers=self.h);self.assertEqual(saved.status_code,200,saved.json)
        clip=saved.json['clips'][0];r=self.a.get('/api/pet-calls/'+clip['id']);self.assertTrue(r.data.startswith(b'RIFF'));self.assertIn('no-store',r.headers['Cache-Control'])
        with wave.open(io.BytesIO(r.data)) as w:self.assertAlmostEqual(w.getnframes()/w.getframerate(),1.5)
        self.assertEqual(self.b.get('/api/pet-calls/'+clip['id']).status_code,400)
        self.a.patch('/api/pet-calls?petId=3',headers=self.h,json={'enabled':True})
        natural=self.a.get('/api/pet-sound?petId=3&kind=meow');self.assertEqual(natural.headers.get('X-Pet-Original'),'true')
        self.assertEqual(natural.data,r.data)
        self.a.delete('/api/pet-calls/'+clip['id'],headers=self.h);self.assertEqual(self.a.get('/api/pet-calls?petId=3').json['clips'],[])

    def test_validation_and_other_pet_cannot_use_source(self):
        source=self.upload().json
        for changes in ({'confirmed':False},{'end':99},{'start':float('nan')},{'kind':'speech'}):
            data=dict(sourceId=source['id'],start=.2,end=1.5,kind='greeting',confirmed=True);data.update(changes)
            self.assertEqual(self.a.post('/api/pet-calls?petId=3',json=data,headers=self.h).status_code,400)
        self.assertEqual(self.a.post('/api/pet-calls?petId=1',json=dict(sourceId=source['id'],start=.2,end=1.5,kind='greeting',confirmed=True),headers=self.h).status_code,400)
        bad=self.a.post('/api/pet-calls/source?petId=3',headers=self.h,data={'consent':'true','media':(io.BytesIO(b'not an audio'),'bad.mp4')})
        self.assertEqual(bad.status_code,400)


if __name__=='__main__':unittest.main()
