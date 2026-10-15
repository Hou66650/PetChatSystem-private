"""Real browser + real Flask/SQLite, temporary account only; never binds port 5002."""
import os, sys, tempfile, threading, subprocess
import logging
logging.getLogger('werkzeug').setLevel(logging.ERROR)
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from flask import render_template,session
from werkzeug.serving import make_server
from app import create_app
from app.config import Config
from app.db import get_db
from app.services import farm_service,companion_service

with tempfile.TemporaryDirectory() as folder:
    class Fixture(Config):
        TESTING=True
        DATABASE_PATH=str(Path(folder)/'garden.db')
        SECRET_KEY='isolated-garden-browser-fixture'
    app=create_app(Fixture)
    with app.app_context():
        db=get_db();db.executescript(Path(Config.SCHEMA_PATH).read_text())
        db.execute('INSERT INTO users(user_name,pwd) VALUES (?,?)',('garden-fixture','test-only'));db.commit()
    @app.get('/garden-test')
    def page():
        session['user_id']='garden-fixture';session['auth_kind']='user'
        scripts=''.join('<script src="/static/js/'+p+'"></script>' for p in ['vendor/three.min.js','vendor/GLTFLoader.js','vendor/OrbitControls.js','den/selected-assets.js','den/scene-navigation.js','den/mistwood-layout.js','den/toy-workshop.js'])
        html=render_template('_farm.html',farm_layout=farm_service.LAYOUT)
        bootstrap='''const scene=new THREE.Scene();scene.background=new THREE.Color(0xd8e5de);const camera=new THREE.PerspectiveCamera(40,innerWidth/innerHeight,.1,100);camera.position.set(-12,10,15);camera.lookAt(-9,.2,4);const canvas=document.getElementById('world'),renderer=new THREE.WebGLRenderer({canvas,antialias:true});renderer.setSize(innerWidth,innerHeight);renderer.outputEncoding=THREE.sRGBEncoding;scene.add(new THREE.HemisphereLight(0xfff8e8,0x47665a,1.3));const sun=new THREE.DirectionalLight(0xffefdf,1.3);sun.position.set(-3,12,7);scene.add(sun);const loader=new SelectedAssets.Loader(new THREE.GLTFLoader()),ticket=loader.begin(),layout=JSON.parse(document.getElementById('farm-layout-data').textContent);const nav=new PetNavigation.Navigation({...FarmGarden.navigation(ToyWorkshop.navigation('room',MistwoodLayout),layout),bodyRadius:.36});const controls=new THREE.OrbitControls(camera,canvas);controls.target.set(-9,.2,4);controls.update();window.farm=new FarmGarden.View({THREE,scene,canvas,camera,controls,layout,loader,ticket,scope:SCOPE,version:'fixture',active:()=>true,focus(){},navigation:()=>nav});window.project=(x,y,z)=>{const p=new THREE.Vector3(x,y,z).project(camera);return {x:Math.round((p.x*.5+.5)*innerWidth),y:Math.round((-p.y*.5+.5)*innerHeight)};};window.faceIsland=()=>{camera.position.set(-1,12,17);camera.lookAt(0,0,0);};window.frameAt=performance.now();function frame(){const now=performance.now();farm.update((now-frameAt)/1000);frameAt=now;renderer.render(scene,camera);requestAnimationFrame(frame);}frame();loader.glb('/static/models/petchat-farm-v1/mistwood-farm.glb',ticket).then(g=>scene.add(g.scene));window.addEventListener('resize',()=>{renderer.setSize(innerWidth,innerHeight);camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();});'''
        return '<!doctype html><meta charset="utf-8"><style>body{margin:0;font-family:Arial}#world{position:fixed;inset:0}</style><canvas id="world"></canvas>'+scripts+html+'<script>const SCOPE='+__import__('json').dumps(companion_service.browser_scope())+';'+bootstrap+'</script>'
    @app.post('/fixture-mature')
    def mature():
        with get_db() as db:db.execute('UPDATE farm_plants SET planted=planted-?',(48*3600,))
        from unittest.mock import patch
        with patch.object(farm_service.secrets,'randbelow',return_value=0):farm_service.resolve_blooms(get_db(),companion_service.owner_key())
        return {'ok':True}
    server=make_server('127.0.0.1',0,app,threaded=True)
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    try:
        env={**os.environ,'GARDEN_TEST_URL':'http://127.0.0.1:'+str(server.server_port)+'/garden-test'}
        log=Path(tempfile.gettempdir())/'pait-garden-browser.log'
        with log.open('w',encoding='utf-8') as output:
            result=subprocess.run([str(Path('desktop/node_modules/electron/dist/electron.exe').resolve()),'test/farm_direct_browser.cjs'],env=env,stdout=output,stderr=output,creationflags=subprocess.CREATE_NO_WINDOW)
        print(log.read_text(encoding='utf-8',errors='replace'))
    finally:server.shutdown();worker.join();server.server_close()
    sys.exit(result.returncode)
