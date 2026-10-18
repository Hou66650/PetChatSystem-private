'use strict';
// Main-process only. A receipt is evidence about one attempt, never user read status.
class DeliveryDispatcher{
 constructor({Notification,sendAck,alive,timeout=10000}){Object.assign(this,{Notification,sendAck,alive,timeout});this.attempts=new Map();}
 deliver(item){
  if(this.attempts.has(item.id))return;
  const attempt={item,called:false,settled:false,notification:null,timer:null};this.attempts.set(item.id,attempt);
  const report=(state,evidence)=>{void this.sendAck({deliveryId:item.id,token:item.token,state,evidence}).catch(()=>{});};
  attempt.report=report;
  if(!this.alive()){attempt.settled=true;report('suppressed','not-called');return;}
  if(!this.Notification.isSupported()){attempt.settled=true;report('failed','unsupported');return;}
  try{
   const notification=new this.Notification({title:'派特岛 · 到时间了',body:item.title,silent:false});attempt.notification=notification;
   notification.once('show',()=>{attempt.settled=true;clearTimeout(attempt.timer);report('delivered','os-show');});
   notification.once('failed',()=>{attempt.settled=true;clearTimeout(attempt.timer);report('unknown','unconfirmed');});
   if(!this.alive()){attempt.settled=true;report('suppressed','not-called');return;}
   // Set BEFORE invoking the OS API: a thrown call can still have side effects.
   attempt.called=true;notification.show();
   if(!attempt.settled)attempt.timer=setTimeout(()=>{attempt.settled=true;report('unknown','unconfirmed');},this.timeout);
  }catch(_){attempt.settled=true;report(attempt.called?'unknown':'suppressed',attempt.called?'unconfirmed':'not-called');}
 }
 dispose(){
  for(const a of this.attempts.values()){
   clearTimeout(a.timer);
   if(!a.settled){a.settled=true;a.report(a.called?'unknown':'suppressed',a.called?'unconfirmed':'not-called');}
   // Do not remove listeners: a late OS show receipt may refine unknown.
   try{a.notification?.close();}catch(_){}
  }
 }
}
module.exports={DeliveryDispatcher};
