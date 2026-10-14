const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const controls=new Map(),timers=new Map(),requests=[];let timerId=0,trackStops=0,lastNode;
const element=()=>({value:'',disabled:false,hidden:false,textContent:'',append(){},replaceChildren(){},addEventListener(){},showModal(){},querySelector(s){if(!controls.has(s))controls.set(s,element());return controls.get(s);}});
const panel=element(),state={scope:'current',storageHint:'游客会话',profiles:[{id:'one',name:'A'}],enabled:true,ready:true};
const context={window:{},document:{createElement:t=>t==='dialog'?panel:element(),body:{append(){}},dispatchEvent(){}},Event:class{},localStorage:{getItem(){return null;}},Uint8Array,AudioContext:class{
 constructor(){this.audioWorklet={addModule:async()=>{}};}async resume(){}async close(){}createMediaStreamSource(){return {connect(){}};}
},AudioWorkletNode:class{constructor(){this.port={};lastNode=this;}disconnect(){}},navigator:{mediaDevices:{getUserMedia:async()=>({getTracks:()=>[{stop(){trackStops++;}}]})}},
setInterval:()=>0,clearInterval(){},setTimeout:(fn,ms)=>{timers.set(++timerId,{fn,ms});return timerId;},clearTimeout:id=>timers.delete(id),
fetch:async(url,options)=>{requests.push({url,options});return {ok:true,json:async()=>url==='/api/voiceprint'?state:{kind:'familiar',name:'A'}};}};
vm.runInNewContext(fs.readFileSync('static/js/realtime/voiceprint-ui.js','utf8'),context);
(async()=>{
 await context.window.VoiceprintUI.open();assert.equal(controls.get('[data-scope]').textContent,'游客会话');
 await controls.get('[data-check]').onclick();assert.equal(controls.get('[data-check]').disabled,true);
 lastNode.port.onmessage({data:{type:'chunk',buffer:new Int16Array(96000).buffer}});
 const timer=[...timers.values()][0];assert.equal(timer.ms,6000);await timer.fn();
 const check=requests.find(r=>r.url==='/api/voiceprint/check');assert.ok(check);assert.equal(check.options.headers['X-Profile-Scope'],'current');
 assert.equal(check.options.body.byteLength,192000);assert.match(controls.get('[data-status]').textContent,/试认成功/);assert.equal(controls.get('[data-check]').disabled,false);assert.equal(trackStops,1);
 await controls.get('[data-check]').onclick();const stale=[...timers.values()][0];controls.get('[data-cancel]').onclick();await stale.fn();
 assert.equal(requests.filter(r=>r.url==='/api/voiceprint/check').length,1);assert.equal(trackStops,2);
 console.log('PASS trial recording, PCM upload, scope, result, device release and cancellation');
})().catch(e=>{console.error(e);process.exitCode=1;});
