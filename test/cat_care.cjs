const assert=require('node:assert/strict'),T=require('../static/js/vendor/three.min.js'),{Controller:Agent}=require('../static/js/den/cat-agent'),{Controller:Life}=require('../static/js/den/cat-life'),{Controller:Move}=require('../static/js/den/pet-locomotion'),{Navigation}=require('../static/js/den/scene-navigation'),layout=require('../static/js/den/mistwood-layout'),catalog=require('../static/data/cat-world.json');
(async()=>{
 let now=0,state='idle',agent;const states=[];const model=new T.Group(),nav=new Navigation({...layout,bodyRadius:.619}),animate=k=>{state=k;states.push(k);},move=new Move({navigation:nav,model,animate,rest:()=>animate('idle')}),life=new Life(T,model,move,{animate});
 life.feedingFront=.423; // Geometry envelope supplied by the real-GLB feeding regression.
 const fetcher=async()=>({ok:true,json:async()=>({scope:'s',catalog,memory:[]})});agent=new Agent({model,locomotion:move,life,scope:'s',animate,fetcher,storage:null,now:()=>now});await agent.ready;
 const frame=()=>{now+=1000/60;agent.step(1/60,false);move.update(1/60,life.step(1/60,false));assert(nav.isWalkable(model.position),'no walls or water');};
 agent.hunger=.9;await agent.plan();assert.equal(agent.goal.action,'eat');
 for(let i=0;i<6500&&agent.goal;i++)frame();assert.equal(agent.goal,null);assert(agent.hunger<.35);assert.equal(agent.memory.food.visits,1);assert(states.includes('sniff'),'sniff before meal');assert(states.indexOf('sniff')<states.indexOf('eat'));assert.equal(life.last,'mouthClean','meal has a cleaning release');assert(Math.abs(model.rotation.y)<.05,'aligned to bowl');
 assert.equal(agent.care(catalog),null,'meal cooldown');now+=120001;agent.energy=.18;await agent.plan();assert.equal(agent.goal.action,'sleep');
 let slept=false;for(let i=0;i<7000&&agent.goal;i++){frame();if(state==='sleep')slept=true;}assert(slept);assert(agent.energy>.7);assert.equal(agent.memory.home.visits,1);assert(states.includes('standUp'),'rise before stretching');assert.equal(life.last,'stretch','wake stretches before next walk');assert(Math.hypot(model.position.x+3,model.position.z-4.62)<.2);
 now+=120001;agent.requestCare('sleep');await new Promise(r=>setImmediate(r));for(let i=0;i<600&&state!=='sleep';i++)frame();assert.equal(state,'sleep');agent.step(.02,true);assert.equal(agent.goal,null);assert.equal(state,'idle','interaction wakes cat');
 agent.dispose();console.log('PASS care: eat alignment + satiety, cooldown, navigate through open doorway, sleep + energy recovery, interrupt wake');
})().catch(e=>{console.error(e);process.exitCode=1});
