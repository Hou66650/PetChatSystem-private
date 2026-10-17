/* Accessories are fitted once in the loaded rest pose, then parented to sockets.
   Never chase world coordinates every frame or infer sockets on private models. */
(function(root){
 'use strict';
 const ASSETS=Object.freeze({'moss-bow':'moss-bow','coral-bow':'coral-bow',daisy:'daisy','blue-beret':'blue-beret'}),cache=new Map();
 async function piece(T,item,loadAccessory){
  if(!Object.prototype.hasOwnProperty.call(ASSETS,item.id))throw Error('未知装扮资源');
  if(loadAccessory){const group=await loadAccessory(item.id);group.name='wardrobe:'+item.id;return group;}
  if(!cache.has(item.id))cache.set(item.id,new Promise((resolve,reject)=>new T.GLTFLoader().load('/static/models/wardrobe-v1/'+ASSETS[item.id]+'.glb',g=>resolve(g.scene),undefined,reject)).catch(error=>{cache.delete(item.id);throw error;}));
  const source=await cache.get(item.id),group=source.clone(true);
  // Instances own their GPU resources; the four small source assets stay cached.
  group.traverse(o=>{if(o.isMesh){o.geometry=o.geometry.clone();o.material=Array.isArray(o.material)?o.material.map(m=>m.clone()):o.material.clone();}});
  group.name='wardrobe:'+item.id;return group;
 }
 function fitSurfaces(T,root){
  const result=[],temporary=[];
  root.traverse(o=>{
   if(!o.isMesh)return;
   if(!o.isSkinnedMesh){result.push(o);return;}
   o.skeleton.update();
   const attr=o.geometry.attributes.position,positions=new Float32Array(attr.count*3),v=new T.Vector3();
   for(let i=0;i<attr.count;i++){v.fromBufferAttribute(attr,i);o.boneTransform(i,v);v.toArray(positions,i*3);}
   const geometry=new T.BufferGeometry();geometry.setAttribute('position',new T.BufferAttribute(positions,3));geometry.setIndex(o.geometry.index);
   const material=new T.MeshBasicMaterial({side:T.DoubleSide}),surface=new T.Mesh(geometry,material);surface.matrixWorld.copy(o.matrixWorld);
   result.push(surface);temporary.push(surface);
  });
  return {result,dispose(){temporary.forEach(o=>{o.geometry.dispose();o.material.dispose();});}};
 }
 function dispose(group){const geometries=new Set(),materials=new Set();group.traverse(o=>{if(o.geometry)geometries.add(o.geometry);if(o.material)(Array.isArray(o.material)?o.material:[o.material]).forEach(m=>materials.add(m));});geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());group.parent?.remove(group);}
 class Controller{
  constructor(T,rootModel,{custom=false,loadAccessory=null}={}){
   this.loadAccessory=loadAccessory;
   this.T=T;this.root=rootModel;this.mounts={};this.objects=[];this.epoch=0;rootModel.userData.accessories=this.objects;rootModel.userData.wardrobe=this;
   if(custom)return;
   rootModel.updateMatrixWorld(true);
   const height=new T.Box3().setFromObject(rootModel).getSize(new T.Vector3()).y;
   const orientation=rootModel.getWorldQuaternion(new T.Quaternion());
   const surfaces=fitSurfaces(T,rootModel);
   const up=new T.Vector3(0,1,0).applyQuaternion(orientation);
   for(const slot of ['head','neck']){
    const socket=rootModel.getObjectByName('SOCKET_'+slot);if(!socket)continue;
    const frames={};
    for(const design of slot==='head'?['flower','beret']:['bow']){
     const frame=new T.Object3D();frame.position.copy(socket.getWorldPosition(new T.Vector3()));frame.quaternion.copy(orientation);
     if(slot==='head'){
      const left=rootModel.getObjectByName('ear_L'),right=rootModel.getObjectByName('ear_R');
      if(!left||!right)continue;
      frame.position.copy(left.getWorldPosition(new T.Vector3())).add(right.getWorldPosition(new T.Vector3())).multiplyScalar(.5);
      const center=frame.position.clone();let hit;
      for(const offset of design==='flower'?[.035,.015,0]:[0]){
       for(const depth of [.012,-.02,-.05,-.08]){
        frame.position.copy(center).add(new T.Vector3(offset,0,depth).applyQuaternion(orientation).multiplyScalar(height));
        const ray=new T.Raycaster(frame.position.clone().addScaledVector(up,height),up.clone().negate(),0,height*1.6);
        const candidate=ray.intersectObjects(surfaces.result,false)[0];
        if(candidate&&(!hit||candidate.point.dot(up)>hit.point.dot(up)))hit=candidate;
       }
       if(hit)break;
      }
      // Surface fit is sampled only in the loaded pose, never while animating.
      if(!hit)continue;
      frame.position.copy(hit.point).addScaledVector(up,.002*height);
      if(design==='flower'){
       const normal=hit.face.normal.clone().transformDirection(hit.object.matrixWorld);
       if(normal.dot(up)<0)normal.negate();
       frame.quaternion.premultiply(new T.Quaternion().setFromUnitVectors(up,normal));
      }
     }
     if(slot==='neck'){
      const forward=new T.Vector3(0,0,1).applyQuaternion(orientation);
      frame.position.addScaledVector(up,-.025*height);
      const ray=new T.Raycaster(frame.position.clone().addScaledVector(forward,height),forward.clone().negate(),0,height*1.6);
      const hit=ray.intersectObjects(surfaces.result,false)[0];if(!hit)continue;
      frame.position.copy(hit.point).addScaledVector(forward,.022*height);
     }
     frame.scale.setScalar(height);frame.updateMatrixWorld();
     frames[design]=new T.Matrix4().copy(socket.matrixWorld).invert().multiply(frame.matrixWorld);
    }
    if(Object.keys(frames).length)this.mounts[slot]={socket,frames};
   }
   surfaces.dispose();
  }
  supports(slot,design){return !!this.mounts[slot]&&(!design||!!this.mounts[slot].frames[design]);}
  async apply(items){
   const epoch=++this.epoch,used=new Set(),pending=[];
   try{
    for(const item of items||[]){
     const mount=this.mounts[item.slot];if(!mount||used.has(item.slot))continue;
     const local=mount.frames[item.design];if(!local)continue;
     const design=await piece(this.T,item,this.loadAccessory);
     if(epoch!==this.epoch){dispose(design);pending.forEach(dispose);return 0;}
     const holder=new this.T.Group();local.decompose(holder.position,holder.quaternion,holder.scale);
     holder.add(design);holder.userData.item=item.id;pending.push(holder);used.add(item.slot);
     holder.userData.socket=mount.socket;
    }
    if(epoch!==this.epoch){pending.forEach(dispose);return 0;}
    this.objects.forEach(dispose);this.objects=pending;this.root.userData.accessories=this.objects;
    for(const holder of pending){holder.userData.socket.add(holder);delete holder.userData.socket;}
    return pending.length;
   }catch(error){pending.forEach(dispose);throw error;}
  }
  dispose(){this.epoch++;this.objects.forEach(dispose);this.objects=[];this.root.userData.accessories=this.objects;}

 }
 root.PetWardrobe={Controller,piece};
})(globalThis);
