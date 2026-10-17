const assert=require('node:assert/strict'),fs=require('node:fs');
const {Agent}=require('../static/js/park-agent.js'),{Motion,clips}=require('../static/js/park-motion.js');
const navigation=require('../static/js/park-navigation.js').create(require('../static/models/paw-commons-v2/navigation.json'));
let seed=43;const random=()=>((seed=(seed*1664525+1013904223)>>>0)/4294967296);
const agent=new Agent({navigation,random}),pos={x:4,z:2},activities=new Set(),actions=new Set();let route=[],speed=1,movement=0;
for(let t=0;t<600;t+=.25){
 const cmd=agent.tick({now:t,dt:.25,pos,peers:[],moving:route.length>0});
 if(cmd){assert(!cmd.cancel,'solo navigation should complete');activities.add(cmd.activity);actions.add(cmd.action);if(cmd.destination)route=navigation.route(pos,cmd.destination);speed=cmd.speed;}
 let budget=.25*speed;
 while(route.length&&budget>0){const end=route[0],d=Math.hypot(end.x-pos.x,end.z-pos.z),step=Math.min(d,budget),next=d<1e-6?end:{x:pos.x+(end.x-pos.x)/d*step,z:pos.z+(end.z-pos.z)/d*step};assert(navigation.segment(pos,next));Object.assign(pos,next);budget-=step;movement+=step;if(d<=step+.001)route.shift();}
}
for(const kind of ['explore','play','rest'])assert(activities.has(kind),'needs choose '+kind);assert(movement>10);assert(actions.has('sleep'));assert(actions.has('stretch'));assert(!activities.has('greet'),'no invented companions');
agent.interrupt(700,12);assert.equal(agent.tick({now:705,dt:.25,pos}),null);agent.enable(false,720);assert.equal(agent.tick({now:1000,dt:.25,pos}),null);
const social=new Agent({navigation,personality:'gentle',random});social.social=1;social.curiosity=0;social.playfulness=0;
const peer={id:'peer',x:3,z:2,action:'idle'};let cmd=social.tick({now:0,dt:.25,pos:{x:-3,z:2},peers:[peer]});assert.equal(cmd.activity,'greet');assert(Math.hypot(cmd.destination.x-peer.x,cmd.destination.z-peer.z)>1.4);
assert(social.tick({now:1,dt:.25,pos:{x:-3,z:2},peers:[]}).cancel,'departed peer cancels greeting');
const tired=new Agent({navigation,random});tired.energy=.1;assert.equal(tired.tick({now:0,dt:.25,pos}).activity,'rest');
for(const file of ['petchat-shiba-v4/qiuqiu','petchat-husky-v3/xueqiu','petchat-cat-v3/cat','petchat-shepherd-v2/shepherd']){
 const b=fs.readFileSync('static/models/'+file+'.glb'),g=JSON.parse(b.subarray(20,20+b.readUInt32LE(12))),names=g.animations.map(a=>a.name.split('|').pop());
 for(const [key,options] of Object.entries(clips))assert(options.some(x=>names.includes(x)),file+' supports '+key);
 for(const transition of ['sit_down','lie_down','stand_up'])assert(names.includes(transition));
}
// Verify one-shot entry clips settle, instead of replaying a sit-down every frame.
const started=[],mockAction=clip=>({clip,reset(){return this},setEffectiveWeight(){return this},setEffectiveTimeScale(){return this},setLoop(mode){this.loop=mode;return this},fadeIn(){return this},play(){started.push(clip.name);return this},fadeOut(){return this}});
const anims=['idle_breathe','sit_down','sit_idle','lie_down','sleep_loop','stand_up','motion_walk'].map(name=>({name,duration:1})),cache=new Map();
const motion=new Motion({T:{LoopOnce:1,LoopRepeat:2},clips:anims,mixer:{clipAction(c){if(!cache.has(c))cache.set(c,mockAction(c));return cache.get(c)}},update(){}});
for(let i=0;i<12;i++)motion.update('sit',.1);assert.deepEqual(started,['sit_down','sit_idle']);
for(let i=0;i<12;i++)motion.update('walk',.1);assert.deepEqual(started.slice(2),['stand_up','motion_walk']);
console.log('PASS 10-minute autonomous needs cycle, collision-safe routes, social departure, manual/pause, four rigs and posture transitions');
