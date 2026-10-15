import io
import json
import struct
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from test_companion import CompanionTests


class PetStudioTests(unittest.TestCase):
    tearDown = CompanionTests.tearDown
    def setUp(self):
        CompanionTests.setUp(self)
        self.scope = self.a.get('/api/pet-studio').json['scope']
        self.headers = {'X-Profile-Scope': self.scope}

    def create_studio(self, mode='companion'):
        r = self.a.post('/api/pet-studio', json={'name':'测试猫', 'mode':mode}, headers=self.headers)
        self.assertEqual(r.status_code, 200)
        return r.json['tasks'][0]['id']

    def photo(self, task, client=None, headers=None):
        image = io.BytesIO()
        Image.new('RGB',(256,256),'orange').save(image,'PNG')
        image.seek(0)
        return (client or self.a).post('/api/pet-studio/'+task+'/assets/front',
            data={'file':(image,'cat.png')}, headers=headers or self.headers)

    def test_private_upload_delete_and_no_cloud(self):
        with patch('requests.post', side_effect=AssertionError('Must not call cloud')):
            key=self.create_studio('memory')
            self.assertEqual(self.photo(key).status_code,200)
            r=self.a.get('/api/pet-studio/'+key+'/assets/front')
            self.assertEqual(r.mimetype,'image/jpeg')
            self.assertIn('no-store',r.headers['Cache-Control'])
            self.assertEqual(self.b.get('/api/pet-studio/'+key+'/assets/front').status_code,404)
            self.assertEqual(self.b.get('/api/pet-studio').json['tasks'],[])
            r=self.a.post('/api/pet-studio/'+key+'/prepare',json={},headers=self.headers)
            self.assertEqual(r.json['tasks'][0]['status'],'awaiting_generation')
            self.a.post('/api/pet-studio/'+key+'/delete',json={},headers=self.headers)
            self.assertEqual(self.a.get('/api/pet-studio/'+key+'/assets/front').status_code,404)

    def test_auth_scope_origin_and_validation(self):
        self.assertEqual(self.app.test_client().get('/api/pet-studio').status_code,403)
        self.assertEqual(self.a.post('/api/pet-studio',json={}).status_code,409)
        headers={**self.headers,'Origin':'https://other.example'}
        self.assertEqual(self.a.post('/api/pet-studio',json={},headers=headers).status_code,403)
        key=self.create_studio()
        self.assertEqual(self.a.post('/api/pet-studio/'+key+'/prepare',json={},headers=self.headers).status_code,400)
        self.assertEqual(self.a.post('/api/pet-studio/'+key+'/approve',json={},headers=self.headers).status_code,409)
        self.assertEqual(self.a.post('/api/pet-studio/'+key+'/assets/front',data={'file':(io.BytesIO(b'bad'),'x.png')},headers=self.headers).status_code,400)

    def test_model_external_uri_rejected(self):
        key=self.create_studio()
        doc=json.dumps({'asset':{'version':'2.0'},'meshes':[{}],'images':[{'uri':'https://other.example/x.png'}]}).encode()
        doc+=b' '*((-len(doc))%4)
        raw=b'glTF'+struct.pack('<IIII',2,len(doc)+20,len(doc),0x4E4F534A)+doc
        r=self.a.post('/api/pet-studio/'+key+'/assets/model',data={'file':(io.BytesIO(raw),'x.glb')},headers=self.headers)
        self.assertEqual(r.status_code,400)

    def test_limit_and_template(self):
        for _ in range(5): self.create_studio()
        self.assertEqual(self.a.post('/api/pet-studio',json={'name':'six','mode':'companion'},headers=self.headers).status_code,409)
        r=self.a.get('/pet-studio');self.assertEqual(r.status_code,200)
        self.assertIn('视频抽帧'.encode(),Path('static/js/pet-studio.js').read_bytes())

    def test_real_glb_review_and_reference_change_invalidates(self):
        key=self.create_studio()
        raw=Path('static/models/petchat-cat-v3/cat.glb').read_bytes()
        r=self.a.post('/api/pet-studio/'+key+'/assets/model',data={'file':(io.BytesIO(raw),'cat.glb')},headers=self.headers)
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json['tasks'][0]['status'],'review')
        r=self.a.post('/api/pet-studio/'+key+'/approve',json={},headers=self.headers)
        self.assertEqual(r.json['tasks'][0]['status'],'approved')
        r=self.photo(key)
        self.assertNotIn('model',r.json['tasks'][0]['assets'])
        self.assertEqual(r.json['tasks'][0]['status'],'draft')
