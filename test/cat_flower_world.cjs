const assert=require('assert'),{Controller}=require('../static/js/den/cat-agent'),{Navigation}=require('../static/js/den/scene-navigation'),farm=require('../static/js/den/farm-garden'),base=require('../static/js/den/mistwood-layout'),layout=require('../static/data/farm-layout.json'),catalog=require('../static/data/cat-world.json');
(async()=>{
 const places=layout.beds.map((b,i)=>({id:'garden:'+b.id,name:'花朵'+i,x:b.x,z:b.z,bounds:{w:b.w,d:b.d},approaches:[],actions:['observe','sniff'],dynamic:true,subject:b.id+':stage10'}));
 let world={revision:'flowers-1',places,attention:places.map(p=>({target:p.id,subject:p.subject,action:'observe',reason:'新花开了'}))},time=5000;
 for(const radius of [.36,.619]){
  const nav=new Navigation({...farm.navigation(base,layout),bodyRadius:radius}),model={position:{x:0,z:0},rotation:{y:0}},move={navigation:nav,path:[],enabled:true,owner:'idle',interrupt(){this.path=[];this.owner='idle'},goTo(p){const route=nav.route(model.position,p);if(!route)return false;this.path=route;this.owner='command';return true;}};
  const cat=new Controller({model,locomotion:move,life:{cancel(){}},scope:'fixture',animate(){},now:()=>time,storage:null,fetcher:async()=>({ok:true,json:async()=>({catalog,memory:[],world:structuredClone(world)})})});await cat.ready;cat.networkAfter=Infinity;
  const candidates=cat.candidates(),near=candidates.filter(p=>p.dynamic);assert(near.length>=6,'flower approaches accessible for radius '+radius);
  for(const p of near){const q=cat.point(p);assert(nav.isWalkable(q));assert(nav.route(model.position,q));assert(Math.hypot(p.x-q.x,p.z-q.z)>.5,'do not stand inside plant bed');}
  await cat.plan();assert(cat.goal.place.dynamic);const first=cat.goal.target,subject=cat.goal.subject;cat.finish('completed');assert(!cat.world.attention.some(a=>a.subject===subject));assert(cat.world.attention.length>0,'observing one flower does not suppress other flowers');
  cat.setWorld(structuredClone(world));assert(!cat.world.attention.some(a=>a.subject===subject),'polling cannot resurrect seen flower');
  await cat.plan();assert.equal(cat.goal.target,first);assert.equal(cat.goal.action,'sniff','observation continues into nearby sniffing');cat.finish('completed');await cat.plan();assert.notEqual(cat.goal.target,first);const target=cat.goal.target;cat.setWorld({...world,revision:'removed',places:places.filter(p=>p.id!==target)});assert.equal(cat.goal,null,'removed plant cancels stale walk');
  cat.setWorld(world);cat.energy=.1;assert.equal(cat.fallback(cat.candidates()).action,'sleep');cat.dispose();
 }
 console.log('PASS flower Agent: actual routes for two body sizes, individual memories, care priority, no stale destination or duplicate observations');
})().catch(e=>{console.error(e);process.exitCode=1});
