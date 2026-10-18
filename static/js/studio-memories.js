/* One private profile, separate reference photos and memory media. */
(()=>{'use strict';
 const $=id=>document.getElementById(id),scope=window.PET_STUDIO_SCOPE;
 const params=new URLSearchParams(location.search);let task=null,state=null,epoch=0,working=false,studioBusy=false;
 let section=params.get('section')==='memories'?'memories':'model';
 const say=text=>{$('memory-status').textContent=text;};
 const endpoint=id=>'/api/pet-studio/'+encodeURIComponent(id);
 const elem=(tag,text,cls)=>{const n=document.createElement(tag);if(text)n.textContent=text;if(cls)n.className=cls;return n;};
 function button(text,fn){const b=elem('button',text);b.type='button';b.onclick=fn;return b;}
 function tabs(value){section=value;$('studio-appearance').hidden=value!=='model';$('studio-memories').hidden=value!=='memories';$('studio-tab-model').setAttribute('aria-pressed',String(value==='model'));$('studio-tab-memories').setAttribute('aria-pressed',String(value==='memories'));dispatchEvent(new Event('studio-tab-changed'));}
 $('studio-tab-model').onclick=()=>tabs('model');$('studio-tab-memories').onclick=()=>tabs('memories');tabs(section);
 const legacyPet=Number(params.get('petId')); // Only used to open pre-existing island records.
 function lock(on){working=on;document.querySelectorAll('#studio-memories button,#studio-memories input,#studio-memories select,#studio-memories textarea,.studio-choice,#studio-create button,#studio-delete').forEach(el=>{if(el.id!=='habit-stop')el.disabled=on||studioBusy;});}
 async function request(url,body){const form=body instanceof FormData;const r=await fetch(url,{paitQuiet:true,method:body===undefined?'GET':'POST',cache:'no-store',headers:body===undefined?{}:form?{'X-Profile-Scope':scope}:{'X-Profile-Scope':scope,'Content-Type':'application/json'},body:body===undefined?undefined:form?body:JSON.stringify(body)});const responseError=()=>Error(r.redirected||r.status===401?'登录状态已失效，请重新登录后重试':r.status===404||r.status===405?'当前服务尚未提供记忆素材接口，请更新并重启服务后刷新页面':r.status===413?'文件过大，请按页面标注的大小限制重新选择':'记忆服务暂时不可用，请稍后重试（HTTP '+r.status+'）');
  if(!r.headers.get('content-type')?.toLowerCase().includes('application/json'))throw responseError();
  let d;try{d=await r.json();}catch{throw responseError();}
  if(!d||typeof d!=='object'||Array.isArray(d))throw responseError();
  if(!r.ok)throw Error(typeof d.error==='string'?d.error:'操作未完成');if(d.scope!==scope)throw Error('账号已变化，请刷新页面');return d;}
 function changed(){if(window.BroadcastChannel){const ch=new BroadcastChannel('companion-memory:'+scope);ch.postMessage('changed');ch.close();}if($('studio-existing').open)loadExisting();}
 async function load(){if(!task)return;const id=task.id,token=epoch;try{const d=await request(endpoint(id)+'/memories');if(token===epoch){state=d;render();}}catch(e){if(token===epoch)say(e.message);}}
 function mediaURL(media,view){return endpoint(task.id)+'/memories/'+media.id+'/'+view;}
 function source(media,start){const d=elem('details'),s=elem('summary','对照原始素材'+(media.duration?' · '+start.toFixed(2)+' 秒':''));d.append(s);let loaded=false;d.ontoggle=()=>{if(!d.open||loaded)return;loaded=true;const item=elem(media.mime.startsWith('audio/')?'audio':media.duration?'video':'img');item.className='memory-source';item.src=mediaURL(media,'source');if(media.duration){item.controls=true;item.preload='metadata';item.onloadedmetadata=()=>{item.currentTime=start;};}else item.alt=media.name;d.append(item);};return d;}
 function render(){
  if(!state||!task)return;
  $('memory-binding').textContent='这些记忆属于「'+state.profile.name+'」。生成并启用它的专属形象后，记忆会随它一起生效。';
  $('memory-media').replaceChildren();
  for(const media of state.media){const box=elem('article',null,'memory-tile'),img=elem('img');img.src=mediaURL(media,'preview');img.alt=media.mime.startsWith('audio/')?'声音波形':media.duration?'视频预览':'回忆照片';img.loading='lazy';box.append(img,elem('strong',media.name));
   const names={ready:'待提取',analyzing:'正在分析',done:'已提取',failed:'未完成',interrupted:'上次分析中断'};
   box.append(elem('p',(names[media.status]||media.status)+(media.duration?' · '+media.duration.toFixed(1)+' 秒':'')),source(media,0));
   if(media.error)box.append(elem('p',media.error,'studio-hint'));
   box.append(button('删除素材',()=>{if(confirm('删除这份素材、它的记忆草稿及已应用的相关记忆？'))void mutation('/memories/'+media.id+'/delete',{});}));$('memory-media').append(box);
  }
  if(!state.media.length)$('memory-media').append(elem('p','还没有回忆素材。可以一次选择多个文件。','studio-hint'));
  $('memory-cards').replaceChildren();
  for(const card of state.cards){const media=state.media.find(m=>m.id===card.media);if(!media)continue;
   const article=elem('article',null,'memory-card');article.dataset.card=card.id;
   article.append(elem('h4',card.confirmed?'已记住 · '+state.profile.name:'待主人核对'),elem('p','依据：'+media.name+(media.duration?' · '+card.start.toFixed(2)+' 秒关键帧':' · 单张照片'),'studio-hint'),source(media,card.start));
   const quote=elem('textarea');quote.value=card.quote;quote.maxLength=400;quote.rows=3;quote.setAttribute('aria-label','核对或补充真实依据');article.append(quote);
   const types=elem('select'),values=elem('select');types.setAttribute('aria-label','记忆类型');values.setAttribute('aria-label','岛上表达');
   for(const kind of ['memory','greeting','comfort','play','activity','vocality']){const o=elem('option',state.labels[kind]);o.value=kind;types.append(o);}types.value=card.kind||'memory';
   const options=()=>{values.replaceChildren();for(const [v,label]of Object.entries(state.options[types.value])){const o=elem('option',label);o.value=v;values.append(o);}};types.onchange=options;options();if(card.value)values.value=card.value;
   const fields=elem('div',null,'memory-fields');fields.append(types,values);article.append(fields);
   const label=elem('label'),check=elem('input');check.type='checkbox';label.append(check,document.createTextNode('我已对照素材，确认依据真实；若选择习惯，我确认它确实符合这只宠物。'));article.append(label);
   const actions=elem('div',null,'studio-actions');actions.append(button(card.confirmed?'更新这份记忆':'确认并记住',()=>{if(!check.checked)return say('请先核对原始素材，并勾选确认。');void mutation('/memory-cards/'+card.id+'/publish',{version:card.version,revision:state.revision,kind:types.value,value:values.value,quote:quote.value,confirmed:true});}));
   if(card.confirmed)actions.append(button('撤回确认',()=>mutation('/memory-cards/'+card.id+'/withdraw',{version:card.version,revision:state.revision})));
   actions.append(button('删除这条',()=>{if(confirm('删除这条草稿及它已应用的记忆？原始素材保留。'))void mutation('/memory-cards/'+card.id+'/delete',{version:card.version,revision:state.revision});}));article.append(actions);$('memory-cards').append(article);
  }
  const selectedTask=task.id,selectedEpoch=epoch;window.StudioHabits?.render({state,task,base:endpoint(task.id),say,request,lock,busy:()=>working||studioBusy,current:()=>task?.id===selectedTask&&epoch===selectedEpoch,update:d=>{state=d;render();},mutate:mutation});
  if(!state.cards.length)$('memory-cards').append(elem('p','上传后点击“提取记忆”，结果会先以草稿出现在这里。也可以在下方手动留下你记得的习惯。','studio-hint'));lock(working);
 }
 async function mutation(path,body){if(working||studioBusy||!task)return;const id=task.id,token=epoch;lock(true);try{const d=await request(endpoint(id)+path,body);if(token!==epoch)return;state=d;render();changed();say('已保存到当前宠物档案。启用它的专属形象时会自动使用已确认的记忆。');}catch(e){say(e.message);await load();}finally{lock(false);}}
 $('memory-files').onchange=async event=>{if(working||studioBusy||!task)return;const files=[...event.target.files];if(!files.length)return;const id=task.id,token=epoch;lock(true);let ok=0;const failed=[];
  try{for(let i=0;i<files.length;i++){if(token!==epoch)break;say('正在上传 '+(i+1)+' / '+files.length+'：'+files[i].name);try{if(files[i].size>30*1024*1024)throw Error('文件超过 30 MB');const data=new FormData();data.append('file',files[i]);const result=await request(endpoint(id)+'/memories',data);if(token!==epoch)break;state=result;ok++;render();lock(true);}catch(e){failed.push(files[i].name+'：'+e.message);}}
   say('已保存 '+ok+' / '+files.length+' 份（重复文件自动合并）。'+(failed.length?'以下文件未完成，可重新选择重试：'+failed.join('；'):'现在可以开始提取记忆。'));
  }finally{event.target.value='';lock(false);}
 };
 $('memory-analyze').onclick=async()=>{if(working||studioBusy||!state||!task)return;if(!$('memory-consent').checked)return say('请先阅读并勾选视觉分析说明。');const media=state.media.filter(m=>!m.mime.startsWith('audio/')&&m.status!=='done'&&m.status!=='analyzing');if(!media.length)return say('没有待分析的素材；正在处理的素材可稍后刷新。');const id=task.id,token=epoch;lock(true);let ok=0;const errors=[];
  try{for(let i=0;i<media.length;i++){if(token!==epoch)break;say('正在整理 '+(i+1)+' / '+media.length+'：'+media[i].name+'，每份可能需要约一分钟。');try{const result=await request(endpoint(id)+'/memories/'+media[i].id+'/analyze',{consent:true});if(token!==epoch)break;state=result;ok++;render();lock(true);}catch(e){errors.push(media[i].name+'：'+e.message);}}
   await load();say('完成 '+ok+' / '+media.length+' 份。请逐条对照原片，再确认应用。'+(errors.length?'未完成：'+errors.join('；'):''));
  }finally{$('memory-consent').checked=false;lock(false);}
 };
 $('memory-refresh').onclick=()=>{if(!working)void load();};
 function loadExisting(){const frame=$('studio-existing-frame');frame.src='/pet-imprint?embedded=1&petId='+([1,2,3,4].includes(legacyPet)?legacyPet:1);}
 $('studio-existing').ontoggle=()=>{if($('studio-existing').open&&!$('studio-existing-frame').getAttribute('src'))loadExisting();};
 if(params.has('petId')&&section==='memories')$('studio-existing').open=true;
 window.StudioMemories={busy:()=>working,setStudioBusy:value=>{studioBusy=value;lock(working);},select:row=>{if(task?.id===row?.id)return;epoch++;window.StudioHabits?.clear();task=row||null;state=null;$('memory-media').replaceChildren();$('memory-cards').replaceChildren();say('');$('memory-consent').checked=false;if(row)void load();}};
 addEventListener('beforeunload',event=>{if(working){event.preventDefault();event.returnValue='';}});
})();
