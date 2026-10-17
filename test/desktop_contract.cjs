const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {TripContext}=require('../desktop/trip-context'),contract=require('../desktop/vendor/openpets/events.cjs');
const {stripTypeScriptTypes}=require('node:module');
const original={};
vm.runInNewContext(stripTypeScriptTypes(fs.readFileSync('desktop/vendor/openpets/agent-events.ts','utf8')).replaceAll('export ','')+';globalThis.validate=validateHookSpeech;globalThis.pick=pickHookSpeech;',original);
for(const input of ['正在听你说话','正常状态','', 'a'.repeat(141),'line\nbreak','const x = 1','https://example.com','C:\\private\\file','token=hidden','<img src=x>', 'hello;']){
 let a,b;try{a=contract.validateHookSpeech(input);}catch(e){a=e.message;}try{b=original.validate(input);}catch(e){b=e.message;}assert.equal(a,b,input);
}
for(const category of Object.keys(contract.hookSpeechPools))for(const value of [0,.5,1,-1,NaN])assert.equal(contract.pickHookSpeech(category,()=>value),original.pick(category,()=>value));
const originalReactions=JSON.parse(fs.readFileSync('desktop/vendor/openpets/protocol.ts','utf8').match(/allowedReactions = (\[[\s\S]*?\]) as const/)[1].replace(/,\s*\]/,']'));
assert.deepEqual(contract.allowedReactions,originalReactions);for(const r of originalReactions)assert.equal(contract.validateReaction(r),r);assert.throws(()=>contract.validateReaction('fake-success'));
const a=new TripContext('https://example.com',{trip:'a'},1),b=new TripContext('https://example.com',{trip:'b'},2);
const first=a.signal(1000),second=b.signal(1000);a.events.push('a');a.chatBusy=true;a.every(()=>{},1000);a.dispose();
assert(first.signal.aborted);assert(!second.signal.aborted);assert.equal(a.timers.size,0);assert.equal(a.requests.size,0);assert.equal(b.chatBusy,false);assert.deepEqual(b.events,[]);b.dispose();
const THREE=require('../static/js/vendor/three.min.js'),context={};vm.runInNewContext(fs.readFileSync('static/js/den/portal-pets.js','utf8'),context);
function pet(names){const scene=new THREE.Group();scene.add(new THREE.Mesh(new THREE.BoxGeometry(1,1,1)));return new context.PortalPets.Pet(THREE,{scene,animations:names.map(name=>new THREE.AnimationClip(name,1,[]))},{height:1,strictActions:true});}
const noIdle=pet(['danger-first']);noIdle.play('walk');assert.equal(noIdle.active,null);assert.equal(noIdle.missingAction,true);
const fallback=pet(['danger-first','Idle','motion_walk']);fallback.play('happy');assert.equal(fallback.active.getClip().name,'Idle');assert(fallback.missingAction);fallback.play('turnLeft');assert.equal(fallback.active.getClip().name,'Idle');fallback.play('walk');assert.equal(fallback.active.getClip().name,'motion_walk');assert(!fallback.missingAction);
console.log('PASS upstream speech/enum parity, isolated cancellation, strict missing-action idle/static fallback');
