/* Bounded paw contact samples: no per-frame full-mesh bounds or scene raycasts. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.PetGrounding=api;})(typeof window!=='undefined'?window:globalThis,function(){
 'use strict';
 const clamp=(v,a,b)=>Math.max(a,Math.min(b,v));
 class Controller{
  constructor(T,root,model,navigation){
   Object.assign(this,{T,root,model,navigation});this.samples=[];this.feet=[];this.skins=new Set();
   this.point=new T.Vector3();this.up=new T.Vector3(0,1,0);this.normal=new T.Vector3();this.tilt=new T.Quaternion();this.target=new T.Quaternion();
   this.basePosition=new T.Vector3();this.baseRotation=new T.Quaternion();this.lift=0;this.applied=false;
   root.updateMatrixWorld(true);const inv=new T.Matrix4().copy(root.matrixWorld).invert(),height=root.userData.height||.85;
   for(const leg of ['FL','FR','HL','HR']){
    const bone=model.getObjectByName(leg+'_foot');if(!bone)continue;
    this.feet.push(bone.getWorldPosition(new T.Vector3()).applyMatrix4(inv));
   }
   if(this.feet.length!==4)return;
   // Keep the lowest skinned vertex in each small paw cell, including toes/heels.
   // Skin weights exclude the tail even when an imported cat has a low hanging tail.
   const cells=this.feet.map(()=>new Map()),cell=height*.025;
   model.traverse(mesh=>{
    if(!mesh.isSkinnedMesh||!mesh.geometry?.attributes.skinWeight)return;
    mesh.skeleton.update();const a=mesh.geometry.attributes,indices=a.skinIndex,weights=a.skinWeight;
    const legIndices=new Set(mesh.skeleton.bones.map((b,i)=>/^(FL|FR|HL|HR)_(foot|lower)$/.test(b.name)?i:-1));legIndices.delete(-1);
    for(let i=0;i<a.position.count;i++){
     let weight=0;for(let j=0;j<4;j++)if(legIndices.has(indices.getComponent?indices.getComponent(i,j):indices.array[i*4+j]))weight+=weights.array[i*4+j];
     if(weight<.25)continue;
     this.vertex(mesh,i,this.point).applyMatrix4(inv);const p=this.point;
     if(p.y>height*.18)continue;
     let leg=0,best=Infinity;for(let j=0;j<4;j++){const f=this.feet[j],d=(p.x-f.x)**2+(p.z-f.z)**2;if(d<best){best=d;leg=j;}}
     if(best>(height*.22)**2)continue;
     const key=Math.round(p.x/cell)+','+Math.round(p.z/cell),old=cells[leg].get(key);
     if(!old||p.y<old.y)cells[leg].set(key,{mesh,index:i,y:p.y});
    }
   });
   for(const cellMap of cells){const points=[...cellMap.values()].sort((a,b)=>a.y-b.y);this.samples.push(...points.slice(0,40));}
   for(const s of this.samples)this.skins.add(s.mesh);
  }
  vertex(mesh,index,out){out.fromBufferAttribute(mesh.geometry.attributes.position,index);if(mesh.applyBoneTransform)mesh.applyBoneTransform(index,out);else mesh.boneTransform(index,out);return out.applyMatrix4(mesh.matrixWorld);}
  beforeFrame(){if(!this.applied)return;this.model.position.copy(this.basePosition);this.model.quaternion.copy(this.baseRotation);this.applied=false;}
  update(dt,{airborne=false,state='idle'}={}){
   this.beforeFrame();if(!this.samples.length||airborne){this.lift=0;this.tilt.identity();return;}
   const root=this.root,k=1-Math.exp(-Math.max(0,Math.min(.1,dt))*14);
   root.updateMatrixWorld(true);
   // Fit the support plane in the pet's yaw space, keeping gait motion out of the slope estimate.
   let sx=0,sz=0,sh=0;const heights=[];
   for(const f of this.feet){this.point.set(f.x,0,f.z).applyMatrix4(root.matrixWorld);const h=this.navigation.surfaceHeight(this.point);heights.push(h);sx+=f.x;sz+=f.z;sh+=h;}
   sx/=4;sz/=4;sh/=4;let xx=0,zz=0,xz=0,xh=0,zh=0;
   for(let i=0;i<4;i++){const x=this.feet[i].x-sx,z=this.feet[i].z-sz,h=heights[i]-sh;xx+=x*x;zz+=z*z;xz+=x*z;xh+=x*h;zh+=z*h;}
   const det=xx*zz-xz*xz,standing=['idle','walk','trot','run','turnLeft','turnRight','sniff'].includes(state);
   const gx=standing&&det>1e-8?clamp((xh*zz-zh*xz)/det,-.35,.35):0,gz=standing&&det>1e-8?clamp((zh*xx-xh*xz)/det,-.35,.35):0;
   this.normal.set(-gx,1,-gz).normalize();this.target.setFromUnitVectors(this.up,this.normal);this.tilt.slerp(this.target,k);
   this.basePosition.copy(this.model.position);this.baseRotation.copy(this.model.quaternion);this.applied=true;
   // Rotate about the grounded pet origin, including the GLB's recentering offset.
   this.model.position.applyQuaternion(this.tilt);this.model.quaternion.premultiply(this.tilt);
   root.updateMatrixWorld(true);for(const mesh of this.skins)mesh.skeleton.update();
   let needed=0;
   for(const s of this.samples){this.vertex(s.mesh,s.index,this.point);needed=Math.max(needed,this.navigation.surfaceHeight(this.point)+.003-this.point.y);}
   needed=clamp(needed,0,(root.userData.height||.85)*.35);
   // Never smooth upward through a surface; ease only the release on the downhill side.
   this.lift=needed>=this.lift?needed:this.lift+(needed-this.lift)*k;
   this.model.position.y+=this.lift;root.updateMatrixWorld(true);
  }
 }
 return {Controller};
});
