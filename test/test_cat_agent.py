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
    def test_memory_idempotence_and_isolation(self):
        data={'target':'bridge','result':'completed','event':'test-event-123'}
        self.assertEqual(self.post('report',data).status_code,200);self.post('report',data)
        self.assertEqual(self.a.get('/api/cat-agent').json['memory'][0]['visits'],1)
        self.assertEqual(self.b.get('/api/cat-agent').json['memory'],[])
        r=self.post('decide',{'candidates':['bridge','home'],'energy':.1})
        self.assertEqual(r.json['target'],'home');self.assertEqual(r.json['action'],'rest')
class PlannerTransportTests(unittest.TestCase):
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
