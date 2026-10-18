"""Offline Rodin contract and durable-job migration tests. No paid API calls."""
import json
import os
import time
import unittest
from unittest.mock import patch, MagicMock

from test_pet_studio import PetStudioTests
from pet_quality_helpers import approve_quality
from app.db import get_db
from app.services import pet_generation_service as cloud, hyper3d_service as rodin


class Hyper3DTests(unittest.TestCase):
    setUp = PetStudioTests.setUp
    tearDown = PetStudioTests.tearDown
    create_studio = PetStudioTests.create_studio
    photo = PetStudioTests.photo

    def start(self):
        key=self.create_studio(); self.photo(key)
        with self.app.app_context(): approve_quality(key,'inputs')
        with patch.object(cloud,'available',return_value=True), patch.object(cloud,'launch') as launch:
            r=self.a.post('/api/pet-studio/'+key+'/generate',json={'consent':True,'provider':'hyper3d'},headers=self.headers)
            self.assertEqual(r.status_code,200)
            token=r.json['tasks'][0]['generation']['id']
            return key,token,launch.call_args.args[3]

    def test_ordered_multipart_auth_and_output_parameters(self):
        session=MagicMock(); session.post.return_value.json.return_value={}; session.post.return_value.status_code=201
        with patch.dict(os.environ,{'RODIN_API_KEY':'offline-test-key'}), patch.object(rodin.requests,'Session') as factory:
            factory.return_value.__enter__.return_value=session
            rodin.call('rodin',{'back':b'b','right':b'r','front':b'f','left':b'l'})
        args=session.post.call_args.kwargs
        self.assertEqual([f[1][0] for f in args['files']],['front.jpg','left.jpg','right.jpg','back.jpg'])
        self.assertEqual(json.loads(args['data']['image_label']),['F','L','R','B'])
        self.assertEqual(args['headers']['Authorization'],'Bearer offline-test-key')
        self.assertEqual(args['data']['tier'],'Gen-2.5-High')
        self.assertEqual(args['data']['quality_override'],'100000')
        self.assertEqual(args['data']['material'],'PBR')
        self.assertFalse(args['allow_redirects']); self.assertFalse(session.trust_env)

    def test_complete_workflow_uses_two_distinct_ids_and_fractional_credit(self):
        key,token,payload=self.start()
        responses=[(201,{'uuid':'task-id','jobs':{'subscription_key':'poll-key'},'consumed':.5}),
                   (201,{'jobs':[{'status':'Done'},{'status':'Generating'}]}),
                   (201,{'jobs':[{'status':'Done'},{'status':'Done'}]}),
                   (201,{'list':[{'name':'preview.png','url':'not-used'},{'name':'model.glb','url':'https://storage.example/model'}]})]
        with self.app.app_context(),patch.object(rodin,'call',side_effect=responses) as call,patch.object(cloud.time,'sleep') as sleep,patch.object(rodin,'download',return_value=b'glb'),patch.object(cloud,'_prepare',return_value=(b'prepared',{})),patch.object(cloud,'_finish') as finish:
            cloud._worker(key,token,payload)
            self.assertEqual([c.args[0] for c in call.call_args_list],['rodin','status','status','download'])
            self.assertEqual(call.call_args_list[1].args[1],{'subscription_key':'poll-key'})
            self.assertEqual(call.call_args_list[-1].args[1],{'task_uuid':'task-id'})
            self.assertEqual(finish.call_args.args[4],.5)
            self.assertEqual(cloud.state(key)['credits'],.5)
            self.assertNotIn('poll-key',json.dumps(cloud.state(key)))
            self.assertEqual(sleep.call_args_list[0].args,(5,))

    def test_timeout_and_partial_receipt_never_resubmit(self):
        for value in [TimeoutError(),(201,{'uuid':'only-uuid'}),(503,{'error':'busy'}),(201,{'uuid':'id','error':'bad','jobs':{'subscription_key':'key'}})]:
            key,token,payload=self.start()
            with self.app.app_context(),patch.object(rodin,'call',side_effect=[value]) as call:
                cloud._worker(key,token,payload)
                self.assertEqual(cloud.state(key)['status'],'uncertain')
                cloud.resume(key,explicit=True);self.assertEqual(call.call_count,1)
            # Remove isolated fixture so the next example isn't account-locked.
            self.a.post('/api/pet-studio/'+key+'/delete',json={},headers=self.headers)

    def test_known_rejection_and_failed_subjob_do_not_download(self):
        key,token,payload=self.start()
        with self.app.app_context(),patch.object(rodin,'call',return_value=(401,{'error':'INVALID_TOKEN'})):
            cloud._worker(key,token,payload);self.assertEqual(cloud.state(key)['status'],'failed')
        with self.app.app_context(),patch.object(cloud.time,'sleep'),patch.object(rodin,'call',side_effect=[
            (201,{'uuid':'id','jobs':{'subscription_key':'key'}}),
            (201,{'jobs':[{'status':'Done'},{'status':'Failed'}]})]) as call,patch.object(rodin,'download') as download:
            cloud._worker(key,token,payload);self.assertEqual(cloud.state(key)['status'],'failed')
            download.assert_not_called();self.assertEqual(call.call_count,2)

    def test_query_throttle_pauses_then_resumes_without_submit(self):
        key,token,payload=self.start()
        with self.app.app_context(),patch.object(cloud.time,'sleep'),patch.object(rodin,'call',side_effect=[
            (201,{'uuid':'id','jobs':{'subscription_key':'key'},'consumed':.5}),
            (429,{'error':'RATE_LIMITED'})]):
            cloud._worker(key,token,payload);self.assertEqual(cloud.state(key)['status'],'paused')
        with self.app.app_context(),patch.object(cloud.time,'sleep'),patch.object(rodin,'call',return_value=(201,{'jobs':[]})) as call:
            cloud._worker(key,token)
            self.assertEqual(call.call_args.args[0],'status');self.assertEqual(call.call_count,1)
            self.assertEqual(cloud.state(key)['status'],'paused')

    def test_legacy_migration_and_query_use_hunyuan(self):
        key=self.create_studio()
        with self.app.app_context():
            db=get_db()
            db.execute('DROP TABLE pet_studio_generations')
            db.execute('CREATE TABLE pet_studio_generations(task TEXT PRIMARY KEY,id TEXT,job TEXT,status TEXT,source_hash TEXT,credits INTEGER,message TEXT,created REAL,updated REAL)')
            db.execute('INSERT INTO pet_studio_generations VALUES (?,?,?,?,?,?,?,?,?)',(key,'old','tencent-job','paused','hash',40,'',time.time(),time.time()))
            db.commit();cloud.init_schema();cloud.init_schema()
            self.assertEqual(cloud.state(key)['provider'],'hunyuan')
            with patch.object(cloud,'_call',return_value=(200,{'Status':'FAIL'})) as old,patch.object(rodin,'call') as new:
                cloud._worker(key,'old');old.assert_called_once_with('query',{'JobId':'tencent-job'});new.assert_not_called()

    def test_no_hunyuan_fallback_when_rodin_missing(self):
        with patch.dict(os.environ,{'RODIN_API_KEY':'','HUNYUAN_3D_API_KEY':'legacy-key'}):
            self.assertFalse(cloud.available())

    def test_stale_page_consent_cannot_send_to_new_provider(self):
        key=self.create_studio()
        with patch.object(cloud,'start') as start:
            r=self.a.post('/api/pet-studio/'+key+'/generate',json={'consent':True},headers=self.headers)
            self.assertEqual(r.status_code,409);start.assert_not_called()

    def test_deleted_receipt_does_not_start_network(self):
        key,token,payload=self.start()
        self.a.post('/api/pet-studio/'+key+'/delete',json={},headers=self.headers)
        with self.app.app_context(),patch.object(rodin,'call') as call:
            cloud._worker(key,token,payload);call.assert_not_called()

    def test_private_and_redirect_downloads_are_rejected(self):
        for url in ['http://example.com/model','https://user:pass@example.com/model','https://example.com:8080/model']:
            with self.assertRaises(ValueError):rodin.download(url)
        with patch.object(rodin.socket,'getaddrinfo',return_value=[(2,1,6,'',('127.0.0.1',443))]),patch.object(rodin.requests,'Session') as session:
            with self.assertRaises(ValueError):rodin.download('https://example.com/model')
            session.assert_not_called()
        session=MagicMock();session.get.return_value.__enter__.return_value.status_code=302
        with patch.object(rodin.socket,'getaddrinfo',return_value=[(2,1,6,'',('8.8.8.8',443))]),patch.object(rodin.requests,'Session') as factory:
            factory.return_value.__enter__.return_value=session
            with self.assertRaises(ValueError):rodin.download('https://example.com/model')
            self.assertNotIn('headers',session.get.call_args.kwargs)
