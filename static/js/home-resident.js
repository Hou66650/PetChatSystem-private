(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.HomeResident=api;})(typeof window!=='undefined'?window:globalThis,function(){
 const models={sakura:'petchat-shiba-v4/qiuqiu',snow:'petchat-husky-v3/xueqiu',room:'petchat-cat-v2/cat',camp:'petchat-shepherd-v2/shepherd'};
 class Resident{
  constructor(T,assets,version,overrides={}){this.overrides=overrides;this.T=T;this.assets=assets;this.version=version;this.loader=new assets.Loader(new T.GLTFLoader());this.model=null;this.mixer=null;this.epoch=0;}
  clear(){this.epoch++;this.loader.begin();if(this.model){this.mixer?.stopAllAction();this.mixer?.uncacheRoot(this.model);this.model.parent?.remove(this.model);this.assets.disposeTree(this.model);}this.model=null;this.mixer=null;}
  async select(theme,view){this.clear();if(!view.object)return;const epoch=this.epoch,ticket=this.loader.current;
   try{const gltf=await this.loader.glb((this.overrides[theme]||'/static/models/'+models[theme]+'.glb')+'?v='+encodeURIComponent(this.version),ticket);if(epoch!==this.epoch){this.assets.disposeTree(gltf.scene);return;}
    const T=this.T,model=gltf.scene,box=new T.Box3().setFromObject(model),size=box.getSize(new T.Vector3()),scale=.82/size.y;
    model.scale.multiplyScalar(scale);model.position.y=-box.min.y*scale;
    view.group.updateMatrixWorld(true);const start=view.group.position.clone().add(new T.Vector3(0,12,1.2)),ray=new T.Raycaster(start,new T.Vector3(0,-1,0));const hit=ray.intersectObject(view.object,true)[0];
    model.position.add(new T.Vector3(0,hit?hit.point.y-view.group.position.y:0,1.2));model.rotation.y=.45;view.group.add(model);this.model=model;
    this.mixer=new T.AnimationMixer(model);const clip=gltf.animations.find(a=>/^(idle_breathe|idle)$/i.test(a.name))||gltf.animations.find(a=>/idle/i.test(a.name));if(clip)this.mixer.clipAction(clip).play();
   }catch(e){if(e.name!=='AbortError')console.warn('Island pet preview unavailable');}
  }
  update(dt){this.mixer?.update(Math.min(dt,.1));}
 }
 return {Resident,models};
});
