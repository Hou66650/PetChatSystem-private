const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
(async()=>{
 const calls=[],catalog=require('../static/data/cat-world.json');
 const context=vm.createContext({console,setTimeout,clearTimeout,AbortController,crypto:globalThis.crypto,calls,catalog});
 // Browser host functions may reject a custom controller as their receiver.
 vm.runInContext(`window=globalThis;fetch=function(url,options){'use strict';if(this!==undefined&&this!==globalThis)throw TypeError('Illegal invocation');calls.push(url);return Promise.resolve({ok:true,json:async()=>({scope:'s',catalog,memory:[]})});};`,context);
 vm.runInContext(fs.readFileSync('static/js/den/cat-agent.js','utf8'),context);
 await vm.runInContext(`(async()=>{const agent=new CatAgent.Controller({model:{position:{x:0,z:0}},locomotion:{path:[],enabled:true},life:{},scope:'s',animate(){},telemetry:true,storage:null});await agent.ready;globalThis.agent=agent;})()`,context);
 await new Promise(r=>setImmediate(r));assert(calls.includes('/api/cat-agent'));assert(calls.includes('/api/cat-agent/telemetry'));assert.equal(context.agent.catalog.length,14);
 context.agent.fetcher=()=>{throw Error('synchronous transport failure');};context.agent.status('still alive');await new Promise(r=>setImmediate(r));assert.equal(context.agent.sending,false,'telemetry synchronous failures contained');
 console.log('PASS browser-like fetch receiver: initialization, online telemetry, synchronous failure isolation');
})().catch(e=>{console.error(e);process.exitCode=1});
