const assert=require('node:assert/strict'),{Controller}=require('../static/js/den/cat-agent'),catalog=require('../static/data/cat-world.json');
(async()=>{
 let time=0,calls=0;const model={position:{x:0,z:0}},move={enabled:true,path:[],owner:'idle',navigation:{clearance:.7,route:()=>[{}]},goTo(){this.path=[{}];this.owner='command';return true;},interrupt(){this.path=[];this.owner='interaction';}},life={cancel(){}};
 const fetcher=async(url)=>{if(url.endsWith('decide'))calls++;return {ok:true,json:async()=>url.endsWith('decide')?{target:'bridge',action:'observe',source:'model',retryAfter:8}:{scope:'s',catalog,memory:[]}};};
 const a=new Controller({model,locomotion:move,life,scope:'s',animate(){},fetcher,storage:null,now:()=>time});await a.ready;time=4000;a.step(.02,false);await new Promise(r=>setImmediate(r));assert.equal(calls,1);
 time=30000;a.step(.02,false);assert.equal(calls,1,'active route is stable even beyond minimum interval');
 a.finish('completed');time=30500;a.step(.02,false);await new Promise(r=>setImmediate(r));assert.equal(calls,2,'completion triggers next decision without 35/90s pause');
 a.interrupt();time=32000;a.step(.02,false);assert.equal(calls,2,'minimum interval respected after interruption');
 time=38500;a.step(.02,true);a.step(.02,false);time=39000;a.step(.02,false);await new Promise(r=>setImmediate(r));assert.equal(calls,3,'interaction release schedules decision');
 a.interrupt();a.fetcher=async()=>{throw Error('offline');};time=50000;await a.plan();assert.equal(a.networkAfter,66000);a.interrupt();time=67000;await a.plan();assert.equal(a.networkAfter,99000);a.dispose();
 console.log('PASS event-driven scheduling: 8s minimum, stable running task, completion/resume triggers, exponential network backoff');
})().catch(e=>{console.error(e);process.exitCode=1});
