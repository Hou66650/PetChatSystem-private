import io
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image
import test_companion as base
from app.db import get_db
from app.services import studio_memory_service as service


class StudioMemoryTests(unittest.TestCase):
    tearDown=base.CompanionTests.tearDown
    def setUp(self):
        base.CompanionTests.setUp(self)
        self.scope=self.a.get('/api/pet-studio').json['scope']
        self.headers={'X-Profile-Scope':self.scope}
        self.task=self.a.post('/api/pet-studio',json={'name':'测试伙伴','mode':'memory'},headers=self.headers).json['tasks'][0]['id']
        self.url='/api/pet-studio/'+self.task
        self.model.observe_pet_memory=Mock(return_value=json.dumps({'observations':[{'quote':'宠物在草地上坐着。','frame':1}]}))

    def photo(self,color='orange'):
        out=io.BytesIO();Image.new('RGB',(200,160),color).save(out,'PNG');return out.getvalue()

    def upload(self,raw=None,name='photo.png'):
        r=self.a.post(self.url+'/memories',data={'file':(io.BytesIO(raw or self.photo()),name)},headers=self.headers)
        self.assertEqual(r.status_code,200,r.json)
        return r.json['media'][0]['id']

    def state(self):return self.a.get(self.url+'/memories').json
    def analyze(self,media):return self.a.post(self.url+'/memories/'+media+'/analyze',json={'consent':True},headers=self.headers)
    def change(self,card,op='publish',**kw):
        return self.a.post(self.url+'/memory-cards/'+card['id']+'/'+op,json={
            'version':card['version'],'revision':self.state()['revision'],'kind':'comfort','value':'sit',
            'quote':card['quote'],'confirmed':True,**kw},headers=self.headers)

    def profile_records(self):
        with self.app.app_context():
            return [dict(r,evidence=json.loads(r['evidence'])) for r in get_db().execute('SELECT * FROM studio_pet_imprints WHERE task=?',(self.task,))]

    def equip_model(self, task):
        import hashlib
        from pet_quality_helpers import approve_quality
        with self.app.app_context():
            db=get_db()
            if not db.execute('SELECT 1 FROM pet_studio_adaptations WHERE task=?',(task,)).fetchone():
                # Synthetic immutable assets for the binding boundary, not a rendering test.
                db.execute('INSERT INTO pet_studio_assets VALUES (?,?,?,?)',(task,'model','model/gltf-binary',b'model'))
                db.execute('INSERT INTO pet_studio_assets VALUES (?,?,?,?)',(task,'adapted','model/gltf-binary',b'adapted'))
                db.execute('INSERT INTO pet_studio_adaptations VALUES (?,?,?,?,?,?)',(task,'job-'+task,hashlib.sha256(b'model').hexdigest(),'reviewed','{}',0))
                db.commit();approve_quality(task)
        r=self.a.post('/api/pet-studio/'+task+'/equip',json={'jobId':'job-'+task},headers=self.headers)
        self.assertEqual(r.status_code,200,r.json)

    def test_profile_binding_switch_pause_and_default_pet_isolation(self):
        first=self.task;media=self.upload();card=self.analyze(media).json['cards'][0]
        # An obsolete or forged pet selection cannot redirect a profile memory.
        self.assertEqual(self.change(card,pet=2).status_code,200)
        self.assertEqual(self.a.get('/api/pet-imprint/2').json['policy']['responses'],{})
        with self.app.app_context():
            db=get_db();proof=json.dumps({'type':'owner','quote':'标准猫原有习惯'})
            db.execute("INSERT INTO pet_imprints VALUES ('default-cat','user:1',3,'comfort','affection',?,1,0,0)",(proof,));db.commit()
        second=self.a.post('/api/pet-studio',json={'name':'另一只宠物','mode':'memory'},headers=self.headers).json['tasks'][0]['id']
        self.task=second;self.url='/api/pet-studio/'+second
        media=self.upload();card=self.analyze(media).json['cards'][0];self.change(card,value='lie_down')
        self.equip_model(first)
        self.assertEqual(self.a.get('/api/pet-imprint/3').json['policy']['responses']['comfort']['action'],'sit')
        self.assertIn('task='+first,self.a.get('/pet-imprint?petId=3').location)
        self.equip_model(second)
        self.assertEqual(self.a.get('/api/pet-imprint/3').json['policy']['responses']['comfort']['action'],'lie_down')
        self.assertIn('task='+second,self.a.get('/pet-imprint?petId=3').location)
        self.assertEqual(self.b.get('/api/pet-imprint/3').json['policy']['responses'],{})
        self.a.patch('/api/companion',json={'enabled':False})
        self.assertEqual(self.a.get('/api/pet-imprint/3').json['policy']['responses'],{})
        self.a.patch('/api/companion',json={'enabled':True})
        self.a.post(self.url+'/unequip',json={},headers=self.headers)
        self.assertEqual(self.a.get('/api/pet-imprint/3').json['policy']['responses']['comfort']['action'],'affection')
        self.equip_model(first)
        self.assertEqual(self.a.get('/api/pet-imprint/3').json['policy']['responses']['comfort']['action'],'sit')
        with self.app.app_context():
            db=get_db();db.execute("DELETE FROM pet_studio_quality WHERE task=? AND stage='motion'",(first,));db.commit()
        # A rejected model is not the runtime appearance, so it cannot carry memories.
        self.assertEqual(self.a.get('/api/pet-imprint/3').json['policy']['responses']['comfort']['action'],'affection')

    def test_migrate_existing_publications_keeps_confirmations_and_manual_records(self):
        media=self.upload();card=self.analyze(media).json['cards'][0]
        with self.app.app_context():
            db=get_db();proof=json.dumps({'type':'owner','quote':'以前已确认的依据'})
            db.execute("INSERT INTO pet_imprints VALUES ('old1','user:1',1,'comfort','sit',?,1,1,1)",(proof,))
            db.execute("INSERT INTO pet_imprints VALUES ('old2','user:1',2,'comfort','lie_down',?,1,2,2)",(proof,))
            db.execute("INSERT INTO pet_imprints VALUES ('manual','user:1',3,'comfort','affection',?,1,3,3)",(proof,))
            db.execute("UPDATE studio_memory_cards SET published='old1',pet=1 WHERE id=?",(card['id'],))
            db.execute("INSERT INTO studio_memory_cards(id,task,media,quote,start,end,published,pet,created) VALUES ('second',?,?,?,0,0,'old2',2,2)",(self.task,media,'以前已确认的依据'))
            db.commit();service.init_schema();service.init_schema()
            rows=db.execute('SELECT * FROM studio_pet_imprints ORDER BY id').fetchall()
            self.assertEqual(len(rows),2);self.assertEqual([r['confirmed'] for r in rows],[0,1])
            self.assertEqual([r['id'] for r in db.execute('SELECT * FROM pet_imprints')],['manual'])
        self.assertTrue(all(c['pet'] is None for c in self.state()['cards']))
        self.equip_model(self.task)
        self.assertEqual(self.a.get('/api/pet-imprint/3').json['policy']['responses']['comfort']['action'],'lie_down')

    def test_private_deduplicated_media_does_not_invalidate_model(self):
        with self.app.app_context():
            db=get_db();db.execute('INSERT INTO pet_studio_assets VALUES (?,?,?,?)',(self.task,'model','model/gltf-binary',b'model'));db.commit()
        media=self.upload();self.upload();self.assertEqual(len(self.state()['media']),1)
        self.model.observe_pet_memory.assert_not_called()
        self.assertEqual(self.b.get(self.url+'/memories').status_code,404)
        self.assertEqual(self.b.get(self.url+'/memories/'+media+'/source').status_code,404)
        r=self.a.get(self.url+'/memories/'+media+'/source');self.assertEqual(r.mimetype,'image/jpeg');self.assertIn('no-store',r.headers['Cache-Control'])
        self.assertIn('model',self.a.get('/api/pet-studio').json['tasks'][0]['assets'])
        self.assertEqual(self.a.post(self.url+'/memories',data={},headers={'X-Profile-Scope':'wrong'}).status_code,409)
        self.assertEqual(self.a.post(self.url+'/memories',data={},headers={**self.headers,'Origin':'https://evil.example'}).status_code,403)
        self.assertEqual(self.app.test_client().get(self.url+'/memories').status_code,403)

    def test_consent_drafts_confirmation_withdraw_and_stale_publish(self):
        media=self.upload()
        self.assertEqual(self.a.post(self.url+'/memories/'+media+'/analyze',json={},headers=self.headers).status_code,400)
        self.model.observe_pet_memory.assert_not_called()
        r=self.analyze(media);self.assertEqual(r.status_code,200,r.json);card=r.json['cards'][0]
        self.assertEqual(self.a.get('/api/pet-imprint/1').json['cards'],[])
        self.analyze(media);self.model.observe_pet_memory.assert_called_once()
        self.assertEqual(self.change(card,confirmed=False).status_code,400)
        r=self.change(card);self.assertEqual(r.status_code,200,r.json)
        self.assertTrue(r.json['cards'][0]['confirmed'])
        for pet in (1,2,3,4):self.assertEqual(self.a.get('/api/pet-imprint/'+str(pet)).json['policy']['responses'],{})
        self.equip_model(self.task)
        self.assertEqual(self.a.get('/api/pet-imprint/3').json['policy']['responses']['comfort']['action'],'sit')
        self.assertEqual(self.change(card).status_code,409)
        current=r.json['cards'][0];self.assertEqual(self.change(current,'withdraw').status_code,200)
        self.assertEqual(self.a.get('/api/pet-imprint/1').json['policy']['responses'],{})

    def test_failed_response_remains_retryable_never_fabricates_card(self):
        media=self.upload();self.model.observe_pet_memory.return_value='{"observations":[{"quote":"x","frame":99}]}'
        self.assertEqual(self.analyze(media).status_code,502)
        self.assertEqual(self.state()['cards'],[]);self.assertEqual(self.state()['media'][0]['status'],'failed')
        self.model.observe_pet_memory.assert_called_once()
        self.model.observe_pet_memory.return_value='{"observations":[]}'
        self.assertEqual(self.analyze(media).status_code,200);self.assertEqual(self.state()['cards'],[])

    def test_source_deletion_and_forget_remove_applied_memories(self):
        media=self.upload();card=self.analyze(media).json['cards'][0];self.change(card)
        self.a.post(self.url+'/memories/'+media+'/delete',json={},headers=self.headers)
        self.assertEqual(self.state()['media'],[]);self.assertEqual(self.state()['cards'],[])
        self.assertEqual(self.profile_records(),[])
        self.assertEqual(self.a.get('/api/pet-imprint/1').json['cards'],[])
        media=self.upload();self.analyze(media)
        self.a.delete('/api/companion',json={})
        self.assertEqual(self.state()['media'],[]);self.assertEqual(self.state()['cards'],[])
        self.assertEqual(self.profile_records(),[])

    def test_late_analysis_cannot_restore_deleted_material(self):
        media=self.upload()
        def delayed(*args):
            self.a.post(self.url+'/memories/'+media+'/delete',json={},headers=self.headers)
            return '{"observations":[{"quote":"观察","frame":1}]}'
        self.model.observe_pet_memory.side_effect=delayed
        self.assertEqual(self.analyze(media).status_code,404)
        self.assertEqual(self.state()['cards'],[])

    def test_running_claim_and_revision_race(self):
        media=self.upload()
        def delayed(*args):
            self.assertEqual(self.analyze(media).status_code,409)
            self.a.patch('/api/companion',json={'enabled':False})
            return '{"observations":[{"quote":"观察","frame":1}]}'
        self.model.observe_pet_memory.side_effect=delayed
        self.assertEqual(self.analyze(media).status_code,409)
        self.assertEqual(self.state()['cards'],[]);self.assertEqual(self.state()['media'][0]['status'],'failed')

    def test_real_video_extracts_private_timestamped_frames(self):
        import imageio_ffmpeg
        path=Path(self.tmp.name)/'clip.mp4'
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-nostdin','-loglevel','error','-f','lavfi','-i',
            'color=c=orange:s=160x120:r=12','-t','1','-c:v','libx264','-pix_fmt','yuv420p','-y',str(path)],check=True,
            timeout=15,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        media=self.upload(path.read_bytes(),'clip.mp4');item=self.state()['media'][0]
        self.assertEqual(len(item['times']),6);self.assertGreater(item['duration'],.3)
        self.model.observe_pet_memory.return_value='{"observations":[{"quote":"合成帧测试","frame":4}]}'
        card=self.analyze(media).json['cards'][0];self.assertEqual(card['start'],item['times'][3])
        self.assertEqual(self.change(card).status_code,200)
        self.assertEqual(self.profile_records()[0]['evidence']['type'],'media')
        source=self.a.get(self.url+'/memories/'+media+'/source',headers={'Range':'bytes=0-15'})
        self.assertEqual(source.status_code,206);self.assertEqual(len(source.data),16)

    def test_invalid_media_and_delete_profile(self):
        r=self.a.post(self.url+'/memories',data={'file':(io.BytesIO(b'#EXTM3U\nhttps://example.com'),'video.mp4')},headers=self.headers)
        self.assertEqual(r.status_code,400)
        media=self.upload();card=self.analyze(media).json['cards'][0];self.change(card)
        self.a.post(self.url+'/delete',json={},headers=self.headers)
        self.assertEqual(self.a.get(self.url+'/memories').status_code,404)
        self.assertEqual(self.a.get('/api/pet-imprint/1').json['cards'],[])
        self.assertIn('/pet-studio?section=memories',self.a.get('/pet-imprint?petId=2').location)
        self.assertEqual(self.a.get('/pet-imprint?embedded=1&petId=2').status_code,200)

    def test_authorized_case_copy_preserves_original_and_is_idempotent(self):
        from scripts.copy_pet_studio_cases import copy_cases
        with self.app.app_context():
            db=get_db()
            db.execute('INSERT INTO pet_studio_assets VALUES (?,?,?,?)',(self.task,'model','model/gltf-binary',b'unchanged-model'))
            db.commit()
            with db:
                db.execute('BEGIN IMMEDIATE');report=copy_cases(db,'user:1','user:2',[self.task])
            new=report[0]['copied'];self.assertNotEqual(new,self.task)
            with db:
                db.execute('BEGIN IMMEDIATE');again=copy_cases(db,'user:1','user:2',[self.task])
            self.assertTrue(again[0]['existing'])
            self.assertEqual(db.execute('SELECT count(*) FROM pet_studio_tasks').fetchone()[0],2)
            self.assertEqual(db.execute('SELECT data FROM pet_studio_assets WHERE task=?',(new,)).fetchone()[0],b'unchanged-model')
            self.assertEqual(db.execute('SELECT count(*) FROM pet_studio_equipped').fetchone()[0],0)
        self.assertEqual(self.b.get(self.url+'/assets/model').status_code,404)
        self.assertEqual(self.b.get('/api/pet-studio/'+new+'/assets/model').data,b'unchanged-model')

    def test_visual_transport_does_not_retry_unknown_outcome(self):
        import requests
        from app.llm.client import GLMClient, LLMError
        client=GLMClient('test-key','https://unused.invalid',['test'])
        client.session.post=Mock(side_effect=requests.Timeout('test timeout'))
        with self.assertRaises(LLMError):client.observe_pet_memory(b'picture','observe')
        client.session.post.assert_called_once()


if __name__=='__main__':unittest.main()
