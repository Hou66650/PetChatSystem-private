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
if __name__=='__main__':unittest.main()
