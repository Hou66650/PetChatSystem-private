/* Motion regressions without external GLBs; use the shipped Three.js mixer. */
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {Controller,gaitSpeeds}=require('../static/js/den/pet-locomotion');
const {Navigation}=require('../static/js/den/scene-navigation');
const T=require('../static/js/vendor/three.min.js');
{
 const action=name=>({getClip:()=>({name})});
 const native=gaitSpeeds({walk:action('walk'),trot:action('trot'),run:action('run'),turnLeft:action('left')},2);
 assert.equal(native.walk,.696);assert.equal(native.trot,1.364);assert.equal(native.run,2);assert.equal(native.turnRight,undefined);
 const custom=gaitSpeeds({walk:action('walk'),trot:action('walk'),run:action('run')},2);
 assert.equal(custom.walk,custom.trot,'aliased cloned clips preserve distance per cycle');assert.equal(custom.run,2);
 assert.equal(gaitSpeeds({walk:action('walk')},2),null,'legacy no-run fallback');
 assert.equal(gaitSpeeds({walk:action('walk'),run:action('run')},1).trot,undefined,'do not advertise a missing gait');
}
function fixture(navigation=new Navigation({radius:10})){
 const model={position:{x:0,z:0},rotation:{y:0}},frames=[];
 const c=new Controller({navigation,model,speed:.34,gaits:{walk:.32,trot:.63,run:.93,turnLeft:1,turnRight:1},animate:(key,rate)=>frames.push({key,rate}),rest:()=>{}});
 c.autonomous=false;return {c,model,frames};
}
function trip(gait,dt){
 const f=fixture();f.c.goTo({x:0,z:4},{gait});let time=0,beforeStop=0;
 for(;time<60&&f.c.path.length;time+=dt){
  const before=f.c.velocity,z=f.model.position.z;
  f.c.update(dt);assert(f.c.navigation.isWalkable(f.model.position));
  if(f.c.path.length){
   assert(Math.abs(f.c.velocity-before)<=1.6*dt+.00001,'bounded linear acceleration');
   const a=f.frames.at(-1);assert(Math.abs(a.rate*f.c.gaits[a.key]-(f.model.position.z-z)/dt)<1e-9,'feet follow actual displacement');
  }else beforeStop=before;
 }
 assert(time<60);assert(beforeStop<.065,`gentle arrival: ${beforeStop}`);
 assert.equal(f.c.acceleration,0);assert.equal(f.c.turnRate,0);assert.equal(f.c.gait,'walk');
 assert(Math.abs(f.model.position.z-4)<1e-9);return {...f,time};
}
const walk=trip('walk',.02),run=trip('run',.02);
assert(run.time<walk.time*.7);for(const gait of ['walk','trot','run'])assert(run.frames.some(f=>f.key===gait));
const times=[30,60,120].map(fps=>trip('run',1/fps).time);
assert(Math.max(...times)-Math.min(...times)<.25,'comparable travel across frame rates');
{
 const {c}=fixture();c.goTo({x:0,z:4},{gait:'run'});for(let i=0;i<100;i++)c.update(.02);
 assert(c.velocity>.9);c.goTo({x:0,z:6},{gait:'walk'});
 for(let i=0;i<100;i++){const before=c.velocity;c.update(.02);assert(Math.abs(c.velocity-before)<=1.6*.02+1e-8,'run-to-walk command must decelerate, not clamp speed in one frame');}
 assert(Math.abs(c.velocity-c.speed)<.01);
}
{
 const {c,model}=fixture();c.path=[{x:0,z:0},{x:0,z:.005},{x:0,z:2}];const path=c.path;c.velocity=.3;
 c.update(.02);assert.equal(c.path,path);assert.equal(c.path.length,1);assert(model.position.z>.005,'no stationary waypoint frame');
 c.interrupt();const before=JSON.stringify(c.debug());c.update(0);c.update(NaN);assert.equal(JSON.stringify(c.debug()),before);
}
{
 const {c,model}=fixture();c.goTo({x:3,z:0});for(let i=0;i<8;i++)c.update(.02);
 const rate=c.turnRate,yaw=model.rotation.y;assert(rate>0);
 c.goTo({x:-3,z:0});c.update(.02);
 const actual=(model.rotation.y-yaw)/.02;
 assert(actual>0&&Math.abs(actual-rate)<1.37,'no instantaneous angular reversal');assert(Math.abs(actual-c.turnRate)<1e-9);
 c.update(.02,true);assert.equal(c.velocity,0);assert.equal(c.path.length,0);
}
{
 const {c,model}=fixture();c.path=[{x:0,z:2},{x:2,z:2}];c.requestedGait='run';let entrySpeed=null;
 for(let i=0;i<4000&&c.path.length;i++){const count=c.path.length;c.update(.02);if(count===2&&c.path.length===1)entrySpeed=c.velocity;}
 assert(entrySpeed!==null&&entrySpeed<.45,'brake before a right-angle corner');assert.equal(c.path.length,0);assert.equal(model.position.x,2);
}
{
 const navigation=new Navigation({radius:5,bodyRadius:.2,obstacles:[{kind:'rect',x:0,z:1.5,w:1,d:1}]}),{c,model}=fixture(navigation);
 c.goTo({x:0,z:3},{gait:'run'});assert(c.path.length>1);
 for(let i=0;i<4000&&c.path.length;i++){const before={...model.position};c.update(.02);assert(navigation.segmentClear(before,model.position),'no corner cutting through scenery');}
 assert.equal(c.path.length,0);assert.equal(model.position.z,3);
}
{
 const {c,model,frames}=fixture();model.position.z=.3;
 c.navigation.dock={entry:{x:0,z:0},target:{x:0,z:.3}};c.interrupt();
 for(let i=0;i<1000&&c.path.length;i++){c.update(.02);assert.equal(model.rotation.y,0,'back away while facing the bowl');}
 assert.equal(c.navigation.dock,null);assert(frames.some(f=>f.key==='walk'&&f.rate<0));
}
{
 const ctx={};vm.runInNewContext(fs.readFileSync('static/js/den/portal-pets.js','utf8'),ctx);
 const scene=new T.Group();scene.add(new T.Mesh(new T.BoxGeometry(1,1,1),new T.MeshBasicMaterial()));
 const clips=['idle_breathe','motion_walk','motion_trot','run','turn_left','turn_right'].map((name,i)=>new T.AnimationClip(name,1+i*.2,[new T.NumberKeyframeTrack('.position[x]',[0,.5,1],[0,.1,0])]));
 const pet=new ctx.PortalPets.Pet(T,{scene,animations:clips},{height:1});
 pet.play('walk',.5);for(let i=0;i<10;i++)pet.update(.04);
 const phase=pet.active.time/pet.active.getClip().duration;
 pet.play('trot',.7);assert.equal(pet.active.getClip().name,'motion_trot');assert(Math.abs(pet.active.time/pet.active.getClip().duration-phase)<1e-9);
 const action=pet.active,time=action.time;pet.play('trot',0);pet.update(.04);assert.equal(action.time,time);
 pet.play('trot',-.5);pet.update(.04);assert(action.time<time,'reverse gait for retreat');
 pet.play('turnLeft',.4);assert.equal(pet.active.getClip().name,'turn_left');assert.equal(pet.active.getEffectiveTimeScale(),.4);
 pet.play('idle');assert.equal(pet.active.getEffectiveTimeScale(),1,'desktop calls retain default playback');
}
console.log('PASS smooth arrivals, waypoint continuity, signed turning, corner braking, collision safety, frame rates, retreat and Three.js gait phase/rate');
