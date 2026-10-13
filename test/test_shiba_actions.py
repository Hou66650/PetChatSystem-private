"""Capability and original-quote boundaries for the new Shiba-only actions."""
import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.services.companion_service import decode_plan,SHIBA_ACTIONS

class ShibaActions(unittest.TestCase):
    def test_each_new_action_requires_shiba_den_and_current_quote(self):
        message='请你歪头再邀请我玩'
        for action in SHIBA_ACTIONS:
            raw=json.dumps({'reply':'好呀','actions':[{'type':action,'quote':message}]})
            self.assertEqual(decode_plan(raw,message,'den',1)['actions'],[action])
            for pet in (2,3,4,None):self.assertEqual(decode_plan(raw,message,'den',pet)['actions'],[])
            self.assertEqual(decode_plan(raw,message,'chat',1)['actions'],[])
            self.assertEqual(decode_plan(raw,'另一轮消息','den',1)['actions'],[])
    def test_arbitrary_action_stays_rejected(self):
        raw=json.dumps({'reply':'好呀','actions':[{'type':'execute_js','quote':'你好'}]})
        self.assertEqual(decode_plan(raw,'你好','den',1)['actions'],[])
    def test_existing_actions_work_for_other_pets(self):
        raw=json.dumps({'reply':'好呀','actions':[{'type':'sit','quote':'坐下'}]})
        for pet in (1,2,3,4):self.assertEqual(decode_plan(raw,'坐下','den',pet)['actions'],['sit'])
if __name__=='__main__':unittest.main()
