(()=>{
 'use strict';
 const root=document.querySelector('.island-home'),canvas=document.getElementById('island-home-canvas');if(!root||!canvas)return;
 const reduced=matchMedia('(prefers-reduced-motion: reduce)'),choices=[...root.querySelectorAll('.island-choice')],status=document.getElementById('island-preview-status'),enter=document.getElementById('island-enter');
 let renderer;
 try{renderer=new THREE.WebGLRenderer({canvas,alpha:true,antialias:true,powerPreference:'high-performance'});}catch(e){status.textContent='三维预览暂不可用，可用下方链接直接进入小窝。';return;}
 renderer.setPixelRatio(Math.min(devicePixelRatio,1.4));renderer.outputEncoding=THREE.sRGBEncoding;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.25;
 const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(42,1,.1,180);scene.fog=new THREE.Fog(0x294b5b,65,135);
 scene.add(new THREE.HemisphereLight(0xe3f5ff,0x718777,1.7));const sun=new THREE.DirectionalLight(0xffe8cd,2.5);sun.position.set(-15,30,20);scene.add(sun);const rim=new THREE.DirectionalLight(0xb6e6ff,1);rim.position.set(20,10,-20);scene.add(rim);
 const controls=new THREE.OrbitControls(camera,canvas);controls.enableDamping=true;controls.dampingFactor=.075;controls.enablePan=false;controls.minDistance=11;controls.maxDistance=100;controls.minPolarAngle=.12;controls.maxPolarAngle=Math.PI*.49;controls.rotateSpeed=.6;controls.zoomSpeed=.8;controls.autoRotateSpeed=.35;
 const positions=[[-9,0,7],[9,1,7],[-9,-.4,-10],[9,.8,-10]],loader=new THREE.GLTFLoader(),ray=new THREE.Raycaster(),pointer=new THREE.Vector2(),projected=new THREE.Vector3();
 let navigationTimer=null;
 let selected=-1,flight=null,entering=false,gesture=null,loaded=0,failed=0,width=0,height=0,last=0,raf;
 const views=choices.map((choice,i)=>{
  const group=new THREE.Group();group.position.set(...positions[i]);group.userData.island=i;scene.add(group);
  const label=document.createElement('button');label.type='button';label.className='island-world-label';label.textContent=choice.dataset.title;label.hidden=true;label.setAttribute('aria-pressed','false');document.querySelector('.island-world-labels').append(label);
  const ring=new THREE.Mesh(new THREE.RingGeometry(4.85,4.89,100),new THREE.MeshBasicMaterial({color:0xb7d8cf,transparent:true,opacity:.27,side:THREE.DoubleSide,depthWrite:false}));ring.rotation.x=-Math.PI/2;ring.position.y=-3.4;group.add(ring);
  const pickArea=new THREE.Mesh(new THREE.CylinderGeometry(4.6,4.6,6,20),new THREE.MeshBasicMaterial({visible:false,side:THREE.DoubleSide}));group.add(pickArea);
  const view={choice,group,label,ring,pickArea,object:null};
  choice.addEventListener('click',e=>{if(e.ctrlKey||e.metaKey||e.shiftKey||e.altKey||e.button!==0)return;e.preventDefault();select(i);});label.onclick=()=>select(i);
  loader.load('/static/models/home-islands/'+choice.dataset.theme+'.glb?v='+encodeURIComponent(root.dataset.version),gltf=>{
   const object=gltf.scene,box=new THREE.Box3().setFromObject(object),size=box.getSize(new THREE.Vector3()),center=box.getCenter(new THREE.Vector3());object.position.sub(center);const scale=9/Math.max(size.x,size.z);object.scale.setScalar(scale);object.position.multiplyScalar(scale);group.add(object);view.object=object;loaded++;label.hidden=false;report();
  },undefined,()=>{failed++;report();});
  return view;
 });
 function report(){status.textContent=loaded+failed===4?(failed?'部分岛屿未加载，仍可选择并进入。':'拖动自由旋转 · 滚轮 / 双指缩放 · 双击岛屿进入小窝'):('正在展开云端群岛 '+(loaded+failed)+'/4');}
 function move(to,target,duration=900,done=null){flight={from:camera.position.clone(),fromTarget:controls.target.clone(),to,target,start:performance.now(),duration:reduced.matches?0:duration,done};controls.autoRotate=false;document.getElementById('island-rotate').setAttribute('aria-pressed','false');}
 function overview(animate=true){const tall=canvas.clientWidth/canvas.clientHeight<1;const to=new THREE.Vector3(tall?42:26,tall?48:30,tall?60:39),target=new THREE.Vector3(0,-4,0);selected=-1;mark();if(animate)move(to,target);else{camera.position.copy(to);controls.target.copy(target);controls.update();}document.getElementById('island-kicker').textContent='四座岛屿 · 一片属于你的世界';document.getElementById('island-name').textContent='先四处看看吧';document.getElementById('island-description').textContent='拖动环绕 · 滚轮缩放 · 点击岛屿近看';enter.href=choices[0].href;enter.innerHTML='去见球球 <span>↗</span>';}
 function mark(){views.forEach((v,i)=>{v.choice.setAttribute('aria-current',String(i===selected));v.label.setAttribute('aria-pressed',String(i===selected));v.ring.material.opacity=i===selected?.8:.27;});}
 function select(i){if(entering)return;selected=i;const v=views[i];mark();const target=v.group.position.clone().add(new THREE.Vector3(0,-1.8,0)),offset=new THREE.Vector3(10,9,17);if(canvas.clientWidth<700)offset.multiplyScalar(1.25);move(target.clone().add(offset),target);document.getElementById('island-kicker').textContent=v.choice.dataset.pet;document.getElementById('island-name').textContent=v.choice.dataset.title;document.getElementById('island-description').textContent=v.choice.dataset.description;enter.href=v.choice.href;enter.innerHTML='进入小岛 <span>↗</span>';}
 function navigate(url){if(entering)return;entering=true;controls.enabled=false;root.classList.add('is-entering');const target=selected>=0?views[selected].group.position.clone():controls.target.clone();let finished=false;const finish=()=>{if(finished)return;finished=true;clearTimeout(navigationTimer);location.assign(url);};navigationTimer=setTimeout(finish,reduced.matches?0:800);move(target.clone().add(new THREE.Vector3(0,2,5)),target,700,finish);}
 enter.addEventListener('click',e=>{if(e.ctrlKey||e.metaKey||e.shiftKey||e.altKey||e.button!==0)return;e.preventDefault();navigate(enter.href);});
 function pick(e){const r=canvas.getBoundingClientRect();pointer.set((e.clientX-r.left)/r.width*2-1,1-(e.clientY-r.top)/r.height*2);ray.setFromCamera(pointer,camera);const hit=ray.intersectObjects(views.filter(v=>v.object).map(v=>v.object),true)[0]||ray.intersectObjects(views.filter(v=>v.object).map(v=>v.pickArea),false)[0];if(!hit)return -1;let o=hit.object;while(o&&o.userData.island===undefined)o=o.parent;return o?o.userData.island:-1;}
 const activePointers=new Set();
 canvas.addEventListener('pointerdown',e=>{activePointers.add(e.pointerId);if(activePointers.size>1){gesture=null;return;}if(!e.isPrimary||e.button!==0)return;gesture={id:e.pointerId,x:e.clientX,y:e.clientY,distance:0};});
 canvas.addEventListener('pointermove',e=>{if(gesture?.id===e.pointerId)gesture.distance=Math.max(gesture.distance,Math.hypot(e.clientX-gesture.x,e.clientY-gesture.y));});
 canvas.addEventListener('pointerup',e=>{activePointers.delete(e.pointerId);const g=gesture;gesture=null;if(!g||g.id!==e.pointerId||g.distance>6||Math.hypot(e.clientX-g.x,e.clientY-g.y)>6||entering)return;const i=pick(e);if(i>=0)select(i);});
 canvas.addEventListener('pointercancel',e=>{activePointers.delete(e.pointerId);gesture=null;});
 canvas.addEventListener('dblclick',e=>{if(entering)return;const i=pick(e);if(i>=0){selected=i;navigate(views[i].choice.href);}});
 controls.addEventListener('start',()=>{if(!entering)flight=null;});
 document.getElementById('island-overview').onclick=()=>overview();
 document.getElementById('island-rotate').onclick=function(){if(entering)return;flight=null;controls.autoRotate=!controls.autoRotate;this.setAttribute('aria-pressed',String(controls.autoRotate));};
 function zoom(factor){if(entering)return;const offset=camera.position.clone().sub(controls.target);offset.multiplyScalar(factor);offset.setLength(THREE.MathUtils.clamp(offset.length(),controls.minDistance,controls.maxDistance));move(controls.target.clone().add(offset),controls.target.clone(),300);}
 document.getElementById('island-zoom-in').onclick=()=>zoom(.8);document.getElementById('island-zoom-out').onclick=()=>zoom(1.25);
 canvas.addEventListener('keydown',e=>{if(!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home'].includes(e.key)||entering)return;e.preventDefault();flight=null;if(e.key==='Home'){overview();return;}const offset=camera.position.clone().sub(controls.target),s=new THREE.Spherical().setFromVector3(offset);if(e.key==='ArrowLeft')s.theta-=.15;if(e.key==='ArrowRight')s.theta+=.15;if(e.key==='ArrowUp')s.phi-=.1;if(e.key==='ArrowDown')s.phi+=.1;s.phi=THREE.MathUtils.clamp(s.phi,controls.minPolarAngle,controls.maxPolarAngle);camera.position.copy(controls.target).add(new THREE.Vector3().setFromSpherical(s));controls.update();});
 overview(false);
 function frame(now){raf=requestAnimationFrame(frame);if(document.hidden||now-last<1000/30)return;last=now;
  if(width!==canvas.clientWidth||height!==canvas.clientHeight){width=canvas.clientWidth;height=canvas.clientHeight;if(!width||!height)return;renderer.setSize(width,height,false);camera.aspect=width/height;camera.updateProjectionMatrix();}
  if(flight){const f=flight,t=f.duration?Math.min(1,(now-f.start)/f.duration):1,k=t*t*(3-2*t);camera.position.lerpVectors(f.from,f.to,k);controls.target.lerpVectors(f.fromTarget,f.target,k);if(t===1){flight=null;f.done?.();}}
  controls.update();views.forEach((v,i)=>{v.group.position.y=positions[i][1]+(reduced.matches?0:Math.sin(now*.00065+i)*.12);projected.copy(v.group.position).add(new THREE.Vector3(0,3.6,0)).project(camera);const x=(projected.x*.5+.5)*width,y=(-projected.y*.5+.5)*height;v.label.hidden=!v.object||projected.z>1||projected.z< -1||x<0||x>width||y<0||y>height-210;v.label.style.left=x+'px';v.label.style.top=y+'px';});renderer.render(scene,camera);
 }
 raf=requestAnimationFrame(frame);
 canvas.addEventListener('webglcontextlost',e=>{e.preventDefault();cancelAnimationFrame(raf);status.textContent='三维画面已暂停，可选择下方岛屿再点击进入。';enter.onclick=null;});
 addEventListener('pagehide',()=>cancelAnimationFrame(raf));addEventListener('pageshow',e=>{if(e.persisted){clearTimeout(navigationTimer);entering=false;flight=null;controls.enabled=true;root.classList.remove('is-entering');raf=requestAnimationFrame(frame);}});
})();
