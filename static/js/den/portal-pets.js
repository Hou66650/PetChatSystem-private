/* Shared native/custom GLB animation adapter, used by visits and desktop. */
(function(root){
 class Pet{
  constructor(THREE,gltf,spec){this.T=THREE;this.root=new THREE.Group();this.model=gltf.scene;this.root.add(this.model);this.spec=spec;
   const box=new THREE.Box3().setFromObject(this.model),scale=spec.height/Math.max(.01,box.max.y-box.min.y);this.model.scale.setScalar(scale);this.model.position.y=-box.min.y*scale;
   this.mixer=new THREE.AnimationMixer(this.model);this.clips=gltf.animations;this.play('idle');
  }
  play(action){if(['trot','turnLeft','turnRight'].includes(action))action='walk';if(this.action===action)return;this.action=action;const names={idle:['idle_breathe','Idle'],walk:['motion_walk','Walk'],run:['run','motion_trot','Run'],sniff:['sniff','Idle'],sleep:['sleep_loop','lie_down'],petting:['touch_head','happy'],happy:['happy','wave_paw']}[action]||['idle_breathe'];
   const clip=names.map(n=>this.clips.find(c=>c.name.split('|').pop()===n)).find(Boolean)||this.clips[0];if(!clip)return;const next=this.mixer.clipAction(clip);if(next===this.active)return;next.reset().fadeIn(.25).play();this.active?.fadeOut(.25);this.active=next;
  }
  update(dt){this.mixer.update(Math.min(.05,dt));}
  snapshot(){return {x:this.root.position.x,z:this.root.position.z,yaw:this.root.rotation.y,action:this.action};}
 }
 root.PortalPets={Pet};
})(globalThis);
