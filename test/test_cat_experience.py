import unittest,io,base64,time
from PIL import Image
from test_companion import CompanionTests as Base
from app.services import story_art_service as art
class ExperienceTests(unittest.TestCase):
 setUp=Base.setUp
 tearDown=Base.tearDown
 def post(self,op,data,c=None):
  c=c or self.a;scope=c.get('/api/cat-agent').json['scope']
  return c.post('/api/cat-agent/'+op,json=data,headers={'X-Profile-Scope':scope})
 def test_album_persistence_isolation_and_delete(self):
  # Owner is resolved server-side: registered fixture Alice is user 1.
  out=io.BytesIO();Image.new('RGB',(30,30)).save(out,format='JPEG')
  with art._lock:art._jobs['user:1']={'id':'fixture-art','status':'ready','created':time.monotonic(),'card':{'day':'2026-10-15','story':'和你玩过一次','coat':'ginger'},'image':'data:image/jpeg;base64,'+base64.b64encode(out.getvalue()).decode()}
  self.assertEqual(self.post('album-save',{'id':'fixture-art'}).status_code,200)
  self.post('album-save',{'id':'fixture-art'})
  self.assertEqual(self.post('album-save',{'id':'wrong-preview'}).status_code,400)
  cards=self.a.get('/api/cat-agent/album').json['cards'];self.assertEqual(len(cards),1)
  self.assertEqual(self.b.get('/api/cat-agent/album').json['cards'],[])
  self.assertEqual(self.b.get('/api/cat-agent/album/2026-10-15/image').status_code,404)
  self.assertEqual(self.a.get('/api/cat-agent/album/2026-10-15/image').mimetype,'image/jpeg')
  self.post('album-delete',{'day':'2026-10-15'},self.b);self.assertEqual(len(self.a.get('/api/cat-agent/album').json['cards']),1)
  self.post('album-delete',{'day':'2026-10-15'});self.assertEqual(self.a.get('/api/cat-agent/album').json['cards'],[])
 def test_control_delivery_ack_and_isolation(self):
  stream='test-stream-0001';packet={'stream':stream,'snapshot':{'phase':'walking','x':0,'z':0,'enabled':True}}
  self.post('telemetry',packet)
  self.assertEqual(self.post('control',{'stream':stream,'action':'pause'},self.b).status_code,400)
  command=self.post('control',{'stream':stream,'action':'pause'}).json
  response=self.post('telemetry',packet).json;self.assertEqual(response['control']['id'],command['id'])
  packet['controlAck']={'id':command['id'],'result':'applied'}
  self.assertIsNone(self.post('telemetry',packet).json['control'])
  self.assertEqual(self.a.get('/api/cat-agent/monitor').json['controls'][0]['result'],'applied')
  self.assertEqual(self.b.get('/api/cat-agent/monitor').json['controls'],[])
  self.post('control',{'stream':stream,'action':'home'})
  from app.db import get_db
  with self.app.app_context():
   with get_db() as db:db.execute('UPDATE cat_controls SET created=0')
  self.assertIsNone(self.post('telemetry',packet).json['control'])
  self.assertEqual(self.a.get('/api/cat-agent/monitor').json['controls'][0]['result'],'expired')
  self.assertEqual(self.post('control',{'stream':stream,'action':'execute'}).status_code,400)
if __name__=='__main__':unittest.main()
