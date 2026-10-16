const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('templates/den.html','utf8'),source=html.slice(html.indexOf('        const ttsAudioCache = {}'),html.indexOf('        // 浏览器 SpeechSynthesis 降级'));
// Exercise the real account-scoped cross-tab bridge, without a server or audio provider.
const profileSource=fs.readFileSync('static/js/pet-profile.js','utf8');
function tab(scope){const events=[],stored=[],handlers={},window={COMPANION_SCOPE:scope,addEventListener:(n,f)=>handlers[n]=f};vm.runInNewContext(profileSource,{window,document:{dispatchEvent:e=>events.push(e)},CustomEvent:class{constructor(type,{detail}){this.type=type;this.detail=detail;}},localStorage:{setItem:(key,newValue)=>stored.push({key,newValue})},crypto:{randomUUID:()=>String(Math.random())}});return{window,events,stored,handlers};}
const first=tab('account-a'),second=tab('account-a'),other=tab('account-b');
first.window.PetVoiceChanges.publish({scope:'account-a',petId:1,activeId:'voice-b'});
assert.equal(first.events.length,1);second.handlers.storage(first.stored[0]);other.handlers.storage(first.stored[0]);
assert.equal(second.events[0].detail.activeId,'voice-b');assert.equal(second.stored.length,0,'storage updates must not broadcast loops');assert.equal(other.events.length,0,'other accounts ignore updates');
second.handlers.storage({key:first.stored[0].key,newValue:'broken JSON'});assert.equal(second.events.length,1);
const calls=[],played=[],revoked=[],listeners={};let seq=0;
const ctx=vm.createContext({console,speechSynthesis:{cancel(){}},currentPetId:1,petPlayer:null,ttsOn:true,voiceUI:null,window:{speechSynthesis:{cancel(){}}},document:{addEventListener:(n,f)=>listeners[n]=f},URL:{createObjectURL:()=>`blob:${++seq}`,revokeObjectURL:u=>revoked.push(u)},Audio:class{constructor(url){this.url=url;}play(){played.push(this.url);}pause(){}},fetch:(url,options)=>new Promise(resolve=>calls.push({url,options,resolve})),browserSpeak(){throw Error('unexpected fallback');}});
vm.runInContext(source,ctx);const run=s=>vm.runInContext(s,ctx),flush=()=>new Promise(r=>setImmediate(r));
(async()=>{
 run("glmTTS('同一句话')");calls[0].resolve({ok:true,blob:async()=>({})});await flush();run("glmTTS('同一句话')");assert.equal(calls.length,1);assert.equal(played.length,2);
 listeners['pet-voice-changed']({detail:{petId:1,activeId:'second'}});assert.equal(revoked.length,1);run("glmTTS('同一句话')");assert.equal(calls.length,2);
 listeners['pet-voice-changed']({detail:{petId:1,activeId:'third'}});calls[1].resolve({ok:true,blob:async()=>({})});await flush();assert.equal(played.length,2,'late old voice cannot play');assert.equal(run('Object.keys(ttsAudioCache).length'),0,'late old voice cannot repopulate cache');
 run("glmTTS('同一句话')");calls[2].resolve({ok:true,blob:async()=>({})});await flush();assert.equal(played.at(-1),'blob:2');
 listeners['pet-voice-changed']({detail:{petId:2,activeId:'other'}});run("glmTTS('同一句话')");assert.equal(calls.length,3,'other pet selection preserves cache');
 listeners['pet-voice-changed']({detail:{petId:1,activeId:null}});run("glmTTS('同一句话')");assert.equal(calls.length,4,'reset default also invalidates');
 const prefix='a'.repeat(50);run(`glmTTS(${JSON.stringify(prefix+'one')})`);calls[4].resolve({ok:true,blob:async()=>({})});await flush();run(`glmTTS(${JSON.stringify(prefix+'two')})`);assert.equal(calls.length,6,'complete text is used as cache key');
 console.log('PASS voice changes invalidate cached and in-flight speech; per-pet isolation, reset and full-text keys');
})().catch(e=>{console.error(e);process.exitCode=1});
