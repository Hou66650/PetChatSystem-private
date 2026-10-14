const assert=require('node:assert/strict'),{Controller}=require('../static/js/den/cat-agent'),catalog=require('../static/data/cat-world.json');
(async()=>{
 let now=0;const sent=[],move={navigation:{route:()=>[],clearance:.7},path:[],enabled:true,owner:'idle',interrupt(){}};
 const agent=new Controller({model:{position:{x:0,z:0}},locomotion:move,life:{cancel(){}},scope:'s',animate(){},telemetry:true,storage:null,now:()=>now,fetcher:async(url,opt)=>{if(url.endsWith('telemetry'))sent.push(JSON.parse(opt.body));return {ok:true,json:async()=>({scope:'s',catalog,memory:[]})};}});
 await agent.ready;await new Promise(r=>setImmediate(r));assert.equal(sent.length,1);assert(sent[0].event);
 agent.step(.01,true);await new Promise(r=>setImmediate(r));assert.equal(sent.length,1,'no per-frame telemetry');
 now=2100;agent.step(.01,true);await new Promise(r=>setImmediate(r));assert.equal(sent.length,2);assert.equal(sent[1].event,false);
 agent.dispose();await new Promise(r=>setImmediate(r));assert.equal(sent.at(-1).snapshot.phase,'stopped');
 assert(sent.every(s=>s.stream===agent.stream));console.log('PASS monitor telemetry: bounded heartbeat, event snapshots, stable stream, stopped state');
})().catch(e=>{console.error(e);process.exitCode=1});
