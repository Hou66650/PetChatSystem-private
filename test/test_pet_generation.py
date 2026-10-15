"""Cloud boundary tests never submit paid jobs; live mode queries an existing ID."""
import hashlib
import io
import json
import os
from pathlib import Path
import time
import unittest
from unittest.mock import patch

from test_pet_studio import PetStudioTests
from app.db import get_db
from app.services import pet_generation_service as cloud, pet_adaptation_service as adaptation


class GenerationTests(unittest.TestCase):
    setUp = PetStudioTests.setUp
    tearDown = PetStudioTests.tearDown
    create_studio = PetStudioTests.create_studio
    photo = PetStudioTests.photo

    def post(self, key, operation, body=None):
        return self.a.post('/api/pet-studio/'+key+'/'+operation,json=body or {},headers=self.headers)

    def ready(self):
        key=self.create_studio(); self.photo(key)
        return key

    def row(self): return self.a.get('/api/pet-studio').json['tasks'][0]

    def test_explicit_consent_duplicate_and_locked_inputs(self):
        key=self.ready()
        with patch.object(cloud,'available',return_value=True),patch.object(cloud,'launch') as launch:
            self.assertEqual(self.post(key,'generate').status_code,409)
            self.assertEqual(self.post(key,'generate',{'consent':True}).status_code,200)
            self.assertEqual(self.post(key,'generate',{'consent':True}).status_code,409)
            self.assertEqual(launch.call_count,1)
            payload=launch.call_args.args[3]
            self.assertIn('ImageBase64',payload);self.assertNotIn('ImageUrl',payload)
            self.assertEqual(payload['Model'],'3.1')
            self.assertEqual(self.photo(key).status_code,409)
            scope=self.b.get('/api/pet-studio').json['scope']
            self.assertEqual(self.b.post('/api/pet-studio/'+key+'/generate',json={'consent':True},headers={'X-Profile-Scope':scope}).status_code,404)

    def test_submit_timeout_is_uncertain_not_retried(self):
        key=self.ready()
        with patch.object(cloud,'available',return_value=True),patch.object(cloud,'launch'):
            self.post(key,'generate',{'consent':True}); token=self.row()['generation']['id']
        with self.app.app_context(),patch.object(cloud,'_call',side_effect=TimeoutError) as call:
            cloud._worker(key,token,{'test':True})
            self.assertEqual(cloud.state(key)['status'],'uncertain')
            cloud.resume(key,explicit=True)
            self.assertEqual(call.call_count,1)
        self.assertEqual(self.post(key,'generate',{'consent':True}).status_code,409)

    def test_deleted_job_and_private_download(self):
        key=self.ready();raw=Path('static/models/petchat-cat-v3/cat.glb').read_bytes()
        with patch.object(cloud,'launch'),patch.object(cloud,'available',return_value=True):
            self.post(key,'generate',{'consent':True});token=self.row()['generation']['id']
        with self.app.app_context():digest=cloud.inputs(key)[1]
        self.post(key,'delete')
        with self.app.app_context():cloud._finish(key,token,digest,raw,50)
        self.assertEqual(self.a.get('/api/pet-studio/'+key+'/assets/model').status_code,404)
        self.assertEqual(self.b.get('/api/pet-studio/'+key+'/assets/model').status_code,404)

    def test_pause_resume_never_resubmits(self):
        key=self.ready()
        with self.app.app_context():
            digest=cloud.inputs(key)[1];db=get_db()
            db.execute('INSERT INTO pet_studio_generations VALUES (?,?,?,?,?,?,?,?,?)',(key,'token','known-job','paused',digest,None,'',time.time(),time.time()));db.commit()
        with patch.object(cloud,'launch') as launch:
            self.assertEqual(self.post(key,'resume-generation').status_code,200)
            launch.assert_called_once()
            self.assertEqual(len(launch.call_args.args),3)  # no submit payload

    def test_download_rejects_untrusted_hosts_before_network(self):
        for url in ['http://a.myqcloud.com/a','https://127.0.0.1/a','https://myqcloud.com.evil.test/a','https://x.tencentcos.cn:8080/a']:
            with self.assertRaises(ValueError):cloud._download(url)

    def test_equipment_requires_review_and_clears_on_change(self):
        key=self.ready();raw=Path('static/models/petchat-cat-v3/cat.glb').read_bytes()
        self.assertEqual(self.post(key,'equip',{'jobId':'j'}).status_code,409)
        with self.app.app_context():
            db=get_db();db.execute("UPDATE pet_studio_tasks SET status='approved' WHERE id=?",(key,))
            db.execute('INSERT INTO pet_studio_adaptations VALUES (?,?,?,?,?,?)',(key,'j',hashlib.sha256(raw).hexdigest(),'reviewed','{}',time.time()))
            db.execute('INSERT INTO pet_studio_assets VALUES (?,?,?,?)',(key,'adapted','model/gltf-binary',raw));db.commit()
        self.assertEqual(self.post(key,'equip',{'jobId':'old'}).status_code,409)
        self.assertEqual(self.post(key,'equip',{'jobId':'j'}).status_code,200)
        self.assertTrue(self.a.get('/api/cat-market').json['effectiveAppearance']['custom'])
        self.assertNotIn('custom',self.b.get('/api/cat-market').json['effectiveAppearance'])
        self.assertIn(('/api/pet-studio/'+key+'/assets/adapted').encode(),self.a.get('/den?pet=3').data)
        self.assertEqual(self.b.get('/api/pet-studio/'+key+'/assets/adapted').status_code,404)
        self.assertEqual(self.photo(key).status_code,200)
        self.assertNotIn('custom',self.a.get('/api/cat-market').json['effectiveAppearance'])

    @unittest.skipUnless(os.getenv('PET_STUDIO_QUERY_JOB'),'Requires an existing completed cloud job; never submits')
    def test_real_cloud_result_to_blender_to_private_island(self):
        key=self.create_studio();folder=Path('uploads/hunyuan-test-cat-20261015/paid-check-20261015')
        for view in ('front','left','back'):
            r=self.a.post('/api/pet-studio/'+key+'/assets/'+view,data={'file':(io.BytesIO((folder.parent/(view+'.png')).read_bytes()),view+'.png')},headers=self.headers)
            self.assertEqual(r.status_code,200)
        real_call=cloud._call;calls=[]
        def transport(action,payload):
            calls.append(action)
            if action=='submit':return 200,{'JobId':os.environ['PET_STUDIO_QUERY_JOB']}
            return real_call(action,payload)
        with patch.object(cloud,'_call',side_effect=transport):
            self.assertEqual(self.post(key,'generate',{'consent':True}).status_code,200)
            # Reopening the workspace and double-clicking must not create another job.
            self.assertEqual(self.post(key,'generate',{'consent':True}).status_code,409)
            row=self.wait_for(lambda r:r.get('generation',{}).get('status') not in cloud.ACTIVE)
        self.assertEqual(row['generation']['status'],'done',row['generation'])
        self.assertEqual(row['generation']['credits'],50)
        self.assertEqual(calls.count('submit'),1)
        self.assertEqual(self.post(key,'approve').status_code,200)
        self.assertEqual(self.post(key,'adapt',{'mode':'template-skin','forward':'-Y'}).status_code,200)
        row=self.wait_for(lambda r:r.get('adaptation',{}).get('status')!='running')
        self.assertEqual(row['adaptation']['status'],'review_motion',row['adaptation'])
        report=row['adaptation']['report'];self.assertEqual(report['unweightedVertices'],0)
        output=folder/'workflow-e2e';output.mkdir(exist_ok=True)
        for slot,filename in [('model','model.glb'),('adapted','adapted.glb'),('blend','review.blend')]:
            r=self.a.get('/api/pet-studio/'+key+'/assets/'+slot);self.assertEqual(r.status_code,200)
            (output/filename).write_bytes(r.data)
        # This checks the acceptance API, not an assertion that visual quality passes.
        job=row['adaptation']['id']
        self.assertEqual(self.post(key,'review-motion',{'jobId':job,'checks':adaptation.CHECKS}).status_code,200)
        self.assertEqual(self.post(key,'equip',{'jobId':job}).status_code,200)
        appearance=self.a.get('/api/cat-market').json['effectiveAppearance']
        self.assertEqual(appearance['task'],key)
        html=self.a.get('/den?pet=3').data.decode()
        self.assertIn(appearance['model'],html)
        (output/'den-fixture.html').write_text(html,encoding='utf-8')
        (output/'result.json').write_text(json.dumps({'cloudJob':os.environ['PET_STUDIO_QUERY_JOB'],'newPaidSubmissions':0,'cloudQueries':calls.count('query'),'modelBytes':(output/'model.glb').stat().st_size,'clips':report['clips'],'unweightedVertices':0,'privateEquipAPI':'passed','visualReview':'pending'},indent=2),encoding='utf-8')
        self.assertEqual(self.post(key,'unequip').status_code,200)
        self.assertNotIn('custom',self.a.get('/api/cat-market').json['effectiveAppearance'])

    def wait_for(self, predicate):
        deadline=time.monotonic()+300
        while time.monotonic()<deadline:
            row=self.row()
            if predicate(row):return row
            time.sleep(.5)
        self.fail('Background job timed out')
