const T=require('../static/js/vendor/three.min.js'),{Controller:Agent}=require('../static/js/den/cat-agent'),{Controller:Life}=require('../static/js/den/cat-life'),{Controller:Move}=require('../static/js/den/pet-locomotion'),{Navigation}=require('../static/js/den/scene-navigation'),layout=require('../static/js/den/mistwood-layout'),catalog=require('../static/data/cat-world.json'),assert=require('node:assert/strict');
(async()=>{
 let now=0,state='idle',agent;const completed=[];const garden=new (require('../static/js/den/greenhouse').Garden)({scope:'test',storage:null,now:()=>now});
 const nav=new Navigation({...layout,bodyRadius:.619,obstacles:[...layout.obstacles,{x:-2.4,z:-1.2,w:1.12,d:.52}]}),model=new T.Group(),animate=k=>state=k;
 const move=new Move({navigation:nav,model,animate,rest:()=>animate('idle')}),life=new Life(T,model,move,{animate,walls:[{x:.8,z:-3.4,nx:-1,nz:0}]});
 const fetcher=async(url)=>({ok:true,json:async()=>({catalog,memory:[],scope:'s'})});
 agent=new Agent({model,locomotion:move,life,scope:'s',animate,fetcher,storage:null,now:()=>now,onComplete:g=>{completed.push(g.target);garden.interact(g.target,g.action);}});await agent.ready;agent.networkAfter=Infinity;
 for(const place of catalog){
   agent.lastTarget=null;agent.memory=Object.fromEntries(catalog.filter(p=>p!==place).map(p=>[p.id,{visits:10}]));
   await agent.plan();assert.equal(agent.goal.target,place.id);
   for(let i=0;i<7000&&agent.goal;i++){
     now+=1000/60;const blocked=!agent.acting&&!['idle','walk','trot','run','turnLeft','turnRight'].includes(state);
     agent.step(1/60,blocked);const acting=life.step(1/60,blocked);move.update(1/60,blocked||acting);assert(nav.isWalkable(model.position));
   }
   assert.equal(agent.goal,null,place.id+' finishes');assert.equal(agent.memory[place.id]?.visits,1,place.id+' completes');
 }
 assert.equal(completed.length,catalog.length);assert.equal(garden.state.plants.grass.growth,1);assert.equal(garden.state.plants.catnip.growth,1);
 agent.dispose();console.log('PASS continuous real navigation + CatLife: all twelve destinations and actions, every frame on walkable ground');
})().catch(e=>{console.error(e);process.exitCode=1});
