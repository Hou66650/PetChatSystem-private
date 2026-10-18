/* Evidence review UI. Never applies model suggestions without a deliberate review. */
(()=>{'use strict';
 let view=null,stop=false;
 const $=id=>document.getElementById(id);
 const node=(tag,text)=>{const n=document.createElement(tag);if(text)n.textContent=text;return n;};
 const button=(text,fn)=>{const b=node('button',text);b.type='button';b.onclick=fn;return b;};
 const field=(label,input)=>{const n=node('label',label);n.append(input);return n;};
 const checked=label=>{const input=node('input');input.type='checkbox';return [field(label,input),input];};
 const actions={curious:'歪头观察',come:'走近',sit:'坐下',sniff:'嗅闻',affection:'亲昵',play_bow:'邀请玩耍',lie_down:'趴卧'};
 function source(event,v){const m=v.state.media.find(x=>x.id===event.media);const d=node('details');d.append(node('summary','核对原始片段 '+event.start.toFixed(1)+'–'+event.end.toFixed(1)+' 秒'));
  d.ontoggle=()=>{if(!d.open||d.children.length>1)return;const media=node(m.mime.startsWith('image/')?'img':m.mime.startsWith('audio/')?'audio':'video');media.className='memory-source';media.controls=true;media.preload='metadata';media.src=v.base+'/memories/'+m.id+'/source';
   media.onloadedmetadata=()=>{media.currentTime=event.start;};media.ontimeupdate=()=>{if(event.end>event.start&&media.currentTime>=event.end)media.pause();};d.append(media);};return d;}
 function render(v){view=v;const h=v.state.habits;if(!h)return;const jobs=h.jobs,done=jobs.filter(j=>j.status==='done').length;
  $('habit-progress').value=done;$('habit-progress').max=Math.max(1,jobs.length);$('habit-count').textContent=done+' / '+jobs.length+' 个片段已整理；今日视觉请求 '+h.quota.used+' / '+h.quota.limit+' 次';
  $('habit-events').replaceChildren();$('habit-candidates').replaceChildren();
  if(!h.events.length)$('habit-events').append(node('p','还没有行为事件。分析完成后，请对照原片确认动物身份、行为和拍摄组。'));
  for(const e of h.events){const card=node('article');card.className='memory-card habit-event';card.append(node('h4',(e.confirmed?'已核对 · ':'待核对 · ')+e.name),source(e,v));
   card.append(node('p',e.provenance==='audio_energy'?'本地检测到的声音，不代表已识别叫声含义。':e.provenance==='image'?'照片只代表一个瞬间。':'3 fps 采样观察，快速动作及遮挡可能漏检。'));
   const quote=node('textarea');quote.value=e.observation;quote.maxLength=400;quote.setAttribute('aria-label','行为依据');card.append(quote);
   if(e.original_observation){const original=node('details');original.append(node('summary','查看原始分析记录'),node('p',e.original_observation));card.append(original);}
   const group=node('input');group.value=e.capture_group===e.media?e.name:e.capture_group;group.maxLength=80;card.append(field('拍摄组：同一原片的剪辑、连拍请填同名，不重复算证据',group));
   const kind=node('select'),value=node('select');kind.setAttribute('aria-label','行为类别');value.setAttribute('aria-label','动作表达');
   for(const [key,label]of Object.entries(h.labels)){const o=node('option',label);o.value=key;kind.append(o);}kind.value=e.kind;
   const sequence=node('p');sequence.className='habit-sequence';const describe=()=>{const r=h.options[kind.value][value.value];sequence.textContent='岛上表达：'+(r.plan.length?r.plan.map(x=>actions[x]||x).join(' → '):r.label)+'（当前模型须支持对应动作）';};
   const choices=()=>{value.replaceChildren();for(const [key,r]of Object.entries(h.options[kind.value])){const o=node('option',r.label);o.value=key;value.append(o);}describe();};kind.onchange=choices;value.onchange=describe;choices();value.value=e.value;describe();
   const fields=node('div');fields.className='memory-fields';fields.append(kind,value);card.append(fields,sequence);
   const [ownerLabel,owner]=checked('我补充了原片之外的真实情境（如确实是在呼唤它）');
   owner.checked=!!e.owner_context;
   const [proofLabel,proof]=checked('我已核对原片：这是这只宠物，行为或叫声以及拍摄分组正确');card.append(ownerLabel,proofLabel);
   const buttons=node('div');buttons.className='studio-actions';buttons.append(button('确认这个事件',()=>{if(!proof.checked)return v.say('请先核对原片和动物身份。');void v.mutate('/habit-events/'+e.id+'/review',{revision:e.revision,kind:kind.value,value:value.value,observation:quote.value,captureGroup:group.value,subjectConfirmed:true,confirmed:true,ownerContext:owner.checked});}));
   if(e.confirmed)buttons.append(button('撤回事件',()=>v.mutate('/habit-events/'+e.id+'/review',{revision:e.revision,confirmed:false})));card.append(buttons);$('habit-events').append(card);
  }
  for(const c of h.candidates){const card=node('article');card.className='memory-card';const active=h.rules.some(r=>r.kind===c.kind&&r.value===c.value);
   card.append(node('h4',h.labels[c.kind]+' · '+c.label),node('p',c.groups+' 个已核对拍摄组，'+c.evidence.length+' 条事件。'+c.level+'。'+(c.contradictions?'另有 '+c.contradictions+' 条不同表现，请判断情境。':'')),node('p','动作顺序：'+(c.plan.map(x=>actions[x]||x).join(' → ')||c.label)));
   card.append(button(active?'已应用，点击撤回':'我确认符合它，应用这个习惯',()=>v.mutate('/habit-rules',{kind:c.kind,value:c.value,events:c.evidence,revision:v.state.revision,confirmed:true,withdraw:active})));
   $('habit-candidates').append(card);
  }
 }
 async function analyze(){const v=view;if(!v||v.busy())return;if(!$('habit-consent').checked)return v.say('请先勾选本轮分析说明。');
  const jobs=v.state.habits.jobs.filter(j=>j.status==='ready'||j.status==='failed'||j.status==='interrupted').slice(0,12);if(!jobs.length)return v.say('没有待分析的片段；可刷新查看进度。');
  stop=false;v.lock(true);$('habit-stop').disabled=false;let completed=0;const errors=[];
  try{for(const j of jobs){if(stop||!v.current())break;v.say('整理片段 '+(completed+1)+' / '+jobs.length+'；可以暂停，已完成片段不会重复分析。');try{const result=await v.request(v.base+'/habits/'+j.media+'/analyze',{part:j.part,consent:true});if(!v.current())break;v.update(result);completed++;}catch(e){errors.push(e.message);break;}v.lock(true);$('habit-stop').disabled=false;}
   v.say(errors.length?errors.join('；'):stop?'已暂停。再次点击可继续未完成片段。':'本轮片段已完成，请核对事件；如有剩余片段，可点击继续。');
  }finally{v.lock(false);$('habit-stop').disabled=true;$('habit-consent').checked=false;}
 }
 $('habit-analyze').onclick=analyze;$('habit-stop').onclick=()=>{stop=true;$('habit-stop').disabled=true;view?.say('当前片段完成后暂停，不会丢失已完成结果。');};
 window.StudioHabits={render,clear:()=>{stop=true;view=null;$('habit-events').replaceChildren();$('habit-candidates').replaceChildren();$('habit-count').textContent='';$('habit-progress').value=0;}};
})();
