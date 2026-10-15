/* Private pet reference workspace; no background cloud submissions. */
(()=>{'use strict';
 const $=id=>document.getElementById(id),scope=window.PET_STUDIO_SCOPE;
 const labels={draft:'收集照片',awaiting_generation:'等待生成',review:'核对外貌',approved:'等待动作适配'};
 let rows=[],selected=null,busy=false,renderer,scene,camera,controls,model,frame,previewTicket=0;
 const note=t=>{$('studio-message').textContent=t;};
 async function api(path='',body,form=false){
  const response=await fetch('/api/pet-studio'+path,{method:body===undefined?'GET':'POST',headers:body===undefined?{}:form?{'X-Profile-Scope':scope}:{'X-Profile-Scope':scope,'Content-Type':'application/json'},body:body===undefined?undefined:form?body:JSON.stringify(body)});
  const data=await response.json();if(!response.ok)throw Error(data.error||'暂时无法保存，请稍后重试');
  if(data.scope!==scope)throw Error('账号已变化，请刷新页面');return data;
 }
 function setBusy(value){busy=value;for(const el of document.querySelectorAll('.pet-studio button,.pet-studio input,.pet-studio textarea'))el.disabled=value;}
 async function change(path,body,form=false){if(busy)return;setBusy(true);try{const data=await api(path,body,form);rows=data.tasks;paint();note('已保存。');}catch(e){note(e.message);}finally{setBusy(false);}}
 function dispose(){previewTicket++;cancelAnimationFrame(frame);if(model){model.traverse(o=>{o.geometry?.dispose();for(const m of Array.isArray(o.material)?o.material:[o.material])if(m){for(const v of Object.values(m))if(v?.isTexture)v.dispose();m.dispose();}});scene?.remove(model);model=null;}controls?.dispose();renderer?.dispose();renderer=null;}
 async function preview(row){
  dispose();$('studio-preview-wrap').hidden=!row.assets.includes('model');if(!row.assets.includes('model'))return;
  const ticket=previewTicket;$('studio-preview-note').textContent='正在加载模型…';
  try{
   const response=await fetch('/api/pet-studio/'+row.id+'/assets/model');if(!response.ok)throw Error('模型读取失败');
   const buffer=await response.arrayBuffer();if(ticket!==previewTicket)return;
   const gltf=await new Promise((resolve,reject)=>new THREE.GLTFLoader().parse(buffer,'',resolve,reject));
   if(ticket!==previewTicket){gltf.scene.traverse(o=>{o.geometry?.dispose();for(const m of Array.isArray(o.material)?o.material:[o.material])if(m){for(const v of Object.values(m))if(v?.isTexture)v.dispose();m.dispose();}});return;}
   model=gltf.scene;renderer=new THREE.WebGLRenderer({canvas:$('studio-preview'),alpha:true,antialias:true,powerPreference:'high-performance'});renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.outputEncoding=THREE.sRGBEncoding;
   scene=new THREE.Scene();scene.add(new THREE.HemisphereLight(0xffffff,0x809584,1.3));const light=new THREE.DirectionalLight(0xffefdb,1.5);light.position.set(3,5,4);scene.add(light);
   const box=new THREE.Box3().setFromObject(model),size=box.getSize(new THREE.Vector3()),center=box.getCenter(new THREE.Vector3()),extent=Math.max(size.x,size.y,size.z);
   if(!Number.isFinite(extent)||extent<=0)throw Error('模型尺寸无效');model.position.sub(center);model.scale.setScalar(1/extent);model.position.multiplyScalar(1/extent);scene.add(model);
   camera=new THREE.PerspectiveCamera(35,1,.01,100);camera.position.set(1.3,.8,2);controls=new THREE.OrbitControls(camera,renderer.domElement);controls.enableDamping=true;controls.minDistance=.7;controls.maxDistance=5;
   let last=0;const tick=now=>{frame=requestAnimationFrame(tick);if(document.hidden||now-last<33)return;last=now;const c=$('studio-preview');renderer.setSize(c.clientWidth,c.clientHeight,false);camera.aspect=c.clientWidth/Math.max(c.clientHeight,1);camera.updateProjectionMatrix();controls.update();renderer.render(scene,camera);};frame=requestAnimationFrame(tick);
   $('studio-preview-note').textContent='拖动旋转 · 滚轮缩放 · 外貌预览不代表动作已适配';
  }catch(e){if(ticket===previewTicket){dispose();$('studio-preview-note').textContent='预览失败：'+e.message;}}
 }
 function paint(){
  selected=rows.some(r=>r.id===selected)?selected:rows[0]?.id;const row=rows.find(r=>r.id===selected);
  $('studio-list').replaceChildren(...rows.map(r=>{const b=document.createElement('button');b.className='studio-choice';b.setAttribute('aria-pressed',String(r.id===selected));b.textContent=r.name;const small=document.createElement('small');small.textContent=labels[r.status];b.append(small);b.onclick=()=>{if(!busy){selected=r.id;paint();}};return b;}));
  $('studio-detail').hidden=!row;$('studio-empty').hidden=!!row;if(!row){dispose();return;}
  $('studio-name').textContent=row.name;$('studio-status').textContent=labels[row.status];$('studio-mode').textContent=row.mode==='memory'?'留一份想念 · 私人档案':'身边的伙伴 · 私人档案';
  $('studio-download').href='/api/pet-studio/'+row.id+'/references';
  $('studio-guidance').textContent=row.mode==='memory'?'从已有照片里选清楚的一张就好。不必凑齐所有角度，未拍到的细节需要后续与你一起核对。':'尽量在柔和光线下拍摄站立的全身照，保持姿势相近，让耳朵、四肢与尾巴都在画面内。手机可直接拍照上传；视频抽帧稍后开放。';
  $('studio-photos').replaceChildren(...Object.entries({front:'正面 · 必填',left:'左侧',right:'右侧',back:'背面',detail:'花纹细节'}).map(([slot,title])=>{const label=document.createElement('label');label.className='studio-photo';const caption=document.createElement('span');caption.textContent=title;label.append(caption);if(row.assets.includes(slot)){const img=document.createElement('img');img.src='/api/pet-studio/'+row.id+'/assets/'+slot+'?v='+row.updated;img.alt=title;label.append(img);}else{const box=document.createElement('span');box.className='photo-placeholder';box.textContent='＋';label.append(box);}const input=document.createElement('input');input.type='file';input.accept='image/jpeg,image/png';input.setAttribute('aria-label','上传'+title+'照片');input.onchange=()=>upload(row.id,slot,input.files[0]);label.append(input);return label;}));
  $('studio-notes').value=row.notes;$('studio-approve').hidden=row.status!=='review';$('studio-prepare').hidden=['review','approved'].includes(row.status);
  $('studio-next').textContent=row.status==='approved'?'外貌已确认。下一步需要 Blender 骨骼、蒙皮与动作验收；目前尚未启用到岛屿或桌宠。':'保存说明后，可随时回来继续。模型生成及外貌核对不会自动公开档案。';void preview(row);
 }
 function upload(id,slot,file){if(!file)return;const limit=(slot==='model'?30:8)*1024*1024;if(file.size>limit){note('文件过大，请压缩后再上传。');return;}if(slot!=='model'&&rows.find(r=>r.id===id)?.assets.includes('model')&&!confirm('更换参考照将移除旧模型预览，继续吗？'))return;const data=new FormData();data.append('file',file);void change('/'+id+'/assets/'+slot,data,true);}
 $('studio-create').onsubmit=e=>{e.preventDefault();const data=new FormData(e.target);selected=null;void change('',{name:data.get('name'),mode:data.get('mode')});};
 $('studio-model').onchange=e=>upload(selected,'model',e.target.files[0]);
 for(const [id,op] of [['studio-prepare','prepare'],['studio-save','notes'],['studio-approve','approve']])$(id).onclick=()=>change('/'+selected+'/'+op,{notes:$('studio-notes').value});
 $('studio-delete').onclick=()=>{if(confirm('永久删除这个私人档案、照片和模型？'))void change('/'+selected+'/delete',{});};
 addEventListener('pagehide',dispose);
 api().then(data=>{rows=data.tasks;paint();}).catch(e=>{note(e.message);$('studio-login').hidden=false;setBusy(true);});
})();
