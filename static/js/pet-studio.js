/* Private pet reference workspace; no background cloud submissions. */
(()=>{'use strict';
 const $=id=>document.getElementById(id),scope=window.PET_STUDIO_SCOPE;
 const labels={draft:'收集照片',awaiting_generation:'等待生成',review:'核对外貌',approved:'等待动作适配'};
 let generationAvailable=false;let rows=[],selected=null,busy=false,renderer,scene,camera,controls,model,frame,previewTicket=0,mixer,activeAction,pollTimer;
 const qualityPass=(row,stage)=>{const stages=['inputs','geometry','rig','motion'];return stages.slice(0,stages.indexOf(stage)+1).every(k=>row.quality?.[k]?.status==='pass');};
 const jobs=new Set(),adaptChoices=new Map();let previewProgress;
 const note=t=>{$('studio-message').textContent=t;};
 async function api(path='',body,form=false){
  const response=await fetch('/api/pet-studio'+path,{method:body===undefined?'GET':'POST',headers:body===undefined?{}:form?{'X-Profile-Scope':scope}:{'X-Profile-Scope':scope,'Content-Type':'application/json'},body:body===undefined?undefined:form?body:JSON.stringify(body)});
  const data=await response.json();if(!response.ok)throw Error(data.error||'暂时无法保存，请稍后重试');
  if(data.scope!==scope)throw Error('账号已变化，请刷新页面');return data;
 }
 function setBusy(value){busy=value;for(const el of document.querySelectorAll('.pet-studio button,.pet-studio input,.pet-studio textarea,.pet-studio select'))el.disabled=value;if(!value)generationControls();}
 async function change(path,body,form=false){if(busy)return;setBusy(true);try{const data=await api(path,body,form);generationAvailable=!!data.generationAvailable;rows=data.tasks;paint();note('已保存。');schedulePoll();}catch(e){note(e.message);}finally{setBusy(false);}}
 function generationControls(){
  const row=rows.find(r=>r.id===selected);if(!row)return;const g=row.generation;
  const locked=['submitting','waiting','running','processing','uncertain','paused'].includes(g?.status);
  $('studio-generate').disabled=busy||!qualityPass(row,'inputs')||!generationAvailable||!row.assets.includes('front')||row.assets.includes('model')||(g&&g.status!=='failed');
  $('studio-cloud-consent').disabled=busy||locked;$('studio-generation-resume').hidden=g?.status!=='paused';
  $('studio-generation-status').textContent=(g?.message||(!generationAvailable?'服务器尚未配置生成服务。':'保存后可手动开始，通常需要几分钟。'))+(g?.credits!=null?' · 已消耗 '+g.credits+' 积分':'');
  $('studio-approve').disabled=busy||!qualityPass(row,'geometry');$('studio-adapt-start').disabled=busy||!qualityPass(row,'geometry');$('studio-motion-accept').disabled=busy||!qualityPass(row,'motion');$('studio-equip').disabled=busy||!qualityPass(row,'motion');
  for(const input of document.querySelectorAll('#studio-photos input,#studio-model'))input.disabled=busy||locked;
 }
 function schedulePoll(){
  const wanted=new Set();let polling=false;
  for(const row of rows){for(const [type,active,label,failed] of [
   ['adapt',row.adaptation?.status==='running','正在为'+row.name+'适配动作 · Blender 处理中',['failed','needs_manual'].includes(row.adaptation?.status)],
   ['cloud',['submitting','waiting','running','processing'].includes(row.generation?.status),row.generation?.message||'正在生成模型',['failed','paused','uncertain'].includes(row.generation?.status)]
  ]){const key='studio:'+type+':'+row.id;wanted.add(key);if(active){jobs.add(key);polling=true;window.PaitLoading?.sync(key,true,label);}else if(jobs.has(key)){window.PaitLoading?.sync(key,false,failed?'处理暂未完成，请查看工作室提示':label,failed);jobs.delete(key);}}}
  for(const key of jobs)if(!wanted.has(key)){window.PaitLoading?.sync(key,false);jobs.delete(key);}
  clearTimeout(pollTimer);if(!polling)return;
  pollTimer=setTimeout(async()=>{if(busy){schedulePoll();return;}try{
   const data=await api(),before=JSON.stringify(rows.map(r=>[r.id,r.status,r.adaptation?.status,r.generation?.status,r.generation?.message]));
   rows=data.tasks;generationAvailable=!!data.generationAvailable;
   if(before!==JSON.stringify(rows.map(r=>[r.id,r.status,r.adaptation?.status,r.generation?.status,r.generation?.message])))paint();schedulePoll();
  }catch(e){for(const key of jobs)window.PaitLoading?.sync(key,false,'暂时无法读取进度，请刷新查看',true);jobs.clear();note(e.message+'，可刷新查看原任务。');}},3000);
 }
 function dispose(){previewProgress?.cancel();previewProgress=null;previewTicket++;cancelAnimationFrame(frame);mixer?.stopAllAction();mixer=null;activeAction=null;if(model){model.traverse(o=>{o.geometry?.dispose();for(const m of Array.isArray(o.material)?o.material:[o.material])if(m){for(const v of Object.values(m))if(v?.isTexture)v.dispose();m.dispose();}});scene?.remove(model);model=null;}if(scene)scene.traverse(o=>{if(o.isGridHelper){o.geometry.dispose();o.material.dispose();}});controls?.dispose();renderer?.dispose();renderer=null;}
 async function preview(row){
  dispose();$('studio-motion-buttons').hidden=true;$('studio-motion-buttons').replaceChildren();$('studio-head-control').hidden=true;$('studio-preview-wrap').hidden=!row.assets.includes('model');if(!row.assets.includes('model'))return;
  const ticket=previewTicket,progress=previewProgress=window.PaitLoading?.start('正在打开宠物模型');$('studio-preview-note').textContent='正在加载模型…';
  try{
   const adapted=row.assets.includes('adapted');const response=await fetch('/api/pet-studio/'+row.id+'/assets/'+(adapted?'adapted':'model'),{paitTask:progress});if(!response.ok)throw Error('模型读取失败');
   const buffer=await (globalThis.PaitLoading?.buffer?globalThis.PaitLoading.buffer(response):response.arrayBuffer());if(ticket!==previewTicket)return;
   progress?.update('正在解析模型、材质与动作');
   const gltf=await new Promise((resolve,reject)=>new THREE.GLTFLoader().parse(buffer,'',resolve,reject));
   if(ticket!==previewTicket){gltf.scene.traverse(o=>{o.geometry?.dispose();for(const m of Array.isArray(o.material)?o.material:[o.material])if(m){for(const v of Object.values(m))if(v?.isTexture)v.dispose();m.dispose();}});return;}
   model=gltf.scene;renderer=new THREE.WebGLRenderer({canvas:$('studio-preview'),alpha:true,antialias:true,powerPreference:'high-performance'});window.PaitWebCompat?.prepareRenderer(renderer);renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.outputEncoding=THREE.sRGBEncoding;
   scene=new THREE.Scene();scene.add(new THREE.HemisphereLight(0xffffff,0x809584,1.3));const light=new THREE.DirectionalLight(0xffefdb,1.5);light.position.set(3,5,4);scene.add(light);
   const box=(window.PetModelBounds?PetModelBounds.measure(THREE,model):new THREE.Box3().setFromObject(model)),size=box.getSize(new THREE.Vector3()),center=box.getCenter(new THREE.Vector3()),extent=Math.max(size.x,size.y,size.z);
   if(!Number.isFinite(extent)||extent<=0)throw Error('模型尺寸无效');model.position.sub(center);model.scale.setScalar(1/extent);model.position.multiplyScalar(1/extent);scene.add(model);
   camera=new THREE.PerspectiveCamera(35,1,.01,100);camera.position.set(1.3,.8,2);controls=new THREE.OrbitControls(camera,renderer.domElement);controls.enableDamping=true;controls.minDistance=.7;controls.maxDistance=5;
   const grid=new THREE.GridHelper(2,20,0x889c8d,0xc3cec0);grid.position.y=-size.y/(2*extent);scene.add(grid);
   mixer=new THREE.AnimationMixer(model);const names={idle_breathe:'站立',walk:'走路',run:'跑动',sit_down:'坐下',stand_up:'起身',lie_down:'趴下',sleep_loop:'睡觉',eat:'吃饭',sniff:'嗅闻',stretch:'伸懒腰',turn_left:'左转',turn_right:'右转'};
   $('studio-motion-buttons').hidden=!adapted;$('studio-head-control').hidden=!adapted;$('studio-head').value='0';
   $('studio-motion-buttons').replaceChildren(...gltf.animations.filter(c=>names[c.name]).map(clip=>{const b=document.createElement('button');b.textContent=names[clip.name];b.onclick=()=>{activeAction?.fadeOut(.15);activeAction=mixer.clipAction(clip);activeAction.reset().fadeIn(.15).play();for(const sibling of b.parentElement.children)sibling.setAttribute('aria-pressed',String(sibling===b));};return b;}));
   if(adapted)$('studio-motion-buttons').firstChild?.click();
   const head=model.getObjectByName('head');let headBase=null;
   let last=0;const tick=now=>{frame=requestAnimationFrame(tick);if(document.hidden||now-last<33)return;const dt=Math.min(.05,(now-last)/1000);last=now;if(headBase)head.quaternion.copy(headBase);mixer.update(dt);if(head&&adapted){headBase=head.quaternion.clone();head.rotation.y+=Number($('studio-head').value);}const c=$('studio-preview');renderer.setSize(c.clientWidth,c.clientHeight,false);camera.aspect=c.clientWidth/Math.max(c.clientHeight,1);camera.updateProjectionMatrix();controls.update();renderer.render(scene,camera);progress?.done();};frame=requestAnimationFrame(tick);
   $('studio-preview-note').textContent=adapted?'动作草稿 · 地面网格用于检查脚掌 · 请逐项验收':'拖动旋转 · 滚轮缩放 · 外貌预览不代表动作已适配';
  }catch(e){progress?.fail('模型预览未完成，请查看页面提示');if(ticket===previewTicket){dispose();$('studio-preview-note').textContent='预览失败：'+e.message;}}
 }
 function paint(){
  selected=rows.some(r=>r.id===selected)?selected:rows[0]?.id;const row=rows.find(r=>r.id===selected);
  $('studio-list').replaceChildren(...rows.map(r=>{const b=document.createElement('button');b.className='studio-choice';b.setAttribute('aria-pressed',String(r.id===selected));b.textContent=r.name;const small=document.createElement('small');small.textContent=labels[r.status];b.append(small);b.onclick=()=>{if(!busy){selected=r.id;paint();}};return b;}));
  $('studio-detail').hidden=!row;$('studio-empty').hidden=!!row;if(!row){dispose();return;}
  $('studio-name').textContent=row.name;$('studio-status').textContent=labels[row.status];$('studio-mode').textContent=row.mode==='memory'?'留一份想念 · 私人档案':'身边的伙伴 · 私人档案';
  $('studio-download').href='/api/pet-studio/'+row.id+'/references';
  $('studio-guidance').textContent=row.mode==='memory'?'从已有照片里选清楚的一张就好。不必凑齐所有角度，未拍到的细节需要后续与你一起核对。':'尽量在柔和光线下拍摄站立的全身照，保持姿势相近，让耳朵、四肢与尾巴都在画面内。手机可直接拍照上传；视频抽帧稍后开放。';
  $('studio-photos').replaceChildren(...Object.entries({front:'正面 · 必填',left:'左侧',right:'右侧',back:'背面',detail:'花纹细节'}).map(([slot,title])=>{const label=document.createElement('label');label.className='studio-photo';const caption=document.createElement('span');caption.textContent=title;label.append(caption);if(row.assets.includes(slot)){const img=document.createElement('img');img.src='/api/pet-studio/'+row.id+'/assets/'+slot+'?v='+row.updated;img.alt=title;label.append(img);}else{const box=document.createElement('span');box.className='photo-placeholder';box.textContent='＋';label.append(box);}const input=document.createElement('input');input.type='file';input.accept='image/jpeg,image/png';input.setAttribute('aria-label','上传'+title+'照片');input.onchange=()=>upload(row.id,slot,input.files[0]);label.append(input);return label;}));
  $('studio-quality').replaceChildren(...Object.entries({inputs:'参考照片一致性',geometry:'身体结构',rig:'骨骼与蒙皮',motion:'网格动作'}).map(([key,label])=>{const li=document.createElement('li'),q=row.quality?.[key];li.textContent=label+'：'+({pass:'通过',fail:'不通过',unknown:'待审核'}[q?.status]||'待审核')+(q?.reason?' · '+q.reason:'');return li;}));
  $('studio-notes').value=row.notes;$('studio-approve').hidden=row.status!=='review';$('studio-prepare').hidden=['review','approved'].includes(row.status);
  $('studio-next').textContent=row.status==='approved'?'外貌已确认，可在下方适配动作。动作验收后可手动启用到自己的猫咪岛。':'保存说明后，可随时回来继续。模型生成及外貌核对不会自动公开档案。';paintAdaptation(row);generationControls();$('studio-cloud-consent').checked=false;void preview(row);
 }
 function paintAdaptation(row){$('studio-adaptation').hidden=row.status!=='approved';const a=row.adaptation,r=a?.report||{},states={running:'Blender 正在适配，通常需要几十秒。你可以离开页面，稍后回来查看。',review_motion:'动作草稿已生成，请在上方逐一播放并检查。',needs_manual:'需要手动修正后重试',failed:'此次适配未完成，可以重试',reviewed:'已记录你的动作验收。现在可以手动启用到猫咪岛。'};$('studio-adapt-status').textContent=states[a?.status]||'在本机运行，不调用混元，不消耗云端额度。';$('studio-adapt-start').hidden=a?.status==='running';$('studio-adapt-report').replaceChildren(...[r.error,...(r.warnings||[])].filter(Boolean).map(text=>{const li=document.createElement('li');li.textContent=text;return li;}));$('studio-adapt-downloads').hidden=!row.assets.includes('adapted');$('studio-adapt-glb').href='/api/pet-studio/'+row.id+'/assets/adapted';$('studio-adapt-glb').download='cat-animated.glb';$('studio-adapt-blend').href='/api/pet-studio/'+row.id+'/assets/blend';$('studio-motion-checks').hidden=a?.status!=='review_motion';for(const c of $('studio-motion-checks').querySelectorAll('input'))c.checked=false;$('studio-equip-controls').hidden=a?.status!=='reviewed';$('studio-equip').hidden=!!row.equipped;$('studio-unequip').hidden=!row.equipped;const noRig=a?.status==='needs_manual'&&r.error?.startsWith('未发现骨骼');const saved=adaptChoices.get(row.id);$('studio-adapt-mode').value=saved?.mode||(noRig?'template-skin':r.mode||(row.generation?.status==='done'?'template-skin':'auto'));$('studio-adapt-forward').value=saved?.forward||'-Y';if(noRig)$('studio-adapt-status').textContent='模型没有骨骼。请先完成身体结构审核；合格的站立猫可尝试模板蒙皮草稿，坐卧或异常结构需先修正网格。';}
 function upload(id,slot,file){if(!file)return;const limit=(slot==='model'?30:8)*1024*1024;if(file.size>limit){note('文件过大，请压缩后再上传。');return;}if(slot!=='model'&&rows.find(r=>r.id===id)?.assets.includes('model')&&!confirm('更换参考照将移除旧模型预览，继续吗？'))return;const data=new FormData();data.append('file',file);void change('/'+id+'/assets/'+slot,data,true);}
 $('studio-create').onsubmit=e=>{e.preventDefault();const data=new FormData(e.target);selected=null;void change('',{name:data.get('name'),mode:data.get('mode')});};
 $('studio-model').onchange=e=>upload(selected,'model',e.target.files[0]);
 for(const [id,op] of [['studio-prepare','prepare'],['studio-save','notes'],['studio-approve','approve']])$(id).onclick=()=>change('/'+selected+'/'+op,{notes:$('studio-notes').value});
 $('studio-delete').onclick=()=>{if(confirm('永久删除这个私人档案、照片和模型？'))void change('/'+selected+'/delete',{});};
 for(const id of ['studio-adapt-mode','studio-adapt-forward'])$(id).onchange=()=>{if(selected)adaptChoices.set(selected,{mode:$('studio-adapt-mode').value,forward:$('studio-adapt-forward').value});};
 $('studio-adapt-start').onclick=()=>change('/'+selected+'/adapt',{mode:$('studio-adapt-mode').value,forward:$('studio-adapt-forward').value});
 $('studio-motion-accept').onclick=()=>{const checks=[...$('studio-motion-checks').querySelectorAll('input:checked')].map(c=>c.value);if(checks.length!==8){note('请播放动作并完成全部 8 项检查。');return;}void change('/'+selected+'/review-motion',{checks,jobId:rows.find(r=>r.id===selected)?.adaptation?.id});};
 $('studio-generate').onclick=()=>{if(!$('studio-cloud-consent').checked){note('请先确认照片上传腾讯云及云端计费。');return;}void change('/'+selected+'/generate',{consent:true});};
 $('studio-generation-resume').onclick=()=>change('/'+selected+'/resume-generation',{});
 $('studio-equip').onclick=()=>change('/'+selected+'/equip',{jobId:rows.find(r=>r.id===selected)?.adaptation?.id});
 $('studio-unequip').onclick=()=>change('/'+selected+'/unequip',{});
 addEventListener('pagehide',()=>{clearTimeout(pollTimer);dispose();});
 const initial=window.PaitLoading?.start('正在读取宠物档案');
 api().then(data=>{generationAvailable=!!data.generationAvailable;rows=data.tasks;paint();schedulePoll();initial?.done();}).catch(e=>{initial?.fail('宠物档案未能读取，请查看页面提示');note(e.message);$('studio-login').hidden=false;setBusy(true);});
})();
