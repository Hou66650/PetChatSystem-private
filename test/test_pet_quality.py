import hashlib
import json
import time
import unittest
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch
from test_pet_studio import PetStudioTests
from pet_quality_helpers import approve_quality
from app import pet_quality
from app.db import get_db
from app.services import pet_generation_service as generation, pet_adaptation_service as adaptation


class QualityTests(unittest.TestCase):
    setUp = PetStudioTests.setUp
    tearDown = PetStudioTests.tearDown
    create_studio = PetStudioTests.create_studio
    photo = PetStudioTests.photo

    def post(self, task, op, **data):
        return self.a.post('/api/pet-studio/'+task+'/'+op, json=data, headers=self.headers)

    def fixture(self):
        task = self.create_studio()
        with self.app.app_context():
            db = get_db(); raw = b'synthetic-model'
            db.execute("UPDATE pet_studio_tasks SET status='review' WHERE id=?", (task,))
            for slot in ('model','adapted'):
                db.execute('INSERT INTO pet_studio_assets VALUES (?,?,?,?)', (task,slot,'model/gltf-binary',raw))
            db.execute('INSERT INTO pet_studio_adaptations VALUES (?,?,?,?,?,?)',
                       (task,'job',hashlib.sha256(raw).hexdigest(),'review_motion','{}',time.time()))
            db.commit()
        return task

    def test_unknown_blocks_paid_generation_before_launch(self):
        task = self.create_studio(); self.photo(task)
        with patch.object(generation,'available',return_value=True), patch.object(generation,'launch') as launch:
            self.assertEqual(self.post(task,'generate',consent=True,provider='hyper3d').status_code,409)
            launch.assert_not_called()

    def test_checkboxes_and_legacy_review_cannot_bypass_gates(self):
        task = self.fixture()
        self.assertEqual(self.post(task,'approve').status_code,409)
        self.assertEqual(self.post(task,'review-motion',jobId='job',checks=adaptation.CHECKS).status_code,409)
        with self.app.app_context():
            db=get_db();db.execute("UPDATE pet_studio_adaptations SET status='reviewed' WHERE task=?",(task,))
            owner=db.execute('SELECT owner FROM pet_studio_tasks WHERE id=?',(task,)).fetchone()[0]
            db.execute('INSERT INTO pet_studio_equipped VALUES (?,?)',(owner,task));db.commit()
            self.assertIsNone(generation.appearance(owner))
        self.assertEqual(self.post(task,'equip',jobId='job').status_code,409)

    def test_reviewed_bundle_can_progress_and_revocation_stops_serving(self):
        task=self.fixture()
        with self.app.app_context(): approve_quality(task)
        self.assertEqual(self.post(task,'approve').status_code,200)
        self.assertEqual(self.post(task,'review-motion',jobId='job',checks=adaptation.CHECKS).status_code,200)
        self.assertEqual(self.post(task,'equip',jobId='job').status_code,200)
        with self.app.app_context():
            db=get_db()
            owner=db.execute('SELECT owner FROM pet_studio_tasks WHERE id=?',(task,)).fetchone()[0]
            self.assertIsNotNone(generation.appearance(owner))
            pet_quality.record(db,task,'geometry',pet_quality.fingerprints(db,task)['geometry'],'fail',
                               {'notes':'duplicate tail','files':[{'sha256':'evidence'}]});db.commit()
            self.assertIsNone(generation.appearance(owner))
            self.assertEqual(pet_quality.state(db,task)['motion']['status'],'unknown')

    def test_asset_and_rig_changes_invalidate_decisions(self):
        for change in ('photo','model','adapted','job','report'):
            with self.subTest(change=change):
                task=self.fixture()
                with self.app.app_context():
                    approve_quality(task);db=get_db()
                    if change=='photo': db.execute('INSERT INTO pet_studio_assets VALUES (?,?,?,?)',(task,'detail','image/jpeg',b'new'))
                    elif change in ('model','adapted'): db.execute('UPDATE pet_studio_assets SET data=? WHERE task=? AND slot=?',(b'new',task,change))
                    elif change=='job': db.execute("UPDATE pet_studio_adaptations SET id='new' WHERE task=?",(task,))
                    else: db.execute("UPDATE pet_studio_adaptations SET report=? WHERE task=?",(json.dumps({'new':True}),task))
                    db.commit()
                    with self.assertRaises(ValueError): pet_quality.require(db,task,'motion')

    def test_stale_bundle_and_out_of_order_review_rejected(self):
        task=self.fixture()
        with self.app.app_context():
            db=get_db();evidence={'notes':'checked','files':[{'sha256':'x'}]}
            with self.assertRaises(ValueError): pet_quality.record(db,task,'geometry','stale','pass',evidence)
            with self.assertRaises(ValueError): pet_quality.record(db,task,'motion',pet_quality.fingerprints(db,task)['motion'],'pass',evidence)

    def test_generation_diagnostics_remain_unknown_and_block_approval(self):
        task=self.create_studio();self.photo(task)
        with self.app.app_context():
            db=get_db();digest=generation.inputs(task)[1]
            db.execute('INSERT INTO pet_studio_generations (task,id,job,status,source_hash,credits,message,created,updated) VALUES (?,?,?,?,?,?,?,?,?)',
                       (task,'token','known','processing',digest,50,'',time.time(),time.time()));db.commit()
            generation._finish(task,'token',digest,b'synthetic-glb',50,
                               {'reason':'疑似重复尾巴','rearBranchCountsAssumingMinusY':[2,2,2]})
            current=pet_quality.state(db,task)
            self.assertEqual(current['geometry']['status'],'unknown')
            self.assertIn('重复尾巴',current['geometry']['reason'])
        self.assertEqual(self.post(task,'approve').status_code,409)

    def test_local_review_checks_exported_files_and_current_database(self):
        task=self.fixture();folder=Path(self.tmp.name)/'review'
        base=[sys.executable,'-X','utf8','scripts/pet_quality_review.py','--database',self.config.DATABASE_PATH]
        result=subprocess.run(base+['export','--task',task,'--output',str(folder)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        evidence=Path(self.tmp.name)/'evidence.txt';evidence.write_text('synthetic inspection')
        command=base+['review','--manifest',str(folder/'manifest.json'),'--stage','inputs','--result','pass',
                      '--notes','fixture only','--evidence',str(evidence)]
        result=subprocess.run(command,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        (folder/'model.glb').write_bytes(b'changed')
        result=subprocess.run(command,capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)


if __name__ == '__main__': unittest.main()
