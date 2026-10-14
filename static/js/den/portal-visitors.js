/* A host island displays only its current, server-authorized visitor. */
(function(root){'use strict';
 class Visitors{
  constructor({THREE,scene,getPet,getNavigation,notify,loader}){Object.assign(this,{THREE,scene,getPet,getNavigation,notify});this.loader=loader||new SelectedAssets.Loader(new THREE.GLTFLoader());this.epoch=0;this.pet=null;this.trip=null;this.failedAt=0;}
  clear(){this.epoch++;this.loader.begin();if(this.pet){this.scene.remove(this.pet.root);SelectedAssets.disposeTree(this.pet.root);}this.pet=null;this.trip=null;this.target=null;this.loading=false;}
  sync(trips){this.lastSync=performance.now();const id=String(this.getPet().id),trip=trips.find(t=>!t.mine&&t.kind==='neighbor'&&t.status==='active'&&String(t.hostPet?.id)===id);
   if(!trip){if(this.trip)this.clear();return;}
   if(this.trip?.id===trip.id){this.trip=trip;this.target=trip.snapshot?.visitor||null;if(this.pet||this.loading||performance.now()-this.failedAt<5000)return;}
   else this.clear();
   this.trip=trip;this.target=trip.snapshot?.visitor||null;this.loading=true;const epoch=this.epoch,ticket=this.loader.begin();
   this.loader.glb(trip.petSpec.model,ticket).then(gltf=>{if(epoch!==this.epoch||String(this.getPet().id)!==id){SelectedAssets.disposeTree(gltf.scene);return;}
    this.pet=new PortalPets.Pet(this.THREE,gltf,trip.petSpec);const nav=this.getNavigation(),arrival=nav?.nearest(this.target||(trip.hostPet.theme==='room'?{x:4.6,z:-.75}:{x:.8,z:-.5}));if(!arrival)throw Error('Visitor arrival is unavailable');
    this.pet.root.position.set(arrival.x,nav.surfaceHeight(arrival),arrival.z);this.scene.add(this.pet.root);this.notify(trip.petSpec.name+'来串门啦！可以在小岛上看到它。');
   }).catch(e=>{if(epoch!==this.epoch||e.name==='AbortError')return;if(this.pet){this.scene.remove(this.pet.root);SelectedAssets.disposeTree(this.pet.root);this.pet=null;}this.failedAt=performance.now();this.notify('来访宠物加载失败，正在重试。');}).finally(()=>{if(epoch===this.epoch)this.loading=false;});
  }
  update(dt){if(this.trip&&performance.now()-this.lastSync>45000){this.clear();return;}if(!this.pet)return;const nav=this.getNavigation(),s=this.target,p=this.pet.root.position;if(nav&&s){const q=nav.nearest(s);if(q){const k=1-Math.exp(-Math.min(dt,.05)*5);if(nav.segmentClear(p,q)){p.x+=(q.x-p.x)*k;p.z+=(q.z-p.z)*k;}else{p.x=q.x;p.z=q.z;}p.y=nav.surfaceHeight(p);}const angle=Math.atan2(Math.sin(s.yaw-this.pet.root.rotation.y),Math.cos(s.yaw-this.pet.root.rotation.y));this.pet.root.rotation.y+=angle*(1-Math.exp(-Math.min(dt,.05)*8));this.pet.play(s.action||'idle');}this.pet.update(dt);}
 }
 root.PortalVisitors={Visitors};
})(globalThis);
