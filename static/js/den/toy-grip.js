/* Screen-space grip drawings anchored to the held model, never used as hit targets. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.ToyGrip=api;})(typeof window!=='undefined'?window:globalThis,function(){
 'use strict';
 const poses={
  ball:{label:'托握球体',anchor:[50,40],reach:0,paths:['M24 46 Q16 44 18 55 L28 74 Q40 90 66 76 L82 53 Q86 43 78 42 Q73 41 69 53 L64 61 Q48 70 35 60 Z','M28 61 L23 39 Q22 32 28 32 Q34 32 35 42 L39 55','M66 61 L72 36 Q73 31 78 33 Q83 35 79 46']},
  disc:{label:'指尖捏边',anchor:[36,42],reach:0,paths:['M74 91 L57 74 Q47 73 43 63 L34 48 Q30 41 36 38 Q42 36 47 44 L54 53 L51 33 Q49 25 41 27 L26 32 Q19 34 17 28 Q16 23 23 20 L43 14 Q58 12 64 29 L77 55 L89 78 Z','M57 55 Q63 47 68 54 L74 64','M61 67 Q68 59 73 66']},
  rope:{label:'抓握绳结',anchor:[48,37],reach:0,paths:['M30 83 L25 61 L24 27 Q25 19 32 22 L37 42 L36 20 Q37 13 44 17 L49 40 L50 19 Q53 12 59 19 L61 42 L65 26 Q70 20 74 27 L74 60 Q73 75 65 82 Z','M25 58 Q18 51 19 42 Q20 36 26 39 L40 49 Q47 54 42 61 Q39 66 32 62','M46 48 L65 48 M47 58 L66 58']},
  bone:{label:'环抱骨头中段',anchor:[49,35],reach:0,paths:['M23 82 L18 61 Q16 48 25 40 L30 23 Q34 17 39 22 L40 46 L57 43 L65 24 Q70 18 75 23 L72 57 Q70 73 61 83 Z','M21 55 Q24 44 33 47 L49 55 Q56 61 50 66 Q46 70 37 65 L28 61','M44 43 L60 45 M45 51 L61 53']},
  duck:{label:'轻捏鸭身',anchor:[48,35],reach:-.05,paths:['M28 85 L22 68 Q16 55 21 44 Q23 39 28 42 L36 55 L35 32 Q35 25 41 26 Q46 27 47 36 L49 51 L56 29 Q60 23 65 27 L65 51 L72 39 Q78 36 79 43 L75 65 Q71 79 62 85 Z','M24 60 Q27 53 34 57 L47 65 Q52 69 48 74 Q44 78 37 73','M51 60 Q59 64 65 58']},
  brush:{label:'斜握刷柄',anchor:[44,39],reach:-.22,paths:['M49 91 L28 69 Q22 61 27 50 L39 27 Q43 21 49 25 L49 38 L59 29 Q65 25 68 31 L61 45 L69 39 Q76 37 77 44 L68 55 Q80 52 81 59 L73 73 L65 83 Z','M29 54 Q22 48 22 40 Q23 34 29 36 L43 48 Q48 53 44 59 Q40 63 34 59','M48 55 L61 64 M45 65 L56 73']},
  rattle:{label:'竖握铃柄',anchor:[48,39],reach:-.24,paths:['M31 89 L26 66 L26 40 Q25 29 35 28 L43 29 Q49 24 56 29 Q67 27 71 37 L73 64 Q73 79 63 88 Z','M27 60 Q19 52 23 46 Q26 41 32 45 L46 54 Q52 60 47 66 Q43 70 36 65','M48 48 L64 49 M50 58 L65 59 M49 69 L63 70']}
 };
 function svg(id){const p=poses[id];if(!p)return '';return '<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><g fill="#fff3de" fill-opacity=".9" stroke="#ae805d" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round">'+p.paths.map(d=>'<path d="'+d+'"/>').join('')+'</g></svg>';}
 class Controller{
  constructor({THREE,element,camera,canvas}){Object.assign(this,{THREE,element,camera,canvas});this.box=new THREE.Box3();this.center=new THREE.Vector3();this.size=new THREE.Vector3();this.edge=new THREE.Vector3();this.id=null;}
  clear(){this.element.hidden=true;document.body.classList.remove('toy-grip-visible');this.id=null;}
  update(record){
   const pose=record?.state==='held'&&poses[record.spec.id];if(!pose){this.clear();return;}
   const n=record.node;n.updateWorldMatrix(true,false);
   if(!n.geometry?.boundingBox)n.geometry?.computeBoundingBox();
   if(n.geometry?.boundingBox)this.box.copy(n.geometry.boundingBox).applyMatrix4(n.matrixWorld);else this.box.setFromObject(n);
   this.box.getCenter(this.center);this.box.getSize(this.size);this.center.y+=this.size.y*pose.reach;
   this.edge.copy(this.center);this.edge.x+=Math.max(this.size.x,this.size.y)*.6;
   this.center.project(this.camera);this.edge.project(this.camera);
   if(!Number.isFinite(this.center.x)||this.center.z>1||this.center.z< -1){this.clear();return;}
   const w=this.canvas.clientWidth,h=this.canvas.clientHeight;
   const scale=Math.max(56,Math.min(116,Math.abs(this.edge.x-this.center.x)*w*2.2));
   if(this.id!==record.spec.id){this.id=record.spec.id;this.element.innerHTML=svg(this.id);this.element.dataset.grip=this.id;this.element.setAttribute('aria-label',pose.label);}
   this.element.style.width=scale+'px';this.element.style.height=scale+'px';
   this.element.style.transform=`translate(${(this.center.x*.5+.5)*w-pose.anchor[0]*scale/100}px,${(-this.center.y*.5+.5)*h-pose.anchor[1]*scale/100}px)`;
   this.element.hidden=false;document.body.classList.add('toy-grip-visible');
  }
 }
 return {poses,svg,Controller};
});
