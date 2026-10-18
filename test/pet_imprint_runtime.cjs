const assert=require('node:assert/strict');
const {Controller}=require('../static/js/den/pet-imprint-runtime.js');
(async()=>{
 let pet=1,busy=false,hidden=false,now=1000000,played=[],cancel=0,called=0,resolve;
 let data={scope:'a',petId:1,enabled:true,policy:{responses:{greeting:{action:'sit',evidence:{quote:'它会坐着等我'}}},calls:{}}};
 const a={scope:'a',pet:()=>pet,available:()=>!busy,hidden:()=>hidden,supports:k=>['come','sit'].includes(k),status:()=>{},now:()=>now,cancel:()=>cancel++,play:async p=>{played.push(p);return true;},call:async()=>called++,fetcher:async()=>({ok:true,json:async()=>data})};
 const c=new Controller(a);
 assert.equal(await c.trigger('greeting',true),true);assert.deepEqual(played,[['come','sit']]);
 await c.trigger('greeting');assert.equal(played.length,1);
 data={...data,enabled:false};await c.trigger('greeting',true);assert.equal(played.length,1);
 data={...data,enabled:true,scope:'b'};await c.trigger('greeting',true);assert.equal(played.length,1);
 data={...data,scope:'a'};busy=true;c.queue('greeting');c.tick();now+=9000;busy=false;c.tick();assert.equal(c.pending,null);
 c.fetcher=async()=>new Promise(r=>resolve=r);const pending=c.trigger('greeting',true);await Promise.resolve();c.invalidate();resolve({ok:true,json:async()=>data});await pending;assert.equal(played.length,1,'late response after manual input cannot act');
 c.fetcher=a.fetcher;data.policy.responses.greeting.action='unknown';await c.trigger('greeting',true);assert.equal(played.length,1,'unsupported motion must not be substituted');
 data.policy.responses={};data.policy.calls={greeting:{id:'confirmed'}};await c.trigger('greeting',true);assert.equal(called,1);
 hidden=true;await c.trigger('greeting',true);assert.equal(called,1);c.dispose();assert(cancel>0);
 console.log('PASS confirmed mappings, scope, pause, cooldown, expired intent, stale/manual cancellation, missing motion and original-call-only response');
})().catch(e=>{console.error(e);process.exitCode=1;});
