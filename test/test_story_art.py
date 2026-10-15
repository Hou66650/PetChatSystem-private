import io,time,unittest
from PIL import Image
from test_companion import CompanionTests as Base
from app.services import story_art_service as art
class StoryArtTests(unittest.TestCase):
 setUp=Base.setUp
 tearDown=Base.tearDown
 def test_generation_scope_cache_and_errors(self):
  with art._lock:art._jobs.clear()
  calls=[]
  def generate(prompt):
   calls.append(prompt);out=io.BytesIO();Image.new('RGB',(40,50),'#cde5c9').save(out,format='PNG');return out.getvalue()
  self.model.generate_image=generate
  scope=self.a.get('/api/cat-agent').json['scope'];headers={'X-Profile-Scope':scope}
  self.assertEqual(self.a.post('/api/cat-agent/story-art',json={}).status_code,409)
  self.assertEqual(self.a.post('/api/cat-agent/story-art',json={},headers=headers).status_code,202)
  for _ in range(100):
   result=self.a.get('/api/cat-agent/story-art').json
   if result['status']!='pending':break
   time.sleep(.01)
  self.assertEqual(result['status'],'ready');self.assertTrue(result['image'].startswith('data:image/jpeg;base64,'))
  self.assertEqual(self.b.get('/api/cat-agent/story-art').json['status'],'idle')
  self.assertEqual(self.a.post('/api/cat-agent/story-art',json={},headers=headers).status_code,200)
  self.assertEqual(len(calls),1)
  self.assertEqual(self.a.post('/api/cat-agent/story-art',json={'refresh':True},headers=headers).status_code,429)
  with art._lock:
   for job in art._jobs.values():job['created']-=61
  self.model.generate_image=lambda p:b'not an image'
  self.a.post('/api/cat-agent/story-art',json={'refresh':True},headers=headers)
  for _ in range(100):
   result=self.a.get('/api/cat-agent/story-art').json
   if result['status']!='pending':break
   time.sleep(.01)
  self.assertEqual(result['status'],'error');self.assertNotIn('image',result)
if __name__=='__main__':unittest.main()
