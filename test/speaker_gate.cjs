const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {Gate}=require('../static/js/realtime/speaker-gate.js');
const tick=()=>new Promise(r=>setImmediate(r));
const pcm=n=>new Int16Array(1600).fill(n).buffer;
(async()=>{
 let starts=0,turns=[];
 const gate=new Gate({onStart:()=>starts++,onTurn:b=>turns.push(b),onError:e=>{throw e;}});
 for(let i=0;i<20;i++)gate.push(pcm(0));assert.equal(starts,0);
 gate.push(pcm(3000));for(let i=0;i<6;i++)gate.push(pcm(0));assert.equal(turns.length,0);
 gate.push(pcm(0));await tick();assert.equal(starts,1);assert.equal(turns.length,1);
 assert.ok(turns[0].byteLength<640000);
 gate.push(pcm(3000));for(let i=0;i<7;i++)gate.push(pcm(0));gate.close();await tick();assert.equal(turns.length,1);
 gate.reset();for(let i=0;i<150;i++)gate.push(pcm(3000));await tick();assert.equal(turns.length,2);assert.ok(turns[1].byteLength<=480000);
 const calls=[];let finishConnect;
 const ctx=vm.createContext({window:{},SpeakerGate:{Gate},performance,console,URLSearchParams,AbortController,setTimeout,clearTimeout,setInterval,clearInterval,
  fetch:async()=>({ok:true,json:async()=>({kind:'familiar',name:'A',instructions:'CURRENT_SPEAKER'})}),
  RealtimeClient:class{constructor(){this.metrics={};}connect(){calls.push(this._session.config.instructions);return new Promise(r=>finishConnect=r);}sendAudio(b){calls.push(b.byteLength);}close(){calls.push('close');}}
 });
 vm.runInContext(fs.readFileSync('static/js/realtime/realtime-controller.js','utf8'),ctx);
 const c=new ctx.window.RealtimeController({petId:1,synthetic:true});
 c._speakerCounter=0;c._speakerSource={profileScope:'scope',expiresAt:Date.now()/1000+600,config:{instructions:'OLD'}};
 const pending=c._speakerTurn(pcm(2000));await tick();assert.deepEqual(calls,['CURRENT_SPEAKER']);
 finishConnect();await pending;assert.equal(calls[1],3200);assert.equal(calls[2],32000);
 calls.length=0;const cancel=c._speakerTurn(pcm(2000));await tick();c.stop();finishConnect();await cancel;
 assert.ok(!calls.some(x=>typeof x==='number'),'stopped turn must never transmit audio');
 console.log('PASS silence, endpoint, bounded utterance, cancel, instructions-before-audio, stop during connection');
})().catch(e=>{console.error(e);process.exitCode=1;});
