const assert=require('node:assert/strict'),fs=require('node:fs');
const THREE=require('../static/js/vendor/three.min.js');
const W=require('../static/js/den/toy-workshop.js'),F=require('../static/js/den/face-play.js');
const {Navigation}=require('../static/js/den/scene-navigation.js');
const {Controller:Locomotion}=require('../static/js/den/pet-locomotion.js');
function glb(path){const b=fs.readFileSync(path);return JSON.parse(b.subarray(20,20+b.readUInt32LE(12)).toString());}
const cabinet=glb('static/models/petchat-toys-v1/cabinet.glb');
assert.equal(cabinet.meshes.length,8);
assert.deepEqual(cabinet.nodes.filter(n=>n.extras?.toy_id).map(n=>n.extras.toy_id).sort(),W.catalog.map(i=>i.id).sort());
for(const m of cabinet.meshes)for(const p of m.primitives)assert.notEqual(p.attributes.COLOR_0,undefined);
for(const n of cabinet.nodes.filter(n=>n.extras?.toy_id)){
 const p=cabinet.meshes[n.mesh].primitives[0],bounds=cabinet.accessors[p.attributes.POSITION];
 for(let i=0;i<3;i++)assert(Math.abs(bounds.min[i]+bounds.max[i])<1e-5,'toy origin must be its own bounds center, not the cabinet origin');
}
for(const theme of ['sakura','snow']){
 const scene=glb(`static/models/petchat-toys-v1/${theme}.glb`);
 assert.equal(scene.nodes.filter(n=>n.extras?.toy_id==='ball').length,1);
 const base=theme==='snow'?require('../static/js/den/snow-haven-layout.js'):{...JSON.parse(fs.readFileSync('templates/den.html','utf8').match(/const SAKURA_NAV = (\{[^\n]+\});/)[1]),...require('../static/js/den/sakura-river-layout.js')};
 for(const bodyRadius of (theme==='sakura'?[.25,.36,.5,.65]:[.36,.5,.65,.81])){
  const nav=new Navigation({...W.navigation(theme,base),bodyRadius});
  assert(nav.isWalkable({x:0,z:0}),theme+' spawn clear');
  assert(!nav.isWalkable(W.positions[theme]),'cabinet is an obstacle');
  assert(nav.randomDestination({x:0,z:0}),'courtyard remains connected');
  if(theme==='sakura')assert(!nav.isWalkable({x:2,z:1.3}),'river still excluded');
  else assert(!nav.isWalkable({x:-1.4,z:1.72}),'pond excluded');
 }
}
console.log('PASS modeled toy identities, vertex colors, cabinet/river/pond navigation');
const dom=new Map();global.document={getElementById(id){if(!dom.has(id))dom.set(id,{textContent:'',hidden:true});return dom.get(id)}};
const scene=new THREE.Scene(),model=new THREE.Group(),parent=new THREE.Group();scene.add(parent,model);parent.position.set(.2,0,.3);
const node=new THREE.Mesh(new THREE.SphereGeometry(.1),new THREE.MeshBasicMaterial());node.position.set(-.7,.2,.5);parent.add(node);scene.updateMatrixWorld(true);
let disposed=0;node.geometry.addEventListener('dispose',()=>disposed++);
const nav=new Navigation({radius:3,bodyRadius:.2,water:[{x:1,z:0,w:.5,d:2}]}),loc=new Locomotion({navigation:nav,model,animate(){},rest(){},speed:1});
const a={THREE,scene,model:()=>model,id:()=>1,mouth:()=>model.position.clone().add(new THREE.Vector3(0,.7,.1)),busy:()=>false,act(){},say(){},locomotion:()=>loc,canvas:{style:{},hasPointerCapture:()=>false}};
const f=Object.create(F.Controller.prototype);Object.assign(f,{a,bones:[],touch:new F.Touch(),halo:{hidden:true},look:{x:0,y:0,r:0},note(){},render(){}});
const w=Object.create(W.Controller.prototype);Object.assign(w,{a:{...a,face:()=>f,cancelCommands(){},flightPoint:F.flightPoint},records:[],preview:{visible:false},hud:{hidden:true},render(){},tip:{textContent:''},lastUse:0});
const r={node,spec:W.catalog[0],parent,position:node.position.clone(),quaternion:node.quaternion.clone(),scale:node.scale.clone(),offset:.1,state:'available',stored:true};w.records=[r];
assert(w.take(r));assert.equal(f.ball.mesh,node);assert.equal(node.parent,scene);w.cancel();assert.equal(node.parent,parent);assert(node.position.equals(r.position));assert.equal(disposed,0);
assert(w.take(r));w.evaluateTarget=()=>({valid:false});w.release();assert.equal(node.parent,parent);assert.equal(w.held,null);
assert(w.take(r));w.evaluateTarget=()=>({valid:true,point:new THREE.Vector3(-1,nav.surfaceHeight({x:-1,z:.5})+.1,.5)});w.mode='place';w.release();assert.equal(f.ball.fetch,false);f.updateBall(f.ball.at+701);assert.equal(r.state,'available');assert.equal(r.stored,false);assert(node.position.distanceTo(new THREE.Vector3(-1,nav.surfaceHeight({x:-1,z:.5})+.1,.5))<1e-8);
const placed=node.position.clone();w.take(r);node.position.set(2,2,2);w.cancel();assert(node.position.equals(placed));assert.equal(node.parent,scene);
w.take(r);w.mode='throw';w.release();const start=f.ball.at,from=f.ball.from.clone(),target={x:-1,y:nav.surfaceHeight({x:-1,z:.5})+.1,z:.5};
f.updateBall(start+350);const expected=F.flightPoint(from,target,.5,.65);assert(node.position.distanceTo(new THREE.Vector3(expected.x,expected.y,expected.z))<1e-8);
let carried=false,returned=false;
for(let t=360;t<15000;t+=20){loc.update(.02,false);f.updateBall(start+t,.02);assert(nav.isWalkable(model.position));if(f.ball?.phase==='return')carried=true;if(f.ball?.phase==='drop')returned=true;}
assert(carried&&returned);assert.equal(f.ball,null);assert.equal(w.held,null);assert.equal(node.parent,scene);assert.equal(disposed,0);
w.take(r);w.grab(false,null,'lost');assert.equal(w.held,null);assert.equal(r.state,'available');
console.log('PASS physical identity, cancel/invalid target, placement/re-pick, shared flight, fetch/return, hand loss; no resource disposal');
let invitesCredited=0;a.onFetch=()=>invitesCredited++;
assert(w.invite('ball',{x:0,z:-1}));assert(f.ball.autonomous);const inviteStart=performance.now();let invitationCarried=false;
for(let t=0;t<16000&&f.ball;t+=20){loc.update(.02,false);f.updateBall(inviteStart+t,.02);if(f.ball?.phase==='return')invitationCarried=true;assert(nav.isWalkable(model.position));}
assert(invitationCarried);assert.equal(f.ball,null);assert.equal(w.held,null);assert.equal(invitesCredited,0,'autonomous invitation is not invented user play');
assert(w.invite('ball',{x:0,z:0}));w.cancel();assert.equal(f.ball,null);assert.equal(w.held,null);
console.log('PASS autonomous invitation: carries real ground toy, safe return, cancellation, no fabricated interaction credit');

r.spec=W.catalog.find(i=>i.id==='brush');w.take(r);assert.equal(f.ball,null);assert.equal(w.mode,'place');w.release();assert.equal(r.state,'available');assert.equal(w.held,null);
const camera=new THREE.PerspectiveCamera(45,1,.1,50);camera.position.set(0,4,5);camera.lookAt(node.position);camera.updateMatrixWorld(true);scene.updateMatrixWorld(true);
w.a.camera=camera;w.a.canvas.clientWidth=500;w.a.canvas.clientHeight=500;w.ray=new THREE.Raycaster();assert.equal(w.pick(250,250),r,'ray picks the real prop');
let cabinetDisposed=0;w.root=new THREE.Group();scene.add(w.root);w.a.dispose=root=>{assert.equal(root,w.root);cabinetDisposed++;};w.dialog={close(){}};w.clear();assert.equal(cabinetDisposed,1);assert.equal(node.parent,parent);assert.equal(disposed,0);assert.equal(w.records.length,0);w.clear();assert.equal(cabinetDisposed,1);
console.log('PASS brush placement, real ray picking, scene switch restores props and releases cabinet once');
// Supply variants clone shared materials and restore them before a free toy is selected.
const original=node.material;r.spec=W.catalog[0];w.records=[r];r.state='available';w.dialog={close(){}};
const savedTake=w.takeKind;w.takeKind=function(kind){this.resetSupply(r);this.held=r;};
assert(w.takeSupply({id:'star_ball',name:'星光弹力球',effect:'ball'}));assert.notEqual(node.material,original);assert.equal(original.color.getHex(),0xffffff);
let cloneDisposed=0;node.material.addEventListener('dispose',()=>cloneDisposed++);w.resetSupply(r);assert.equal(node.material,original);assert.equal(r.spec.name,'彩纹球');assert.equal(cloneDisposed,1);w.takeKind=savedTake;w.held=null;
console.log('PASS purchased toy style: shared material isolation, original free toy and disposal');

// A held rattle uses the real river router, including the bridge, rather than a straight chase.
const riverBase={...JSON.parse(fs.readFileSync('templates/den.html','utf8').match(/const SAKURA_NAV = (\{[^\n]+\});/)[1]),...require('../static/js/den/sakura-river-layout.js')};
const riverNav=new Navigation({...W.navigation('sakura',riverBase),bodyRadius:.36});
model.position.set(1.4,0,0);
const runner=new Locomotion({navigation:riverNav,model,animate(){},rest(){},gaits:{walk:.55,trot:.9,run:1.5}});runner.enabled=false;
w.a.locomotion=()=>runner;w.a.busy=()=>false;r.spec=W.catalog.find(i=>i.id==='rattle');w.take(r);
let aim=new THREE.Vector3(0,0,2.35);
w.evaluateTarget=()=>({valid:riverNav.isWalkable(aim)&&!!riverNav.route(model.position,aim),point:aim});
assert(w.followRattle());assert.equal(runner.requestedGait,'run');
const initial=runner.path;assert(w.followRattle());assert.equal(runner.path,initial,'same destination does not restart path');
let crossed=false;
for(let i=0;i<1600&&runner.path.length;i++){
 runner.update(.02,false);assert(riverNav.isWalkable(model.position));
 if(Math.abs(model.position.z-1.3)<.2){crossed=true;assert(Math.abs(model.position.x)<.8,'cross on bridge');}
}
assert(crossed);assert(Math.hypot(model.position.x-aim.x,model.position.z-aim.z)<.03);
aim=new THREE.Vector3(1.4,0,0);assert(w.followRattle());assert(runner.path.length);
aim=new THREE.Vector3(2,0,1.3);assert.equal(w.followRattle(),false);assert.equal(runner.path.length,0,'invalid river aim cancels chase');
aim=new THREE.Vector3(0,0,0);assert(w.followRattle());w.cancel();assert.equal(runner.path.length,0,'putting away stops chase');
w.take(r);assert(w.followRattle());runner.goTo({x:0,z:2.2});const replacement=runner.path;w.stopRattle();assert.equal(runner.path,replacement,'do not cancel another movement owner');
w.cancel();
console.log('PASS rattle run follows bridge, safe retargeting, invalid water, cancellation and movement ownership');
// Run the real page guard: holding other toys still blocks wandering; a rattle route can move.
const vm=require('node:vm'),page=fs.readFileSync('templates/den.html','utf8');
const guard=page.match(/function movementBlocked\(\) \{([\s\S]*?)\n        \}/)[1];
const env={portals:null,catAgent:null,supplyCare:null,document:{hidden:false,querySelector:()=>null,getElementById:()=>({classList:{contains:()=>true}})},toyWorkshop:{held:{state:'held',spec:{id:'rattle'}},rattlePath:[{}]},facePlay:{},spawnBusy:false,petModel:{},anim:{birth:1,state:'run',until:0},grabbed:false,dropping:false,bounceBack:0,interactionBusy:()=>false,performing:()=>false,chatBusy:false,voiceBusy:false,dialogueRunner:{active:false},breathActive:false,gameOverlay:{hidden:true},gamesMask:{hidden:true},moodMask:{hidden:true},performance:{now:()=>5000}};
const blocked=()=>vm.runInNewContext('(function(){'+guard+'})()',env);
assert.equal(blocked(),false);env.toyWorkshop.rattlePath=null;assert.equal(blocked(),true);
env.toyWorkshop.rattlePath=[{}];env.toyWorkshop.held.spec.id='brush';assert.equal(blocked(),true);
console.log('PASS live page movement guard allows only active rattle pursuit while holding a prop');
