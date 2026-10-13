const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const read=n=>fs.readFileSync(require('node:path').join(__dirname,'../static/js/realtime',n+'.js'),'utf8');
const base=()=>({window:{},console,performance,setTimeout,clearTimeout,setInterval,clearInterval,
  atob:s=>Buffer.from(s,'base64').toString('binary'),btoa:s=>Buffer.from(s,'binary').toString('base64')});
let passed=0;
async function test(name,fn){await fn();passed++;console.log('PASS '+name);}
function playerSetup(mode='ok'){
 const contexts=[];
 class AC{
  constructor(){this.state='suspended';this.currentTime=0;this.nodes=[];this.calls=0;contexts.push(this);}
  createGain(){return {gain:{value:1},connect(){}};}
  resume(){this.calls++;if(mode==='denied')return Promise.reject(Object.assign(Error(),{name:'NotAllowedError'}));
   if(mode==='pending'&&this.calls===1)return new Promise(r=>this.release=r);
   this.state='running';return Promise.resolve();}
  close(){this.state='closed';return Promise.resolve();}
  createBuffer(c,n,rate){return {duration:n/rate,copyToChannel:f=>this.samples=f};}
  createBufferSource(){const n={connect(){},start(t){this.when=t;},stop(){this.stopped=true;}};this.nodes.push(n);return n;}
 }
 const ctx=vm.createContext({...base(),window:{AudioContext:AC}});vm.runInContext(read('pcm-player'),ctx);
 return {p:new ctx.window.PCMPlayer(),ctx,contexts};
}
(async()=>{
 await test('playback is unlocked before requesting microphone permission',async()=>{
  const order=[];let release;
  const ctx=vm.createContext({...base(),PCMPlayer:class{unlock(){order.push('unlock');}destroy(){order.push('destroy');}},
   navigator:{mediaDevices:{getUserMedia(){order.push('permission');return new Promise(r=>release=r);}}}});
  vm.runInContext(read('realtime-controller'),ctx);const c=new ctx.window.RealtimeController({petId:1});
  const pending=c.start();assert.deepEqual(order,['unlock','permission']);c.stop();let stopped=false;
  release({getTracks:()=>[{stop(){stopped=true;}}]});await pending;assert.ok(stopped);assert.ok(order.includes('destroy'));
 });
 await test('PCM samples decode correctly and chunks schedule without overlap',async()=>{
  const {p,contexts}=playerSetup();await p.unlock();const b=Buffer.alloc(480);b.writeInt16LE(-32768,0);b.writeInt16LE(16384,2);
  p.append(b.toString('base64'));p.append(b.toString('base64'));
  const c=contexts[0];assert.equal(c.samples[0],-1);assert.equal(c.samples[1],.5);
  assert.ok(c.nodes[1].when>=c.nodes[0].when+.01);assert.equal(p.receivedChunks,2);
  p.interrupt();assert.ok(c.nodes.every(n=>n.stopped));assert.equal(p.playing,false);p.destroy();
 });
 await test('denied resume is handled and its state stays distinguishable from playing',async()=>{
  const {p}=playerSetup('denied');assert.equal(await p.unlock(),false);assert.equal(p.outputState,'suspended');
  assert.equal(p.lastError,'NotAllowedError');p.destroy();
 });
 await test('sound-test click retries a pending unlock and uses the same output without counting as received voice',async()=>{
  const {p,contexts}=playerSetup('pending');const old=p.unlock();p.testTone();assert.equal(contexts[0].calls,2);
  assert.equal(p.outputState,'running');assert.ok(contexts[0].samples.some(n=>Math.abs(n)>.05));assert.equal(p.receivedChunks,0);
  contexts[0].release();await old;p.destroy();
 });
 await test('destroy while unlock is pending cannot resurrect the audio context',async()=>{
  const {p,contexts}=playerSetup('pending');const pending=p.unlock();p.destroy();contexts[0].release();
  assert.equal(await pending,false);assert.equal(p.outputState,'uninitialized');
 });
 await test('microphone rejection closes the pre-unlocked player',async()=>{
  let closed=0;const ctx=vm.createContext({...base(),PCMPlayer:class{unlock(){}destroy(){closed++;}},
   navigator:{mediaDevices:{getUserMedia:async()=>{throw {name:'NotAllowedError'};}}}});
  vm.runInContext(read('realtime-controller'),ctx);const c=new ctx.window.RealtimeController({petId:1});await c.start();
  assert.equal(closed,1);assert.equal(c.state,'ERROR');assert.equal(c._player,null);
 });
 await test('missing audio is reported only for the current non-cancelled response',()=>{
  const ctx=vm.createContext(base());vm.runInContext(read('realtime-controller'),ctx);const warnings=[];
  const c=new ctx.window.RealtimeController({petId:1,onWarning:w=>warnings.push(w.code)});
  c._onClientEvent('response.created',{response:{id:'new'}});
  c._onClientEvent('response.done',{response:{id:'old'}});assert.equal(warnings.length,0);
  c._onClientEvent('response.done',{response:{id:'new',status:'completed'}});assert.deepEqual(warnings,['reply_audio_missing']);
  c._onClientEvent('response.created',{response:{id:'next'}});c._onClientEvent('response.audio.delta',{response_id:'next',delta:'AAA='});
  c._onClientEvent('response.done',{response:{id:'next'}});assert.equal(warnings.length,1);
 });
 await test('audio decoding failure is surfaced without breaking websocket event handling',()=>{
  const ctx=vm.createContext(base());vm.runInContext(read('realtime-client'),ctx);const events=[];
  const c=new ctx.window.RealtimeClient({petId:1,player:{append(){throw Error('bad audio');}},onEvent:t=>events.push(t)});
  c._dispatch({type:'response.audio.delta',delta:'bad'});assert.ok(events.includes('playback.error'));
 });
 console.log(JSON.stringify({passed,failed:0}));
})().catch(e=>{console.error(e);process.exitCode=1;});
