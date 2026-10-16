import json, subprocess, unittest
from concurrent.futures import ThreadPoolExecutor
from test_companion import CompanionTests as Base
from test_farm import FarmTests
from app.db import get_db
from app.services import farm_service as farm, farm_placement_service as placement

class DirectGardenTests(unittest.TestCase):
    setUp=Base.setUp
    tearDown=Base.tearDown
    post=FarmTests.post
    planted=FarmTests.planted
    mature=FarmTests.mature

    def point(self,container='soil',species='cosmos',others=()):
        for x in range(-140,79,4):
            for z in range(-75,85,4):
                p=dict(x=x/10,z=z/10,yaw=.3,container=container,species=species)
                if not placement.validate(p,others):return p
        raise AssertionError('No valid location')

    def test_soil_transplant_survives_reload_and_separates_accounts(self):
        pid=self.planted();self.mature();p=self.point()
        d=self.post('arrange',dict(**p,bed='bed-1',plant=pid)).json
        self.assertIsNone(d['beds'][0]['plant']);self.assertEqual(d['inventory']['pot'],1)
        plant=d['arrangements'][0];self.assertEqual(plant['x'],p['x']);self.assertEqual(plant['container'],'soil')
        self.assertEqual(self.a.get('/api/farm').json['arrangements'],d['arrangements'])
        self.assertEqual(self.b.get('/api/farm').json['arrangements'],[])
        from app import create_app
        app=create_app(self.config);client=app.test_client()
        with client.session_transaction() as s:s['user_id']='alice';s['auth_kind']='user'
        self.assertEqual(client.get('/api/farm').json['arrangements'],d['arrangements'])
        self.assertIn('土栽',str(self.a.get('/api/cat-agent/scene').json['world']['decorations']))

    def test_pot_atomic_inventory_move_revision_and_recovery(self):
        pid=self.planted();self.mature();p=self.point('pot')
        body=dict(**p,bed='bed-1',plant=pid,token='stable-direct-placement')
        self.post('arrange',body);d=self.post('arrange',body).json
        self.assertEqual(d['inventory']['pot'],0);self.assertEqual(len(d['arrangements']),1)
        a=d['arrangements'][0];point=self.point('pot',others=d['arrangements'])
        moved=self.post('arrange',dict(**point,id=a['id'],revision=a['revision'])).json['arrangements'][0]
        self.assertEqual(moved['revision'],2)
        self.assertEqual(self.post('arrange',dict(**p,id=a['id'],revision=1)).status_code,409)
        self.assertEqual(self.post('recover-arrangement',dict(id=a['id'],revision=2),c=self.b).status_code,409)
        d=self.post('recover-arrangement',dict(id=a['id'],revision=2)).json
        self.assertEqual(d['inventory']['cosmos'],1);self.assertEqual(d['inventory']['pot'],1)
        self.assertEqual(d['arrangements'],[])

    def test_invalid_locations_and_failed_placement_never_consume(self):
        pid=self.planted();self.mature()
        for p in [dict(x=0,z=1.8),dict(x=100,z=0),dict(x=3,z=-3.4),dict(x=True,z=0),dict(x=float('inf'),z=0)]:
            r=self.post('arrange',dict(**p,yaw=0,container='soil',bed='bed-1',plant=pid));self.assertEqual(r.status_code,409)
        self.assertEqual(self.a.get('/api/farm').json['beds'][0]['plant']['id'],pid)
        # A transaction cannot remove a plant if a required flowerpot is unavailable.
        with self.app.app_context():
            with get_db() as db:db.execute("UPDATE farm_stock SET quantity=0 WHERE item='pot'")
        self.assertEqual(self.post('arrange',dict(**self.point('pot'),bed='bed-1',plant=pid)).status_code,409)
        self.assertEqual(self.a.get('/api/farm').json['beds'][0]['plant']['id'],pid)

    def test_fertilizer_daily_stock_and_stale_plant_protection(self):
        pid=self.planted();data=dict(bed='bed-1',plant=pid,token='once-fertilizer')
        d=self.post('fertilize',data).json;self.assertTrue(d['beds'][0]['plant']['fertilized']);self.assertEqual(d['inventory']['fertilizer'],2)
        self.assertEqual(self.post('fertilize',data).json['inventory']['fertilizer'],2)
        self.assertEqual(self.post('fertilize',dict(bed='bed-1',plant=pid)).status_code,409)
        self.assertEqual(self.post('fertilize',dict(bed='bed-1',plant='stale-id')).status_code,409)
        self.assertTrue(self.a.get('/api/cat-agent/scene').json['world']['beds'][0]['plant']['fertilizedToday'])

    def test_simultaneous_transplants_cannot_duplicate_one_plant(self):
        pid=self.planted();self.mature();point=self.point()
        with self.app.app_context():owner=get_db().execute('SELECT owner FROM farm_accounts').fetchone()[0]
        def operation(i):
            with self.app.app_context():
                try:return farm.operate(owner,'arrange',dict(**point,bed='bed-1',plant=pid,token='concurrent-'+str(i)))
                except farm.Error:return None
        with ThreadPoolExecutor(max_workers=2) as pool:result=list(pool.map(operation,range(2)))
        self.assertEqual(sum(r is not None for r in result),1)
        self.assertEqual(len(self.a.get('/api/farm').json['arrangements']),1)

    def test_browser_server_placement_parity(self):
        points=[dict(x=x/2,z=z/2,yaw=.2,species=s,container=c) for x in range(-28,17,2) for z in range(-16,19,2) for s,c in [('cosmos','soil'),('cosmos','pot'),('birch','soil')]]
        script="const fs=require('fs'),p=require('./static/js/den/farm-placement'),m=require('./static/data/farm-placement.json');console.log(JSON.stringify(JSON.parse(fs.readFileSync(0,'utf8')).map(q=>p.validate(m,q))));"
        js=json.loads(subprocess.check_output(['node','-e',script],input=json.dumps(points).encode()).decode())
        self.assertEqual(js,[placement.validate(p) for p in points]);self.assertTrue(any(not s for s in js))

    def test_existing_garden_schema_migrates_without_losing_plants(self):
        import sqlite3,tempfile,time
        from pathlib import Path
        from app import create_app
        from app.config import Config
        with tempfile.TemporaryDirectory() as folder:
            database=Path(folder)/'old.db'
            with sqlite3.connect(database) as db:
                db.execute("CREATE TABLE farm_plants(owner TEXT,bed TEXT,id TEXT,species TEXT,planted REAL,bonus REAL DEFAULT 0,water_day TEXT DEFAULT '',PRIMARY KEY(owner,bed))")
                db.execute("INSERT INTO farm_plants(owner,bed,id,species,planted) VALUES ('user:legacy','bed-1','kept-plant','cosmos',?)",(time.time(),))
                db.execute("CREATE TABLE farm_arrangements(owner TEXT,id TEXT,species TEXT,container TEXT,x REAL,z REAL,yaw REAL,revision INTEGER DEFAULT 1,created REAL,PRIMARY KEY(owner,id))")
                db.execute("INSERT INTO farm_arrangements VALUES ('user:legacy','kept-decor','cosmos','pot',0,4,0,1,1)")
            db.close()
            class Migrated(Config):DATABASE_PATH=str(database);TESTING=True
            restored=create_app(Migrated)
            with restored.app_context():
                row=get_db().execute('SELECT * FROM farm_plants').fetchone()
                self.assertEqual(row['id'],'kept-plant');self.assertEqual(row['fertilizer_day'],'')
                placed=farm.arrangements(get_db(),'user:legacy')[0]
                self.assertEqual(placed['id'],'kept-decor');self.assertTrue(placed['ready']);self.assertEqual(placed['stage'],10)

if __name__=='__main__':unittest.main()
