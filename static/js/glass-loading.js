/* Shared, honest loading feedback. No simulated percentages and no response copies. */
(()=>{'use strict';
 if(window.PaitLoading)return;
 const tasks=new Map(),named=new Map();const dialogOrder=new WeakMap();let dialogSeq=0,seq=0,host,timer;
 const clamp=x=>Math.max(0,Math.min(1,x));
 function mount(){if(!document.body)return;const dialogs=[...document.querySelectorAll('dialog[open]:not([data-loading-overlay="outside"])')].sort((a,b)=>(dialogOrder.get(a)||0)-(dialogOrder.get(b)||0));const parent=dialogs.at(-1)||document.fullscreenElement||document.body;if(!host){host=document.createElement('section');host.className='pait-glass-loading';host.setAttribute('aria-label','加载进度');host.setAttribute('aria-live','polite');host.hidden=true;}if(host.parentNode!==parent){if(parent.tagName==='DIALOG')parent.prepend(host);else parent.append(host);}host.classList.toggle('in-dialog',parent.tagName==='DIALOG');}
 let updateTimer;
 function scheduleRender(){if(!updateTimer)updateTimer=setTimeout(()=>{updateTimer=null;render();},100);}
 function render(){
  clearTimeout(timer);mount();if(!host)return;
  const now=Date.now(),visible=[...tasks.values()].filter(t=>now-t.started>=t.delay),shown=visible.slice(-3);
  host.hidden=!visible.length;
  for(const node of [...host.querySelectorAll('[data-loading-id]')])if(!shown.some(t=>String(t.id)===node.dataset.loadingId))node.remove();
  for(const t of shown){
   let row=host.querySelector('[data-loading-id="'+t.id+'"]');
   if(!row){row=document.createElement('div');row.dataset.loadingId=t.id;row.innerHTML='<div class="pait-glass-heading"><span></span><small></small></div><div class="pait-glass-track" role="progressbar" aria-valuemin="0" aria-valuemax="100"><i></i></div>';host.append(row);}
   row.className='pait-glass-task '+t.state;
   row.querySelector('span').textContent=t.label;
   row.querySelector('small').textContent=t.progress===null?'':Math.round(t.progress*100)+'%';
   const track=row.querySelector('.pait-glass-track'),fill=track.firstElementChild;
   track.setAttribute('aria-label',t.label);track.classList.toggle('indeterminate',t.progress===null);
   if(t.progress===null){track.removeAttribute('aria-valuenow');track.setAttribute('aria-valuetext',t.state==='failed'?'未完成':'正在处理，进度暂不可计算');fill.style.removeProperty('width');}
   else{track.removeAttribute('aria-valuetext');track.setAttribute('aria-valuenow',String(Math.round(t.progress*100)));fill.style.width=(t.progress*100)+'%';}
  }
  let more=host.querySelector('.pait-glass-more');
  if(visible.length>3){if(!more){more=document.createElement('small');more.className='pait-glass-more';}more.textContent='另有 '+(visible.length-3)+' 项处理中';host.append(more);}else more?.remove();
  const pending=[...tasks.values()].filter(t=>now-t.started<t.delay);
  if(pending.length)timer=setTimeout(render,Math.min(...pending.map(t=>t.delay-(now-t.started)))+5);
 }
 function start(label,options={}){
  const id=++seq,entry={id,label,started:Date.now(),delay:options.delay??180,progress:null,state:'working',closed:false};tasks.set(id,entry);render();
  const remove=()=>{tasks.delete(id);render();};
  const finish=(state,message)=>{if(entry.closed)return;entry.closed=true;entry.state=state;if(message)entry.label=message;if(state==='done')entry.progress=1;else entry.progress=null;clearTimeout(entry.deadline);if(Date.now()-entry.started<entry.delay&&state!=='failed'){remove();return;}entry.delay=0;render();setTimeout(remove,state==='failed'?4500:400);};
  const task={update(text,progress=null){if(entry.closed)return;entry.label=text||entry.label;entry.progress=typeof progress==='number'&&Number.isFinite(progress)?clamp(progress):null;scheduleRender();},done:()=>finish('done'),fail:(text)=>finish('failed',text||entry.label+' · 未完成，请重试'),cancel(){if(entry.closed)return;entry.closed=true;clearTimeout(entry.deadline);remove();}};
  entry.deadline=setTimeout(()=>task.fail(entry.label+' · 等待较久，请查看页面提示'),options.timeout??300000);
  return task;
 }
 async function run(label,fn,options){const task=start(label,options);try{const value=await fn(task);task.done();return value;}catch(e){if(e?.name==='AbortError')task.cancel();else task.fail();throw e;}}
 function sync(key,active,label,failed=false){let task=named.get(key);if(active){if(!task){task=start(label,{delay:180,timeout:900000});named.set(key,task);}else task.update(label);}else if(task){if(failed)task.fail(label);else task.done();named.delete(key);}}
 const silent=/^\/api\/(?:cat-agent\/(?:telemetry|decide|report|relationship-event|monitor|relationship)$|voiceprint\/identify$)/;
 function classify(input,init={}){let url;try{url=new URL(typeof input==='string'||input instanceof URL?input:input.url,location.href);}catch{return null;}if(!['http:','https:','file:'].includes(url.protocol))return null;
  const path=url.pathname,method=(init.method||input?.method||'GET').toUpperCase();
  if(init.paitQuiet||silent.test(path)||(path==='/api/portals'&&url.searchParams.get('brief'))||/visitors|heartbeat|telemetry/.test(path))return null;
  if(method==='GET'&&['/api/pet-studio','/api/cat-agent/story-art'].includes(path))return null;
  if(/^\/api\/(?:supplies\/(?:claim|complete|consume)|companion\/voice-round)$/.test(path))return null;
  if(path.includes('/story-art')||/^\/api\/portals\/(sample|plan)$/.test(path))return null; // The outer AI job owns the polling interval.
  if(/\.(glb|gltf)(?:$)/i.test(path)||/\/assets\/(model|adapted)$/.test(path))return '正在下载三维模型';
  if(/mediapipe|\.wasm$|\.task$/.test(path))return '正在准备识别资源';
  if(/\.(webp|png|jpg|jpeg)$/.test(path))return '正在加载画面素材';
  if(/\.(wav|mp3|ogg)$/.test(path))return '正在准备声音';
  if(init.body instanceof FormData)return '正在上传文件';
  if(/get_gpt_response|chat|message/.test(path))return '正在等待宠物回应';
  if(/realtime/.test(path))return '正在连接语音';
  if(/voiceprint/.test(path))return '正在处理声音档案';
  if(path.startsWith('/api/'))return method==='GET'?'正在读取内容':'正在处理你的操作';
  if(url.origin===location.origin&&method!=='GET')return '正在提交';
  return null;
 }
 function fail(task,e){if(e?.name==='AbortError')task.cancel();else task.fail();}
 if(window.fetch){const original=window.fetch.bind(window);window.fetch=async function(input,init={}){
  const label=classify(input,init);if(!label)return original(input,init);const owned=!!init.paitTask,task=init.paitTask||start(label);const complete=()=>{if(!owned)task.done();};let idle;
  try{const response=await original(input,init);if(!response.ok){task.fail(label+' · 未完成，请查看页面提示');return response;}
   // Keep the real Response: URL, headers, status, identity, clone and streaming semantics survive.
   idle=setTimeout(complete,1500);const consume=()=>clearTimeout(idle);
   for(const name of ['json','text','blob','arrayBuffer','formData']){const method=response[name]?.bind(response);if(method)Object.defineProperty(response,name,{configurable:true,value:async(...args)=>{consume();try{const value=await method(...args);complete();return value;}catch(e){fail(task,e);throw e;}}});}
   const body=response.body;if(body){const originalReader=body.getReader.bind(body);Object.defineProperty(body,'getReader',{configurable:true,value:(...args)=>{consume();const reader=originalReader(...args);let loaded=0;const total=!response.headers.get('Content-Encoding')?Number(response.headers.get('Content-Length')):0;return new Proxy(reader,{get(target,key){if(key==='read')return async(...a)=>{try{const result=await target.read(...a);if(result.done)complete();else{loaded+=result.value?.byteLength||0;task.update(label,total>0&&loaded<=total?loaded/total:null);}return result;}catch(e){fail(task,e);throw e;}};if(key==='cancel')return (...a)=>{task.cancel();return target.cancel(...a);};const v=Reflect.get(target,key,target);return typeof v==='function'?v.bind(target):v;}});}});}
   return response;
  }catch(e){clearTimeout(idle);fail(task,e);throw e;}
 };}
 if(window.XMLHttpRequest){const proto=XMLHttpRequest.prototype,open=proto.open,send=proto.send;proto.open=function(method,url,...rest){this.__paitRequest={method,url};return open.call(this,method,url,...rest);};proto.send=function(body){const meta=this.__paitRequest,label=meta&&classify(meta.url,{method:meta.method,body});if(!label)return send.call(this,body);const task=start(label);this.addEventListener('progress',e=>task.update(label,e.lengthComputable?e.loaded/e.total:null));this.upload?.addEventListener('progress',e=>task.update('正在上传文件',e.lengthComputable?e.loaded/e.total:null));this.upload?.addEventListener('load',()=>task.update('上传完成，正在处理'));this.addEventListener('load',()=>this.status>=200&&this.status<400?task.done():task.fail());this.addEventListener('abort',()=>task.cancel());this.addEventListener('error',()=>task.fail());this.addEventListener('timeout',()=>task.fail());try{return send.call(this,body);}catch(e){fail(task,e);throw e;}};}
 async function buffer(response){
  if(!response.body?.getReader)return response.arrayBuffer();
  const reader=response.body.getReader(),chunks=[];let size=0;
  try{for(;;){const {done,value}=await reader.read();if(done)break;chunks.push(value);size+=value.byteLength;}}
  finally{reader.releaseLock();}
  const bytes=new Uint8Array(size);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.byteLength;}return bytes.buffer;
 }
 window.PaitLoading={start,run,sync,buffer,activeCount:()=>tasks.size};
 function watch(){render();new MutationObserver(mutations=>{for(const m of mutations)if(m.target.tagName==='DIALOG'&&m.target.open)dialogOrder.set(m.target,++dialogSeq);mount();}).observe(document.body,{subtree:true,attributes:true,attributeFilter:['open']});document.addEventListener('fullscreenchange',mount);}
 if(document.body)watch();else{
  // Show initial feedback as soon as the parser creates body, before slow scripts finish.
  let watching=false;const ready=()=>{if(watching||!document.body)return;watching=true;bootstrap.disconnect();watch();};
  const bootstrap=new MutationObserver(ready);bootstrap.observe(document.documentElement,{childList:true});
  document.addEventListener('DOMContentLoaded',ready,{once:true});
 }
 const page=start('正在打开页面',{timeout:60000});if(document.readyState==='complete')page.done();else window.addEventListener('load',()=>page.done(),{once:true});
 document.addEventListener('click',event=>{const link=event.target.closest?.('a[href]');if(!link||event.button!==0||event.ctrlKey||event.metaKey||event.shiftKey||event.altKey||link.target==='_blank'||link.hasAttribute('download'))return;let url;try{url=new URL(link.href);}catch{return;}if(url.origin!==location.origin||url.pathname===location.pathname&&url.search===location.search||/\/assets\/|\/references$/.test(url.pathname))return;queueMicrotask(()=>{if(!event.defaultPrevented)start('正在进入页面',{timeout:20000});});});
 document.addEventListener('submit',event=>queueMicrotask(()=>{if(!event.defaultPrevented&&event.target.method!=='dialog')start('正在提交，请稍候',{timeout:30000});}));
 window.addEventListener('pageshow',e=>{if(e.persisted){for(const t of tasks.values())clearTimeout(t.deadline);tasks.clear();named.clear();render();}});
})();
