"""Capability and original-quote boundaries for the expressive pets."""
import json,sys,unittest
from unittest.mock import patch
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.services.companion_service import decode_plan,SHIBA_ACTIONS,planner_prompt

class ShibaActions(unittest.TestCase):
    def test_each_new_action_requires_expressive_pet_den_and_current_quote(self):
        message='请你歪头再邀请我玩'
        for action in SHIBA_ACTIONS:
            raw=json.dumps({'reply':'好呀','actions':[{'type':action,'quote':message}]})
            for pet in (1,2,3):self.assertEqual(decode_plan(raw,message,'den',pet)['actions'],[action])
            for pet in (4,None):self.assertEqual(decode_plan(raw,message,'den',pet)['actions'],[])
            self.assertEqual(decode_plan(raw,message,'chat',1)['actions'],[])
            self.assertEqual(decode_plan(raw,'另一轮消息','den',1)['actions'],[])
    def test_eight_step_plan_preserves_order_repeats_and_capability_checks(self):
        actions=['come','sit','ears','wave','wave','greet','yawn','lie_down']
        message='能不能过来坐会儿竖耳挥爪两次摇尾打哈欠最后休息'
        raw=json.dumps({'reply':'好呀','actions':[{'type':a,'quote':message} for a in actions]})
        self.assertEqual(decode_plan(raw,message,'den',1)['actions'],actions)
        self.assertEqual(decode_plan(raw,message,'den',2)['actions'],actions)
        self.assertEqual(decode_plan(raw,message,'den',3)['actions'],actions)
        self.assertEqual(decode_plan(raw,message,'chat',1)['actions'],[])
        raw=json.dumps({'reply':'好呀','actions':[{'type':'wave','quote':message}]*12})
        self.assertEqual(decode_plan(raw,message,'den',1)['actions'],['wave']*8)
    def test_arbitrary_action_stays_rejected(self):
        raw=json.dumps({'reply':'好呀','actions':[{'type':'execute_js','quote':'你好'}]})
        for pet in (1,2,3):self.assertEqual(decode_plan(raw,'你好','den',pet)['actions'],[])
    def test_planner_advertises_only_available_pet_expressions(self):
        with patch('app.services.companion_service.context',return_value='当前宠物档案'):
            for pet in (1,2,3):self.assertIn('nose_lick(舔鼻)',planner_prompt('test',pet,'den'))
            for pet in (4,):self.assertNotIn('nose_lick(舔鼻)',planner_prompt('test',pet,'den'))
    def test_existing_actions_work_for_other_pets(self):
        raw=json.dumps({'reply':'好呀','actions':[{'type':'sit','quote':'坐下'}]})
        for pet in (1,2,3,4):self.assertEqual(decode_plan(raw,'坐下','den',pet)['actions'],['sit'])
if __name__=='__main__':unittest.main()
