import unittest
from test_companion import CompanionTests as Base
from app.llm.client import LLMError
class CatAgentTests(unittest.TestCase):
    setUp=Base.setUp
    tearDown=Base.tearDown
    def post(self,op,data,c=None):
        c=c or self.a
        scope=c.get('/api/cat-agent').json['scope']
        return c.post('/api/cat-agent/'+op,json=data,headers={'X-Profile-Scope':scope})
    def test_validation_and_scope(self):
        self.assertEqual(self.a.post('/api/cat-agent/decide',json={}).status_code,409)
        self.assertEqual(self.post('decide',{'candidates':['ocean']}).status_code,400)
        self.assertEqual(self.post('decide',{'candidates':['home'],'energy':True}).status_code,400)
    def test_model_cooldown_and_failure(self):
        calls=[]
        def plan(messages):calls.append(messages);return '{"target":"bridge","action":"observe"}'
        self.model.plan_once=plan
        data={'candidates':['bridge','home']}
        self.assertEqual(self.post('decide',data).json['source'],'model')
        self.assertEqual(self.post('decide',data).json['source'],'local');self.assertEqual(len(calls),1)
        self.app.extensions['cat_agent_gate']['next']=0
        self.model.plan_once=lambda m:'{"target":"ocean","action":"execute"}'
        self.assertEqual(self.post('decide',data).json['source'],'local')
        self.app.extensions['cat_agent_gate']['next']=0
        def fail(m):raise LLMError('rate limit')
        self.model.plan_once=fail
        self.assertEqual(self.post('decide',data).json['source'],'local')
    def test_eight_second_gate_and_adaptive_backoff(self):
        from unittest.mock import patch
        from app.llm.client import PlanningError
        calls=[]
        def ok(messages):calls.append(messages);return '{"target":"bridge","action":"observe"}'
        self.model.plan_once=ok;data={'candidates':['bridge']}
        with patch('app.services.cat_agent_service.time.time',return_value=1000) as clock:
            self.assertEqual(self.post('decide',data).json['source'],'model')
            clock.return_value=1007
            self.assertEqual(self.post('decide',data).json['source'],'local');self.assertEqual(len(calls),1)
            clock.return_value=1008
            self.assertEqual(self.post('decide',data).json['source'],'model');self.assertEqual(len(calls),2)
            def limited(m):raise PlanningError('limited',kind='rate_limit',retry_after=45)
            self.model.plan_once=limited;clock.return_value=1016
            result=self.post('decide',data).json
            self.assertEqual(result['retryAfter'],45);self.assertIn('限流',result['reason'])
            clock.return_value=1061;self.model.plan_once=ok
            self.assertEqual(self.post('decide',data).json['source'],'model')
            self.assertEqual(self.app.extensions['cat_agent_gate']['failures'],0)
    def test_greenhouse_model_action_and_catalog(self):
        self.model.plan_once=lambda messages: '{"target":"grass","action":"nibble"}'
        r=self.post('decide',{'candidates':['grass','catnip','hammock']})
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json['action'],'nibble')
        self.assertIn('猫草',r.json['intent'])
        catalog=self.a.get('/api/cat-agent').json['catalog']
        self.assertTrue({'grass','catnip','hammock'} <= {p['id'] for p in catalog})

    def test_failure_reason_distinguishes_timeout_from_invalid_plan(self):
        from app.llm.client import PlanningError
        def timeout(_):raise PlanningError('timeout',kind='timeout')
        self.model.plan_once=timeout
        r=self.post('decide',{'candidates':['bridge']})
        self.assertIn('响应超时',r.json['reason'])
        self.assertNotIn('结果无效',r.json['reason'])
        self.app.extensions['cat_agent_gate']['next']=0
        self.model.plan_once=lambda _: '{"target":"ocean","action":"observe"}'
        self.assertIn('不在允许',self.post('decide',{'candidates':['bridge']}).json['reason'])

    def test_compact_prompt_does_not_offer_reserved_care_actions(self):
        import json
        def plan(messages):
            payload=json.loads(messages[1]['content'])
            self.assertNotIn('memory',payload)
            for p in payload['candidates']:
                self.assertNotIn('x',p)
                self.assertNotIn('sleep',p['actions'])
                self.assertNotIn('eat',p['actions'])
            return '{"target":"food","action":"sniff"}'
        self.model.plan_once=plan
        self.assertEqual(self.post('decide',{'candidates':['food','home']}).json['source'],'model')

    def test_care_priority_and_validation(self):
        r=self.post('decide',{'candidates':['home','food','bridge'],'hunger':.9,'energy':.8})
        self.assertEqual(r.json['action'],'eat')
        r=self.post('decide',{'candidates':['home','food'],'hunger':.9,'energy':.1})
        self.assertEqual(r.json['action'],'sleep')
        self.assertEqual(self.post('decide',{'candidates':['food'],'hunger':2}).status_code,400)
    def test_memory_idempotence_and_isolation(self):
        data={'target':'bridge','result':'completed','event':'test-event-123'}
        self.assertEqual(self.post('report',data).status_code,200);self.post('report',data)
        self.assertEqual(self.a.get('/api/cat-agent').json['memory'][0]['visits'],1)
        self.assertEqual(self.b.get('/api/cat-agent').json['memory'],[])
        r=self.post('decide',{'candidates':['bridge','home'],'energy':.1})
        self.assertEqual(r.json['target'],'home');self.assertEqual(r.json['action'],'sleep')
class PlannerTransportTests(unittest.TestCase):
    def test_planning_transport_budget_and_typed_failures(self):
        import requests
        from unittest.mock import Mock
        from app.llm.client import GLMClient, PlanningError
        client=GLMClient('test-key','https://example.invalid',['test-model'])
        response=Mock(status_code=200)
        response.json.return_value={'choices':[{'finish_reason':'stop','message':{'content':'{"target":"bridge","action":"observe"}'}}]}
        client.session.post=Mock(return_value=response)
        self.assertIn('bridge',client.plan_once([]))
        self.assertEqual(client.session.post.call_args.kwargs['timeout'],(3,25))
        for code,kind in [(401,'auth'),(403,'auth'),(400,'request'),(503,'unavailable')]:
            response.status_code=code
            with self.assertRaises(PlanningError) as cm:client.plan_once([])
            self.assertEqual(cm.exception.kind,kind)
        response.status_code=200
        for choice,kind in [({'finish_reason':'length','message':{'content':'{'}},'truncated'),({'message':{'content':''}},'empty'),({},'format')]:
            response.json.return_value={'choices':[choice]}
            with self.assertRaises(PlanningError) as cm:client.plan_once([])
            self.assertEqual(cm.exception.kind,kind)
        for exception,kind in [(requests.ReadTimeout(),'timeout'),(requests.ConnectionError(),'network')]:
            client.session.post.side_effect=exception
            with self.assertRaises(PlanningError) as cm:client.plan_once([])
            self.assertEqual(cm.exception.kind,kind)
        self.assertTrue(client._sem.acquire(blocking=False));client._sem.release()

    def test_busy_and_rate_limit_do_not_queue_or_retry(self):
        from app.llm.client import GLMClient
        from unittest.mock import Mock
        client=GLMClient('test-key','https://example.invalid',['test-model'],max_concurrency=1)
        client.session.post=Mock(return_value=Mock(status_code=429))
        client._sem.acquire()
        with self.assertRaises(LLMError):client.plan_once([])
        client.session.post.assert_not_called();client._sem.release()
        with self.assertRaises(LLMError):client.plan_once([])
        self.assertEqual(client.session.post.call_count,1)
        self.assertTrue(client._sem.acquire(blocking=False));client._sem.release()
if __name__=='__main__':unittest.main()
