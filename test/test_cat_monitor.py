import unittest
from test_companion import CompanionTests
class MonitorTests(unittest.TestCase):
    setUp=CompanionTests.setUp
    tearDown=CompanionTests.tearDown
    def send(self,client=None,**changes):
        c=client or self.a;scope=c.get('/api/cat-agent').json['scope']
        data={'stream':'stream-test-123','event':True,'snapshot':{'phase':'walking','text':'去桥头','reason':'访问较少','energy':.8,'x':0,'z':1,'pathLength':3,'candidates':['bridge'],'enabled':True,'private':'must not persist'}}
        data.update(changes)
        return c.post('/api/cat-agent/telemetry',json=data,headers={'X-Profile-Scope':scope})
    def test_page_and_isolation(self):
        self.assertEqual(self.a.get('/cat-agent-monitor').status_code,200)
        self.assertEqual(self.send().status_code,200)
        d=self.a.get('/api/cat-agent/monitor').json
        self.assertEqual(len(d['events']),1);self.assertNotIn('private',d['events'][0]['snapshot'])
        self.assertEqual(self.b.get('/api/cat-agent/monitor').json['events'],[])
        self.assertEqual(self.a.post('/api/cat-agent/telemetry',json={}).status_code,409)
    def test_paths_are_bounded_deduplicated_and_isolated(self):
        for batch in range(22):
            points=[[i/1000,0,i+1,0] for i in range(batch*30,batch*30+32)]
            self.assertEqual(self.send(snapshot={'trail':points,'route':[[0,1],[1,1]]}).status_code,200)
        d=self.a.get('/api/cat-agent/monitor').json
        trail=d['streams'][0]['snapshot']['trail']
        self.assertEqual(len(trail),600);self.assertEqual(len({p[2] for p in trail}),600)
        self.assertNotIn('trail',d['events'][0]['snapshot'])
        self.assertEqual(d['streams'][0]['snapshot']['route'],[[0,1],[1,1]])
        self.assertEqual(self.b.get('/api/cat-agent/monitor').json['streams'],[])
        for data in [{'trail':[[0,0,2],[0,0,1]]},{'route':[[0,0]]*65},{'trail':[[0,0,1,7]]},{'route':[[float('nan'),0]]}]:
            self.assertEqual(self.send(snapshot=data).status_code,400)
    def test_retention_heartbeat_and_validation(self):
        for i in range(125):self.send()
        self.send(event=False)
        d=self.a.get('/api/cat-agent/monitor').json
        self.assertEqual(len(d['events']),120);self.assertEqual(len(d['streams']),1)
        for i in range(10):self.send(stream='another-stream-'+str(i))
        self.assertEqual(len(self.a.get('/api/cat-agent/monitor').json['streams']),8)
        self.assertEqual(self.send(snapshot={'x':float('nan')}).status_code,400)
        self.assertEqual(self.send(snapshot={'candidates':['ocean']}).status_code,400)
        self.assertEqual(self.send(snapshot={'text':'x'*161}).status_code,400)
    def test_decision_evidence_is_bounded_and_account_isolated(self):
        import copy
        trace={'id':'decision-123','created':1000,'needs':{'energy':.8,'hunger':.3,'thirst':.4},
               'outcome':'completed','candidateCount':1,'excludedCount':0,'attention':['新花苞'],
               'ranked':[{'target':'bridge','name':'桥','score':1,'parts':{'novelty':1}}],
               'selection':{'target':'bridge','name':'桥','action':'observe','source':'local','trigger':'本地评分'},
               'memory':{'before':0,'after':1,'synced':True,'note':'服务器确认'},'private':'must not persist'}
        self.assertEqual(self.send(snapshot={'decision':trace}).status_code,200)
        saved=self.a.get('/api/cat-agent/monitor').json['streams'][0]['snapshot']['decision']
        self.assertNotIn('private',saved)
        self.assertEqual(saved['memory']['after'],1)
        self.assertEqual(self.b.get('/api/cat-agent/monitor').json['streams'],[])
        for key,value in [('attention',['x']*7),('ranked',trace['ranked']*9),('needs',{'thirst':float('nan')}),('selection',{'source':'script'}),('outcome','invented')]:
            bad=copy.deepcopy(trace);bad[key]=value
            self.assertEqual(self.send(snapshot={'decision':bad}).status_code,400)
if __name__=='__main__':unittest.main()
