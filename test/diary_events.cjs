const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
(async()=>{
  let now=100000,calls=[],finish;
  const window={COMPANION_SCOPE:'test-owner'};
  vm.runInNewContext(fs.readFileSync('static/js/den/diary-events.js','utf8'),{
    window,document:{dispatchEvent(){}},CustomEvent:class{},Date:{now:()=>now},fetch:(url,options)=>{
      calls.push({url,options});return new Promise(resolve=>{finish=resolve});
    }
  });
  const record=window.PetDiary.record,flush=()=>new Promise(resolve=>setImmediate(resolve));
  record(3,'chat');assert.equal(calls.length,0,'server chat must not be reported by client');
  record(3,'pet');record(3,'pet');assert.equal(calls.length,1,'single in-flight event');
  assert.equal(calls[0].options.headers['X-Profile-Scope'],'test-owner');
  assert.deepEqual(JSON.parse(calls[0].options.body),{petId:3,kind:'pet'});
  finish({ok:true});await flush();record(3,'pet');assert.equal(calls.length,1,'success is throttled');
  now+=60001;record(3,'pet');assert.equal(calls.length,2);finish({ok:false});await flush();
  record(3,'pet');assert.equal(calls.length,3,'failure may retry');finish({ok:true});await flush();
  record(1,'pet');assert.equal(calls.length,4,'pet scopes are independent');finish({ok:true});await flush();
  console.log('Diary event dedupe, throttle, failure retry and pet isolation passed');
})().catch(error=>{console.error(error);process.exitCode=1});
