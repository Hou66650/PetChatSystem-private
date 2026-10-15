// Isolated file fixture: no browser profile, login, live page or remote request.
const {app,BrowserWindow,ipcMain}=require('electron'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),{pathToFileURL}=require('node:url');
const root=path.resolve(__dirname,'..'),temp=fs.mkdtempSync(path.join(os.tmpdir(),'cat-polish-'));
app.setPath('userData',path.join(temp,'profile'));
ipcMain.handle('fixture',()=>{const b=fs.readFileSync(path.join(root,'static/models/petchat-cat-v3/cat.glb'));return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);});
app.whenReady().then(async()=>{
 const w=new BrowserWindow({width:1120,height:1450,show:false,webPreferences:{preload:path.join(__dirname,'visit-preload.cjs'),sandbox:true,contextIsolation:true,offscreen:true,backgroundThrottling:false}});
 const script=p=>'<script src="'+pathToFileURL(path.join(root,p)).href+'"></script>';
 fs.writeFileSync(path.join(temp,'index.html'),'<body style="margin:0;background:#e9e5da"><canvas id="card"></canvas>'+['static/js/vendor/three.min.js','static/js/vendor/GLTFLoader.js','static/js/den/portal-pets.js','static/js/den/cat-life.js','static/js/den/cat-paths.js','static/js/den/cat-share-card.js'].map(script).join('')+`<script>
 async function run(){
 const canvas=document.getElementById('card');CatShareCard.draw(canvas,{path:'M-2 -3 L-1 -3 L0 -2 L0 0 L0 3 L1 4',distance:8.2,points:43,names:['温室石墙','林间花园','桥另一端'],time:1792022400000,stale:false});
 const png=await new Promise(r=>canvas.toBlob(r));if(!png||png.size<20000)throw Error('PNG export failed');return {size:png.size,data:canvas.toDataURL('image/png').split(',')[1]};
 }
 async function poses(){document.body.replaceChildren();const bytes=await visitFixture.request();const gltf=await new Promise((r,j)=>new THREE.GLTFLoader().parse(bytes,'',r,j));const pet=new PortalPets.Pet(THREE,gltf,{height:.85}),scene=new THREE.Scene();scene.add(pet.root);scene.add(new THREE.HemisphereLight(0xffffff,0x84957d,1.2));const light=new THREE.DirectionalLight(0xffecd1,1.4);light.position.set(2,4,3);scene.add(light);const camera=new THREE.PerspectiveCamera(32,1,.01,20);camera.position.set(1.3,.85,2.3);camera.lookAt(0,.43,0);
 const renderer=new THREE.WebGLRenderer({antialias:true,alpha:true,preserveDrawingBuffer:true});renderer.setSize(480,480);renderer.outputEncoding=THREE.sRGBEncoding;renderer.toneMapping=THREE.ACESFilmicToneMapping;
 const move={navigation:{surfaceHeight:()=>0},velocity:0},life=new CatLife.Controller(THREE,pet.root,move);pet.play('idle');pet.update(.01);
 for(const [kind,time,side] of [['idle',0,1],['groom',2,-1],['groom',5.2,1],['mouthClean',.7,1],['stretch',2.3,1],['rub',2,1]]){life.beforeFrame();pet.mixer.stopAllAction();const base=gltf.animations.find(a=>a.name===(kind==='groom'?'sit_idle':'idle_breathe'));pet.mixer.clipAction(base).reset().play();pet.mixer.update(.1);pet.model.updateMatrixWorld(true);life.elapsed=time;life.active=kind==='idle'?null:{kind,time,side,duration:kind==='groom'?7.2:5.4};life.pose(1/60,'idle');renderer.render(scene,camera);const frame=document.createElement('div');frame.style='display:inline-block;width:500px;text-align:center;font:24px sans-serif';const img=document.createElement('img');img.src=renderer.domElement.toDataURL();frame.append(img,document.createTextNode(kind+' '+time+'s'));document.body.append(frame);}return true;
 }
 </script>`);
 try{await w.loadFile(path.join(temp,'index.html'));const card=await w.webContents.executeJavaScript('run()');console.log('PNG bytes',card.size);fs.writeFileSync(path.join(os.tmpdir(),'pait-cat-share-export.png'),Buffer.from(card.data,'base64'));await new Promise(r=>setTimeout(r,200));fs.writeFileSync(path.join(os.tmpdir(),'pait-cat-share.png'),(await w.webContents.capturePage()).toPNG());await w.webContents.executeJavaScript('poses()');await new Promise(r=>setTimeout(r,300));fs.writeFileSync(path.join(os.tmpdir(),'pait-cat-poses.png'),(await w.webContents.capturePage()).toPNG());console.log('PASS actual WebGL pose sheet and PNG card export');app.exit(0);}catch(e){console.error(e);app.exit(1);}
});
