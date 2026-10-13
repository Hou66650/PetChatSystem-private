"""Voice archive and automatic preference policy; isolated SQLite and fake planner."""
import json
import unittest
from test_companion import CompanionTests

class VoiceTests(unittest.TestCase):
    setUp=CompanionTests.setUp
    tearDown=CompanionTests.tearDown
    add=CompanionTests.add
    facts=CompanionTests.facts
    send=CompanionTests.send

    def voice(self, **data):
        return self.a.post('/api/companion/voice-round',json={'message':'请坐下','assistantText':'好呀','petId':1,**data})

    def test_den_voice_executes_validated_plan_and_archives_spoken_reply(self):
        self.model.plan(actions=[{'type':'sit','quote':'坐下'}])
        r=self.voice(surface='den')
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json['actions'],['sit'])
        self.assertEqual(r.json['reply'],'好呀')
        self.assertEqual(self.a.get('/api/companion/history').json['messages'][-1]['content'],'好呀')
        self.assertIn('3D小窝',r.json['instructions'])

    def test_chat_voice_never_dispatches_scene_actions(self):
        self.model.plan(actions=[{'type':'sit','quote':'坐下'}])
        r=self.voice();self.assertEqual(r.json['actions'],[])

    def test_explicit_preference_automatically_changes_motion_and_voice_policy(self):
        text='我平时喜欢简短安静温柔的陪伴'
        self.model.plan(memories=[{'category':'style','value':'简短安静温柔的陪伴','quote':text}])
        r=self.voice(message=text,surface='den')
        b=r.json['profile']['pet']['behavior']
        self.assertEqual(b['mode'],'calm');self.assertEqual(b['verbosity'],'brief')
        self.assertLess(b['speedScale'],1);self.assertGreater(b['idleSeconds'][0],9)
        self.assertIn('温柔耐心',r.json['instructions'])
        self.assertEqual(self.a.get('/api/companion').json['pet']['behavior'],b)

    def test_hobbies_and_temporary_moods_do_not_define_activity(self):
        self.add(category='likes',value='安静的画室和活泼的音乐')
        self.add(category='memory',value='今天很累想安静')
        self.assertEqual(self.a.get('/api/companion').json['pet']['behavior']['mode'],'natural')

    def test_negated_or_conflicting_style_does_not_become_positive(self):
        for value in ['不喜欢活泼热闹','喜欢安静也喜欢热闹']:
            self.add(category='style',value=value)
            self.assertEqual(self.a.get('/api/companion').json['pet']['behavior']['mode'],'natural')

    def test_changed_preference_replaces_old_policy(self):
        self.add(category='style',value='安静简短')
        self.model.plan(memories=[{'category':'style','value':'活泼幽默多互动','quote':'以后活泼幽默多互动'}])
        r=self.voice(message='以后活泼幽默多互动')
        b=r.json['profile']['pet']['behavior']
        self.assertEqual(b['mode'],'lively');self.assertEqual(b['reaction'],'happy')
        self.assertNotIn('安静简短',r.json['instructions'])

    def test_pause_and_forget_restore_default_motion(self):
        self.add(category='style',value='活泼多互动')
        self.a.patch('/api/companion',json={'enabled':False})
        self.assertEqual(self.a.get('/api/companion').json['pet']['behavior']['mode'],'natural')
        self.a.patch('/api/companion',json={'enabled':True})
        self.assertEqual(self.a.get('/api/companion').json['pet']['behavior']['mode'],'lively')
        fact=self.facts()[0]['id'];self.a.delete('/api/companion/memories/'+str(fact),json={})
        self.assertEqual(self.a.get('/api/companion').json['pet']['behavior']['mode'],'natural')

    def test_stale_voice_queued_before_forget_is_rejected(self):
        revision=self.a.get('/api/companion').json['revision']
        self.a.delete('/api/companion',json={})
        self.assertEqual(self.voice(profileRevision=revision).status_code,409)
        self.assertEqual(self.a.get('/api/companion/history').json['messages'],[])

    def test_voice_retry_does_not_replay_actions(self):
        self.model.plan(actions=[{'type':'sit','quote':'坐下'}])
        self.voice(surface='den',requestId='voice-round-1')
        r=self.voice(surface='den',requestId='voice-round-1')
        self.assertEqual(r.json['actions'],[])
        self.assertEqual(len(self.a.get('/api/companion/history').json['messages']),2)

    def test_queued_voice_cannot_cross_account_switch_even_with_same_revision(self):
        scope=self.b.get('/api/companion').json['scope']
        self.assertEqual(self.voice(profileScope=scope).status_code,409)
        self.assertEqual(self.a.get('/api/companion/history').json['messages'],[])

    def test_profile_policy_is_scoped_to_account(self):
        self.add(category='style',value='活泼热情')
        self.assertEqual(self.b.get('/api/companion').json['pet']['behavior']['mode'],'natural')

if __name__=='__main__':unittest.main(verbosity=2)
