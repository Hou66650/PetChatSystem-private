(()=>{'use strict';
 const $=id=>document.getElementById(id),phases={loading:'加载地图',idle:'等待 / 休息',planning:'选择目标',walking:'前往地点',docking:'靠近食水盆',aligning:'到达 / 观察环境',acting:'执行动作',stopped:'已离开'},actions={drink:'饮水',observe:'观察',sniff:'嗅闻',rub:'蹭墙',jump:'短跳',groom:'理毛',stretch:'伸展',rest:'休息',eat:'进食',sleep:'回窝睡觉'},results={completed:'已完成',blocked:'受阻',interrupted:'被打断'};
 const cutoffs=new Map();
 let paused=false,busy=false,latest=null,selected='',timer,scopeLost=false,receivedAt=0;
 const text=(id,value)=>$(id).textContent=value;
 function sceneContext(d){
  const scene=d.scene||{},current=scene.current,used=scene.used?.[selected],decision=scene.decisions?.find(r=>r.stream===selected);
  const list=(id,items)=>$(id).replaceChildren(...(items.length?items:['暂无记录']).map(value=>{const li=document.createElement('li');li.textContent=value;return li;}));
  text('scene-current',current?'服务器场景版本 '+current.revision+' · '+new Date(current.asOf*1000).toLocaleTimeString():'场景数据暂不可用');
  text('scene-received',used?'本实例使用版本 '+used.revision+(used.revision===current?.revision?' · 已同步':' · 当前行动沿用出发快照，新变化将在后续选择时考虑'):'尚未收到本实例的场景快照，请刷新猫咪小岛。');
  list('scene-beds',[...(used?.beds||[]).map(b=>b.name+'：'+(b.plant?b.plant.name+(b.plant.variant?' ✧ 梦幻变异':'')+' · '+b.plant.stageName+' · '+b.plant.stage+'/10'+(b.plant.wateredToday?' · 今日已浇水':''):'尚未种植')),...(used?.decorations||[]).map(p=>p.place+'：'+p.plant)]);
  list('scene-changes',(current?.recentChanges||[]).map(e=>new Date(e.created*1000).toLocaleTimeString()+' · '+e.summary));
  list('scene-experiences',(scene.experiences||[]).map(e=>new Date(e.created*1000).toLocaleString()+' · '+e.summary));
  text('scene-model-status',decision?new Date(decision.created*1000).toLocaleTimeString()+' · '+(decision.modelUsed?'已尝试请求模型；结果来源：'+decision.result.source:'本轮使用本地规则，未请求模型'):'本实例尚无后台决策请求。');
  text('scene-model-input',decision?JSON.stringify({inputs:decision.inputs,result:decision.result},null,2):'');
 }
 function renderPaths(s,age){
  const history=CatPaths.trail(s?.trail,cutoffs.get(selected)??-Infinity);
  $('walked-path').setAttribute('d',$('show-trail').checked?history.d:'');
  $('planned-path').setAttribute('d',$('show-route').checked&&age<=10&&s?.phase!=='stopped'?CatPaths.route([s.x,s.z],s.route):'');
  text('path-stats',history.count+' 个轨迹点 · 已记录路程 '+history.length.toFixed(1)+' 米'+(s?.pathLength>64?' · 路线显示前 64 个路点':'')+(age>10?' · 数据已暂停更新':''));
 }
 function render(d){
  text('life-story',d.relationship?.story||'今天的故事还在发生。');text('life-imprints',(d.relationship?.imprints||[]).join(' '));
  const options=d.streams.map(s=>{const o=document.createElement('option');o.value=s.stream;o.textContent=s.stream.slice(0,8)+' · '+new Date(s.updated*1000).toLocaleTimeString();return o;});
  $('streams').replaceChildren(...options);if(!d.streams.some(s=>s.stream===selected))selected=d.streams[0]?.stream||'';$('streams').value=selected;
  const stream=d.streams.find(s=>s.stream===selected),s=stream?.snapshot,age=stream?d.serverTime-stream.updated:Infinity;
  sceneContext(d);
  $('share-card').disabled=!stream;
  for(const id of ['agent-pause','agent-resume','agent-home'])if($(id))$(id).disabled=scopeLost||!stream||age>10||s.phase==='stopped';
  const control=d.controls?.find(c=>c.stream===selected);if(control&&$('control-status'))text('control-status',({pending:d.serverTime-control.created>30?'指令已过期':'等待猫咪页面确认…',applied:'猫咪已响应指令',busy:'猫咪正在与你互动，请稍后再试',unavailable:'当前无法执行，请检查自由活动和猫窝',expired:'指令已过期，请重新发送'})[control.result]||'');
  text('connection',paused?'刷新已暂停':!stream?'等待小岛连接':s.phase==='stopped'?'猫咪已离开':age>10?'遥测已停止更新 · 小岛可能在后台或已断开':'实时连接 · 每 2 秒更新');
  renderPaths(s,age);
  const names=Object.fromEntries(d.catalog.map(p=>[p.id,p.name]));
  if(s){text('intent',s.text||'等待下一次探索');text('reason',s.reason);text('phase',phases[s.phase]||s.phase);text('source',s.source==='model'?'模型建议 · 本地校验执行':'本地自主策略');text('energy',Math.round(s.energy*100)+'%');text('hunger',Math.round((s.hunger||0)*100)+'%');text('thirst',Math.round((s.thirst||0)*100)+'%');text('tired',Math.round((1-s.energy)*100)+'%');text('route',s.pathLength);$('energy-bar').value=s.energy;text('task',(s.enabled?'自由活动开启':'自由活动关闭')+' · '+(names[s.target]||'暂无目标')+' · '+(actions[s.action]||'等待')+' · 坐标 '+s.x.toFixed(2)+', '+s.z.toFixed(2));$('cat').setAttribute('cx',s.x);$('cat').setAttribute('cy',s.z);$('cat').setAttribute('visibility','visible');}
  const ns='http://www.w3.org/2000/svg';$('places').replaceChildren(...d.catalog.map(p=>{const g=document.createElementNS(ns,'g'),c=document.createElementNS(ns,'circle'),t=document.createElementNS(ns,'text');c.setAttribute('cx',p.x);c.setAttribute('cy',p.z);c.setAttribute('r',p.id===s?.target?'.23':'.14');c.setAttribute('fill',p.id===s?.target?'#f3d38a':s?.candidates.includes(p.id)?'#78d8b0':'#537f71');t.setAttribute('x',p.x+.23);t.setAttribute('y',p.z-.2);t.textContent=p.name;g.append(c,t);return g;}));
  const events=d.events.filter(e=>e.stream===selected);text('count',events.length+' 条');$('events').replaceChildren(...events.map(e=>{const a=document.createElement('div');a.className='event';const time=document.createElement('time'),p=document.createElement('p'),reason=document.createElement('small');time.textContent=new Date(e.updated*1000).toLocaleTimeString()+' · '+(phases[e.snapshot.phase]||e.snapshot.phase);p.textContent=(e.snapshot.source==='model'?'[AI] ':'[本地] ')+e.snapshot.text;reason.textContent=e.snapshot.reason;a.append(time,p,reason);return a;}));
  $('memory').replaceChildren(...d.catalog.map(p=>{const m=d.memory.find(m=>m.target===p.id),tr=document.createElement('tr');for(const value of [p.name,m?.visits||0,results[m?.result]||'尚未探索']){const td=document.createElement('td');td.textContent=value;tr.append(td);}return tr;}));
 }
 async function poll(){if(paused||busy||document.hidden||scopeLost)return;busy=true;const abort=new AbortController(),timeout=setTimeout(()=>abort.abort(),5000);try{const r=await fetch('/api/cat-agent/monitor',{cache:'no-store',signal:abort.signal});if(!r.ok)throw Error();const d=await r.json();if(d.scope!==window.MONITOR_SCOPE){scopeLost=true;for(const id of ['agent-pause','agent-resume','agent-home'])if($(id))$(id).disabled=true;latest=null;sceneContext({});$('share-card').disabled=true;$('share-preview').close();cutoffs.clear();$('walked-path').setAttribute('d','');$('planned-path').setAttribute('d','');text('path-stats','');$('events').replaceChildren();$('memory').replaceChildren();$('places').replaceChildren();$('cat').setAttribute('visibility','hidden');for(const id of ['life-story','life-imprints','intent','reason','phase','source','energy','hunger','thirst','tired','route','task'])text(id,'—');text('connection','账号已切换，请刷新监控页');return;}latest=d;receivedAt=Date.now();render(d);}catch(e){text('connection','监控连接暂时中断，正在重试');}finally{clearTimeout(timeout);busy=false;}}
 async function control(action){if(scopeLost||!selected)return;try{const r=await fetch('/api/cat-agent/control',{method:'POST',headers:{'Content-Type':'application/json','X-Profile-Scope':window.MONITOR_SCOPE},body:JSON.stringify({stream:selected,action}),signal:AbortSignal.timeout(6000)});const d=await r.json();if(!r.ok)throw Error(d.error||'发送失败');if(d.scope!==window.MONITOR_SCOPE)throw Error('账号已变化，请刷新');text('control-status','已发送，等待猫咪页面确认…');await poll();}catch(e){text('control-status',e.message);}}
 for(const [id,action] of [['agent-pause','pause'],['agent-resume','resume'],['agent-home','home']])if($(id))$(id).onclick=()=>control(action);
 $('share-card').onclick=()=>{const s=CatShareCard.summary(latest?{...latest,serverTime:latest.serverTime+(Date.now()-receivedAt)/1000}:null,selected,cutoffs.get(selected)??-Infinity);if(!s)return;CatShareCard.draw($('share-canvas'),s);text('share-status',s.points?'预览已生成，保存后可自行分享。':'当前还没有轨迹，卡片会如实显示 0 个采样点。');$('share-preview').showModal();};
 $('share-close').onclick=()=>$('share-preview').close();
 $('share-save').onclick=()=>{const progress=window.PaitLoading?.start('正在导出探索卡片');$('share-canvas').toBlob(blob=>{if(!blob){progress?.fail('卡片导出失败，请重试');text('share-status','保存失败，请重试。');return;}progress?.done();const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='派特岛-猫咪探索-'+new Date().toISOString().slice(0,10)+'.png';a.click();setTimeout(()=>URL.revokeObjectURL(url),30000);},'image/png');};
 for(const id of ['show-trail','show-route'])$(id).onchange=()=>{if(latest)render(latest);};
 $('clear-trail').onclick=()=>{const s=latest?.streams.find(s=>s.stream===selected)?.snapshot;cutoffs.set(selected,s?.trail?.at(-1)?.[2]??0);if(latest)render(latest);};
 $('pause').onclick=()=>{paused=!paused;$('pause').textContent=paused?'继续刷新':'暂停刷新';if(latest)render(latest);if(!paused)poll();};$('streams').onchange=()=>{selected=$('streams').value;if(latest)render(latest);};document.addEventListener('visibilitychange',()=>{if(!document.hidden)poll();});timer=setInterval(poll,2000);window.addEventListener('pagehide',()=>clearInterval(timer));poll();
})();
