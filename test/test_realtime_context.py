import unittest
from unittest.mock import patch
from flask import session
from test_companion import CompanionTests
from app.services import realtime_service, realtime_context, cat_scene_service


class VoiceContextTests(unittest.TestCase):
    setUp=CompanionTests.setUp
    tearDown=CompanionTests.tearDown

    def test_large_garden_and_memory_are_bounded_without_navigation_data(self):
        world={'scene':'雾林温室、云畔种植园与云上原野','beds':[{'name':'种植床'+str(i),'plant':{'name':'波斯菊','stageName':'盛开','ready':True,'wateredToday':True}} for i in range(10)],
               'decorations':[{'plant':'玫瑰','x':i,'z':i,'approaches':[{'x':i,'z':i}]*8} for i in range(100)],'recentChanges':[{'summary':'主人浇了水'}], 'places':[{'id':'plant:test','approaches':list(range(500))}]*100}
        facts=[dict(category='likes',value='花园里的花'*60,updated_at='2026-10-16') for _ in range(80)]
        facts.append(dict(category='pet_name',value='测试昵称',updated_at='2026-10-16'))
        with self.app.test_request_context('/'):
            session['user_id']='alice';session['auth_kind']='user'
            with patch.object(cat_scene_service,'snapshot',return_value=world),patch('app.services.companion_service.memories',return_value=facts):
                text=realtime_service.build_instructions(3,surface='den')
                self.assertLessEqual(len(text.encode()),realtime_context.MAX_INSTRUCTION_BYTES)
                for wanted in ('测试昵称','波斯菊','3D小窝','主人操作'):self.assertIn(wanted,text)
                for excluded in ('approaches','plant:test','source_quote'):self.assertNotIn(excluded,text)
                self.assertEqual(len(world['decorations']),100)
                private=realtime_service.build_instructions(3,private_context=False)
                self.assertNotIn('测试昵称',private);self.assertNotIn('波斯菊',private)

    def test_all_roles_fit_and_paused_memory_is_not_leaked(self):
        with self.app.test_request_context('/'):
            with patch('app.services.companion_service.settings',return_value={'enabled':False}):
                for pet in (1,2,3,4):
                    text=realtime_service.build_instructions(pet)
                    self.assertLessEqual(len(text.encode()),realtime_context.MAX_INSTRUCTION_BYTES)
                    self.assertIn('暂停长期记忆',text)

    def test_utf8_budget_preserves_whole_characters(self):
        text=realtime_context.clip('🌷测试'*300,77)
        self.assertLessEqual(len(text.encode()),77)
        self.assertNotIn('\ufffd',text)
