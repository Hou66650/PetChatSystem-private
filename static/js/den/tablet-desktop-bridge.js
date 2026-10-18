/* The app polls this mailbox only in the configured top-level den page. */
(function(root){
 let enabled=false,pending=null,serial=0;
 function request(op,code=''){
  if(!enabled)return Promise.reject(Error('当前客户端尚未启用平板桌宠'));
  if(pending)return Promise.reject(Error('正在连接平板桌宠，请稍候'));
  return new Promise((resolve,reject)=>{const id=++serial;const timer=setTimeout(()=>{if(pending?.id===id){pending=null;reject(Error('平板桌宠没有响应，宠物仍留在小窝'));}},15000);pending={id,op,code,resolve,reject,timer};});
 }
 root.PaitTabletDesktop={get available(){return enabled;},prepare:()=>request('prepare'),start:code=>request('start',code),cancel:()=>request('cancel'),
  exchange(reply){enabled=true;if(pending&&reply?.id===pending.id){const p=pending;pending=null;clearTimeout(p.timer);reply.ok?p.resolve(reply):p.reject(Error(reply.message||'平板桌宠暂不可用'));}return JSON.stringify(pending?{id:pending.id,op:pending.op,code:pending.code}:null);}
 };
})(globalThis);
