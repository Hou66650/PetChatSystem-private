/* Shared native/custom GLB animation adapter, used by visits and desktop. */
(function(root){
 class Pet{
  constructor(THREE,gltf,spec){this.T=THREE;this.root=new THREE.Group();this.model=gltf.scene;this.root.add(this.model);this.spec=spec;
   const box=spec.custom&&root.PetModelBounds?root.PetModelBounds.measure(THREE,this.model):new THREE.Box3().setFromObject(this.model),scale=spec.height/Math.max(.01,box.max.y-box.min.y);this.model.scale.setScalar(scale);this.model.position.y=-box.min.y*scale;
   this.wardrobe=root.PetWardrobe?new root.PetWardrobe.Controller(THREE,this.root,spec):null;
   this.wardrobeReady=this.wardrobe?.apply(spec.wardrobe||[]).catch(error=>{this.wardrobeError=error;return 0;});
   this.mixer=new THREE.AnimationMixer(this.model);this.clips=gltf.animations;this.play('idle');
  }
  play(action,timeScale=1){const previous=this.action;this.action=action;const names={idle:['idle_breathe','Idle'],walk:['motion_walk','Walk','walk'],trot:['motion_trot','trot','motion_walk','Walk','walk'],turnLeft:['turn_left','motion_walk','Walk','walk'],turnRight:['turn_right','motion_walk','Walk','walk'],run:['run','motion_trot','Run'],sniff:['sniff','Idle'],sleep:['sleep_loop','lie_down'],petting:['touch_head','happy','sniff'],happy:['happy','wave_paw']}[action]||['idle_breathe'];
   const clip=names.map(n=>this.clips.find(c=>c.name.split('|').pop()===n)).find(Boolean)||this.clips[0];if(!clip)return;const next=this.mixer.clipAction(clip);
   const rate=Number.isFinite(timeScale)?timeScale:1;
   if(next===this.active){next.setEffectiveTimeScale(rate);return;}
   const moving=k=>['walk','trot','run'].includes(k);
   const phase=moving(action)&&moving(previous)&&this.active?this.active.time/this.active.getClip().duration:0;
   next.reset();next.time=((phase%1)+1)%1*clip.duration;next.setEffectiveTimeScale(rate);next.setEffectiveWeight(1);next.fadeIn(.25).play();this.active?.fadeOut(.25);this.active=next;
  }
  update(dt){this.mixer.update(Math.min(.05,dt));}
  snapshot(){return {x:this.root.position.x,z:this.root.position.z,yaw:this.root.rotation.y,action:this.action};}
 }
 root.PortalPets={Pet};
})(globalThis);
