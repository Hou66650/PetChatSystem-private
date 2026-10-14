const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
const THREE=require('../static/js/vendor/three.min.js');
const F=require('../static/js/den/face-play.js');
const {Navigation}=require('../static/js/den/scene-navigation.js');
const {Controller:Locomotion}=require('../static/js/den/pet-locomotion.js');
const source=fs.readFileSync('static/js/den_vision.js','utf8').replace(/^import .*;$/m,'');
const flush=()=>new Promise(r=>setImmediate(r));
let passes=0;
async function check(name,fn){await fn();passes++;console.log('PASS '+name);}
function stream(){const track={readyState:'live',stops:0,stop(){this.stops++;this.readyState='ended';}};return {track,getTracks:()=>[track],getVideoTracks:()=>[track]};}
function harness(overrides={}){
 const models=[],requested=[];
 const task={createFromOptions:async(f,o)=>{requested.push(o);const model={closed:0,close(){this.closed++},detectForVideo(){return {}}};models.push(model);return model;}};
 const context={window:{},navigator:{mediaDevices:{getUserMedia:async()=>stream()}},FilesetResolver:{forVisionTasks:async()=>({})},FaceLandmarker:task,HandLandmarker:task,performance:{now:()=>10000},setTimeout,clearTimeout,setInterval,clearInterval,requestAnimationFrame:()=>1,cancelAnimationFrame(){},...overrides};
 vm.runInNewContext(source,context);
 return {D:context.window.DenVision,context,models,requested};
}
const video=()=>({srcObject:null,readyState:2,currentTime:1,clientWidth:640,clientHeight:480,play:async()=>{}});
(async()=>{
 await check('calibration clamps invalid preferences and preserves independent switches',()=>{
  assert.equal(F.settings({sensitivity:99,lift:true,face:false}).sensitivity,2.5);
  assert.equal(F.settings({hands:false}).hands,false);assert.equal(F.settings().lift,false);
  assert.equal(F.settings({sensitivity:'bad'}).sensitivity,1.3);
 });
 await check('touch distinguishes zones, requires movement, and rewards at a bounded rate',()=>{
  const zones=[{id:'head',x:0,y:0,rx:10,ry:10},{id:'chin',x:0,y:20,rx:6,ry:6}];
  assert.equal(F.zoneAt({x:0,y:20},zones).id,'chin');assert.equal(F.zoneAt({x:100,y:20},zones),null);
  const touch=new F.Touch();touch.sample({x:0,y:0},'head',0);
  let rewards=0;
  for(let t=100;t<=10000;t+=100){const r=touch.sample({x:(t/100)%2*10,y:0},'head',t);if(r.reward)rewards++;}
  assert.equal(rewards,2);let nuzzles=0;
  for(let t=10100;t<=12000;t+=100){if(touch.sample({x:0,y:0},'head',t).nuzzle)nuzzles++;}
  assert.equal(nuzzles,1);touch.reset();assert.equal(touch.zone,null);
 });
 await check('face-only loads one model, wires blink/snap, and frees camera/models on stop',async()=>{
  const h=harness(),d=new h.D(),v=video();let blink=0,snap=0;
  d.configure({hands:false});assert.equal(await d.start(v,{onBlink:()=>blink++,onSnap:()=>snap++}),true);
  d.onBlink();d.onSnap();assert.equal(blink,1);assert.equal(snap,1);
  assert.equal(h.models.length,1);const s=d.stream;d.stop();assert.equal(s.track.stops,1);assert.equal(h.models[0].closed,1);assert.equal(v.srcObject,null);
 });
 await check('late camera permission cannot replace or stop a newer camera session',async()=>{
  const pending=[];const h=harness({navigator:{mediaDevices:{getUserMedia:()=>new Promise(r=>pending.push(r))}}}),d=new h.D();
  const first=d.start(video());d.stop();const second=d.start(video());
  const s2=stream();pending[1](s2);assert.equal(await second,true);
  const s1=stream();pending[0](s1);assert.equal(await first,false);
  assert.equal(s1.track.stops,1);assert.equal(s2.track.stops,0);assert.equal(d.stream,s2);d.stop();
 });
 await check('stop during model creation closes late model and cannot restart inference',async()=>{
  let resolveModel;const late={closed:0,close(){this.closed++}};
  const h=harness({FaceLandmarker:{createFromOptions:()=>new Promise(r=>resolveModel=r)}}),d=new h.D();
  const pending=d.start(video());await flush();const s=d.stream;d.stop();resolveModel(late);
  assert.equal(await pending,false);assert.equal(late.closed,1);assert.equal(s.track.stops,1);assert.equal(d.running,false);
 });
 await check('main-thread fallback requests GPU and reports the selected delegate',async()=>{
  const h=harness({document:{createElement:()=>({getContext:()=>({})})}}),d=new h.D();d.configure({hands:false});
  assert.equal(await d.start(video()),true);assert.equal(h.requested[0].baseOptions.delegate,'GPU');assert.equal(d.delegate,'GPU');d.stop();assert.equal(h.models[0].closed,1);
 });
 await check('GPU initialization failure releases context and falls back to CPU',async()=>{
  const attempts=[];let lost=0,closed=0;
  const h=harness({document:{createElement:()=>({getContext:()=>({getExtension:()=>({loseContext(){lost++;}})})})},FaceLandmarker:{createFromOptions:async(f,o)=>{attempts.push(o.baseOptions.delegate);if(o.baseOptions.delegate==='GPU')throw Error('driver unavailable');return {close(){closed++;}};}}}),d=new h.D();d.configure({hands:false});
  assert.equal(await d.start(video()),true);assert.deepEqual(attempts,['GPU','CPU']);assert.equal(lost,1);assert.equal(d.delegate,'CPU');d.stop();assert.equal(closed,1);
 });
 await check('mirror and calibration map a comfortable hand center to the canvas center',()=>{
  const {D}=harness(),d=new D();d.canvasSize={w:800,h:600};d.handState.present=true;d.lastRaw={x:.3,y:.6};
  d.calibrate();assert.equal(d._point(.3,.6).x,400);assert.equal(d._point(.3,.6).y,300);
  assert(d._point(.4,.6).x<400);d.configure({mirror:false});assert(d._point(.4,.6).x>400);
 });
 await check('worker mode bounds in-flight frames and closes a stale captured bitmap',async()=>{
  let worker;class Worker{constructor(){worker=this;this.terminated=false;this.frames=0;}postMessage(m){if(m.type==='init')queueMicrotask(()=>this.onmessage({data:{type:'ready'}}));else this.frames++;}terminate(){this.terminated=true;}}
  let resolveBitmap;const h=harness({Worker,OffscreenCanvas:class {},createImageBitmap:()=>new Promise(r=>resolveBitmap=r)}),d=new h.D(),v=video();
  await d.start(v);d._detect();v.currentTime++;d._detect();assert.equal(d.pending,true);assert.equal(worker.frames,0);
  const bitmap={closed:0,close(){this.closed++;}};d.stop();resolveBitmap(bitmap);await flush();
  assert.equal(bitmap.closed,1);assert.equal(worker.terminated,true);assert.equal(h.models.length,0);
 });
 await check('a blocked Worker constructor falls back to the selected main-thread model',async()=>{
  const h=harness({Worker:class {constructor(){throw new Error('blocked')}},OffscreenCanvas:class {},createImageBitmap(){}}),d=new h.D();
  d.configure({face:false,hands:true});assert.equal(await d.start(video()),true);assert.equal(d.backend,'main');assert.equal(h.models.length,1);d.stop();
 });
 await check('pose overlays restore quaternion state instead of accumulating over frames',()=>{
  const bone=new THREE.Bone();bone.quaternion.setFromEuler(new THREE.Euler(.1,.2,.3));const original=bone.quaternion.clone();
  const c=Object.create(F.Controller.prototype);c.bones=[{bone,base:original.clone()}];
  for(let i=0;i<1000;i++){bone.quaternion.multiply(new THREE.Quaternion().setFromEuler(new THREE.Euler(.01,.02,0)));c.beforeFrame();assert(bone.quaternion.angleTo(original)<1e-7);c.bones[0].base=original.clone();}
 });
 await check('ball refuses water and uses real navigation for chase, mouth carry and return',()=>{
  const nav=new Navigation({radius:3,bodyRadius:.2,water:[{x:1,z:0,w:.5,d:2}],bridges:[]});
  const model=new THREE.Group();model.userData.height=1;const scene=new THREE.Scene();
  const a={THREE,scene,model:()=>model,id:()=>1,head:()=>model.position.clone().add(new THREE.Vector3(0,.8,0)),mouth:()=>model.position.clone().add(new THREE.Vector3(0,.7,.1)),busy:()=>false,act(){},say(){},reward(){}};
  const loc=new Locomotion({navigation:nav,model,animate(){},rest(){},speed:1});a.locomotion=()=>loc;
  const c=Object.create(F.Controller.prototype);Object.assign(c,{a,bones:[],touch:new F.Touch(),halo:{hidden:true},look:{x:0,y:0,r:0},note(){}});
  c.holdBall();c.throwBall({x:1,z:0});assert.equal(c.ball,null);assert.equal(scene.children.length,0);
  c.holdBall();c.throwBall({x:-1,z:.5});const start=c.ball.at;let returned=false,carried=false;
  for(let t=0;t<15000;t+=20){loc.update(.02,false);c.updateBall(start+t);assert(nav.isWalkable(model.position));if(c.ball?.phase==='return'){carried=true;assert(c.ball.mesh.position.distanceTo(a.mouth())<.001);}if(c.ball?.phase==='drop')returned=true;}
  assert(carried);assert(returned);assert.equal(c.ball,null);assert.equal(scene.children.length,0);
  // Wall-clock gaps must not spend the navigation's simulation-time budget.
  c.holdBall();c.throwBall({x:-1,z:.5});const slowStart=c.ball.at;returned=false;
  for(let t=0;t<15000;t+=20){loc.update(.02,false);c.updateBall(slowStart+t*100,.02);if(c.ball?.phase==='drop')returned=true;}
  assert(returned,'throttled rendering still completes the fetch');assert.equal(c.ball,null);
 });
 console.log(JSON.stringify({passed:passes}));
})().catch(e=>{console.error(e);process.exitCode=1});
