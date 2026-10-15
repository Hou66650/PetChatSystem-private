(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.FarmPlacement=api;})(typeof window!=='undefined'?window:globalThis,function(){
 'use strict';
 const radius=(species,container)=>container==='pot'?.28:species==='birch'?.42:species==='pumpkin'?.48:.30;
 const inside=(p,d)=>d.kind==='rect'?Math.abs(p.x-d.x)<=d.w/2&&Math.abs(p.z-d.z)<=d.d/2:((p.x-d.x)/d.rx)**2+((p.z-d.z)/d.rz)**2<=1;
 function overlap(p,o,r){if(o.kind!=='rect')return Math.hypot(p.x-o.x,p.z-o.z)<=r+o.r;const c=Math.cos(o.angle||0),s=Math.sin(o.angle||0),dx=p.x-o.x,dz=p.z-o.z;return Math.hypot(Math.max(0,Math.abs(c*dx+s*dz)-o.w/2),Math.max(0,Math.abs(-s*dx+c*dz)-o.d/2))<=r;}
 function segment(p,line){const dx=line.b.x-line.a.x,dz=line.b.z-line.a.z,t=Math.max(0,Math.min(1,((p.x-line.a.x)*dx+(p.z-line.a.z)*dz)/(dx*dx+dz*dz||1)));return Math.hypot(p.x-line.a.x-t*dx,p.z-line.a.z-t*dz);}
 function validate(map,p,others=[],ignore){
  if(!map||!['soil','pot'].includes(p.container)||!['cosmos','pumpkin','birch'].includes(p.species)||![p.x,p.z,p.yaw].every(Number.isFinite))return '请选择有效落点';
  if(p.container==='pot'&&p.species!=='cosmos')return '这株植物需要栽入土壤';
  const r=radius(p.species,p.container),ring=Array.from({length:17},(_,i)=>i===16?p:{x:p.x+r*Math.cos(i*Math.PI/8),z:p.z+r*Math.sin(i*Math.PI/8)});
  if(!ring.every(q=>map.domains.some(d=>inside(q,d))))return '请放在岛屿地面内';
  if(map.blocked.some(o=>overlap(p,o,r+.08)))return '请避开水面、建筑和已有设施';
  if(map.paths.some(line=>segment(p,line)<line.r+r))return '这里要留给宠物通行';
  if(p.container==='soil'&&(!ring.every(q=>map.soil.some(d=>inside(q,d)))||map.soilExcluded.some(o=>overlap(p,o,r))))return '这里是铺装地面，请选择草地土壤或使用花盆';
  if(others.some(o=>o.id!==ignore&&Math.hypot(p.x-o.x,p.z-o.z)<r+radius(o.species,o.container)+.12))return '与其他植物太近了';
  return '';
 }
 return {radius,validate};
});
