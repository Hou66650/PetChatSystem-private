const assert=require('node:assert/strict'),{EventEmitter}=require('node:events');
const {DeliveryDispatcher}=require('../desktop/notifications');
class FakeNotification extends EventEmitter{
 static supported=true;static behavior='show';static count=0;static last;
 static isSupported(){return this.supported;}
 constructor(){super();FakeNotification.last=this;}
 show(){FakeNotification.count++;if(FakeNotification.behavior==='show')this.emit('show');if(FakeNotification.behavior==='throw')throw Error('uncertain');}
 close(){}
}
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
(async()=>{
 for(const mode of ['show','silent','throw','unsupported','dead']){
  const acks=[];FakeNotification.behavior=mode;FakeNotification.supported=mode!=='unsupported';const before=FakeNotification.count;
  const d=new DeliveryDispatcher({Notification:FakeNotification,sendAck:async a=>acks.push(a),alive:()=>mode!=='dead',timeout:5});
  d.deliver({id:mode,title:'test',token:'secret'});d.deliver({id:mode,title:'test',token:'secret'});await delay(10);
  assert.equal(FakeNotification.count-before,['unsupported','dead'].includes(mode)?0:1);
  assert.equal(acks[0].state,{show:'delivered',silent:'unknown',throw:'unknown',unsupported:'failed',dead:'suppressed'}[mode]);
  if(mode==='silent'){d.dispose();FakeNotification.last.emit('show');assert.equal(acks.at(-1).state,'delivered','late receipt remains factual after recall');}
  d.dispose();assert.equal(acks.filter(a=>a.state==='suppressed').length,mode==='dead'?1:0);
 }
 const acks=[];FakeNotification.behavior='silent';FakeNotification.supported=true;
 const d=new DeliveryDispatcher({Notification:FakeNotification,sendAck:async a=>acks.push(a),alive:()=>true,timeout:1000});
 d.deliver({id:'recall',title:'test',token:'secret'});d.dispose();assert.equal(acks[0].state,'unknown');FakeNotification.last.emit('show');assert.equal(acks.at(-1).state,'delivered');
 console.log('PASS notification once-only invocation, unsupported, uncertain throw, timeout, recall and late OS receipt');
})().catch(e=>{console.error(e);process.exitCode=1});
