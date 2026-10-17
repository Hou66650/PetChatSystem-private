const assert=require('node:assert/strict');
const {ModelCache,Loader,validGlb}=require('../static/js/den/selected-assets.js');
const url='/static/models/cat/cat.glb?v=1';
function glb(value=1){const b=new ArrayBuffer(24),d=new DataView(b);d.setUint32(0,0x46546c67,true);d.setUint32(4,2,true);d.setUint32(8,24,true);d.setUint32(20,value,true);return b;}
class MemoryStore {
 constructor(){this.rows=new Map();this.puts=0;}
 async get(k){return this.rows.get(k);}
 async remove(k){this.rows.delete(k);}
 async touch(){}
 async put(e,budget){this.puts++;this.rows.set(e.key,e);}
}
const response=(status=200,buffer=glb(),etag='"one"')=>({ok:status===200,status,headers:{get:k=>k==='ETag'?etag:null},arrayBuffer:async()=>buffer});
(async()=>{
 const store=new MemoryStore(),cache=new ModelCache({store,base:'http://tablet.test/den'});
 assert.equal(cache.key(url),cache.key(url.replace('v=1','v=2')),'app release must not invalidate unchanged model');
 for(const p of ['https://other.test'+url,'/uploads/private.glb','/api/model.glb',url+'&user=1'])assert.equal(cache.key(p),null);
 let calls=[],version=1;
 const fetcher=async(u,o)=>{calls.push({u,...o});return response(o.headers?.['If-None-Match']==='"'+version+'"'?304:200,glb(version),'"'+version+'"');};
 const parser={parse(b,p,done){done({scene:{traverse(){}},value:new DataView(b).getUint32(20,true)});}};
 const loader=new Loader(parser,fetcher,cache);
 assert.equal((await loader.glb(url,loader.begin())).value,1);assert.equal(store.puts,1);
 const reloaded=new Loader(parser,fetcher,new ModelCache({store,base:'http://tablet.test/den'}));
 assert.equal((await reloaded.glb(url.replace('v=1','v=2'),reloaded.begin())).value,1);
 assert.equal(calls.at(-1).headers['If-None-Match'],'"1"');assert.equal(store.puts,1);
 version=2;assert.equal((await reloaded.glb(url,reloaded.begin())).value,2);assert.equal(store.puts,2);
 const offline=new Loader(parser,async()=>{throw new TypeError('offline');},cache);
 assert.equal((await offline.glb(url,offline.begin())).value,2,'offline uses complete saved model');
 const controller=new AbortController();controller.abort();
 await assert.rejects(cache.read(url,{signal:controller.signal,fetcher}),{name:'AbortError'});
 const cancelled=new Loader(parser,async(u,o)=>{cancelled.begin();throw Object.assign(Error(),{name:'AbortError'});},cache);
 await assert.rejects(cancelled.glb(url,cancelled.begin()),{name:'AbortError'},'cancel does not use saved model');
 store.rows.get(cache.key(url)).buffer=new ArrayBuffer(24);
 assert.equal((await loader.glb(url,loader.begin())).value,2,'corrupt header is replaced');
 assert.equal(calls.at(-1).headers['If-None-Match'],undefined);
 // Valid header but invalid payload must evict and retry the network once.
 store.rows.get(cache.key(url)).buffer=glb(99);
 const validating=new Loader({parse(b,p,ok,fail){new DataView(b).getUint32(20,true)===99?fail(Error('bad payload')):parser.parse(b,p,ok);}},fetcher,cache);
 assert.equal((await validating.glb(url,validating.begin())).value,2);
 await assert.rejects(cache.read(url,{fetcher:async()=>response(404)}),/404/);assert.equal(store.rows.size,0);
 const denied={get:async()=>{throw Error('storage denied')},put:async()=>{throw Error('quota')},remove:async()=>{}};
 const fallback=new Loader(parser,fetcher,new ModelCache({store:denied,base:cache.base}));
 assert.equal((await fallback.glb(url,fallback.begin())).value,2,'storage failure cannot block model');
 const limited=new ModelCache({store,base:cache.base,maxEntry:20});
 assert.equal((await limited.read(url,{fetcher})).entry,null,'oversized model loads without persistence');
 const bad=new Loader({parse(b,p,ok,fail){fail(Error('invalid gltf'));}},fetcher,cache);
 await assert.rejects(bad.glb(url,bad.begin()),/invalid gltf/);assert.equal(store.rows.size,0,'parse failure never persists bytes');
 assert(!validGlb(new ArrayBuffer(8)));
 let budgets=[];const quotaCache=new ModelCache({store:{put:async(e,b)=>{budgets.push(b);if(budgets.length===1)throw Object.assign(Error(),{name:'QuotaExceededError'});}},base:cache.base});
 await quotaCache.save({buffer:glb()});assert.equal(budgets.length,2);assert.equal(budgets[1],24);
 console.log('PASS model cache: release-independent identity, revalidation/update, reload, offline, cancellation, corruption retry, privacy, quota and parse failure');
})().catch(e=>{console.error(e);process.exitCode=1;});
