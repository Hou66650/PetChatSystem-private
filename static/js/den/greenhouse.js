(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.Greenhouse=api;})(typeof window!=='undefined'?window:globalThis,function(){
 'use strict';
 const day=date=>new Date(date).toLocaleDateString('sv-SE');
 const hour=(date,scene)=>({night:23,morning:7,day:12,dusk:18}[scene]??new Date(date).getHours());
 function lighting(h,distance){
  const dusk=Math.max(0,Math.min(1,(h-16)/2));
  const level=h<6?.16:h<16?0:h<22?.7*dusk:.22;
  return {intensity:level,warmth:Math.max(0,1-distance/3)};
 }
 class Garden{
  constructor({scope,storage=globalThis.localStorage,now=()=>Date.now()}){
   this.key='pait-greenhouse:'+scope;this.storage=storage;this.now=now;this.state={plants:{},cosmetics:{night:false,seasonal:false,lace:false,plush:false}};
   try{const s=JSON.parse(storage?.getItem(this.key)||'{}');for(const id of ['grass','catnip']){
    const p=s.plants?.[id];if(p)this.state.plants[id]={growth:Math.max(0,Math.min(2,Math.floor(Number(p.growth)||0))),water:/^\d{4}-\d{2}-\d{2}$/.test(p.water)?p.water:'',touch:/^\d{4}-\d{2}-\d{2}$/.test(p.touch)?p.touch:''};
   }for(const k of Object.keys(this.state.cosmetics))this.state.cosmetics[k]=s.cosmetics?.[k]===true;}catch(e){}
   for(const id of ['grass','catnip'])this.state.plants[id]??={growth:0,water:'',touch:''};this.rollover();
  }
  save(){try{this.storage?.setItem(this.key,JSON.stringify(this.state));this.persisted=true;}catch(e){this.persisted=false;}}
  rollover(){const today=day(this.now());let changed=false;for(const p of Object.values(this.state.plants))if(p.water&&p.water<today){p.growth=Math.min(2,p.growth+1);p.water='';changed=true;}if(changed)this.save();return changed;}
  water(id){this.rollover();const p=this.state.plants[id];if(!p)return false;const today=day(this.now());if(p.water===today)return false;p.water=today;this.save();return true;}
  interact(id,action){if(!((id==='grass'&&action==='nibble')||(id==='catnip'&&action==='sniff')))return false;this.rollover();const p=this.state.plants[id],today=day(this.now());if(p.touch===today)return false;p.touch=today;p.growth=Math.min(2,p.growth+1);this.save();return true;}
  cosmetic(id,value){if(!(id in this.state.cosmetics))return;this.state.cosmetics[id]=!!value;this.save();}
 }
 class View{
  constructor(THREE,scene,options){
   this.THREE=THREE;this.scene=scene;this.garden=new Garden(options);this.nodes=[];this.lamps=[];this.glow=[];this.elapsed=31;this.tint=new THREE.Color();this.baseColor=new THREE.Color(0xffdfb2);this.nearColor=new THREE.Color(0xffb865);
   scene.traverse(o=>{if(o.userData.garden_plant||o.userData.garden_cosmetic)this.nodes.push(o);if(o.isMesh&&o.material.name==='Garden_lamp')this.glow.push(o.material);});
   for(const x of [2,4]){const lamp=new THREE.PointLight(0xffcf8e,0,4.2);lamp.position.set(x,2.26,-3.1);scene.add(lamp);this.lamps.push(lamp);}
   this.refresh();
  }
  refresh(){
   const {plants,cosmetics}=this.garden.state,month=new Date(this.garden.now()).getMonth();this.month=month;
   for(const o of this.nodes){
    const id=o.userData.garden_plant;if(id){o.visible=o.userData.growth_layer<=plants[id].growth;
     if(id==='grass'&&/jade|lime/.test(o.material.name)){
      if(!o.userData.gardenBaseColor){o.material=o.material.clone();o.userData.gardenBaseColor=o.material.color.clone();}
      o.material.color.copy(o.userData.gardenBaseColor);if(cosmetics.seasonal)o.material.color.lerp(new this.THREE.Color(month>=8&&month<=10?0xb69a45:month<2||month===11?0x8eb5a0:0x98bb52),.38);
     }
    }else o.visible=!!cosmetics[o.userData.garden_cosmetic];
   }
  }
  update(dt,position,scene){
   this.elapsed+=dt;if(this.elapsed>30||scene!==this.lastScene){this.elapsed=0;this.lastScene=scene;this.h=hour(this.garden.now(),scene);const grown=this.garden.rollover();if(grown||this.month!==new Date(this.garden.now()).getMonth())this.refresh();}
   const h=this.h,d=position?Math.hypot(position.x-3,position.z+3.4):10;
   const light=lighting(h,d),color=this.tint.copy(this.baseColor).lerp(this.nearColor,light.warmth),k=1-Math.exp(-dt*2);
   for(const lamp of this.lamps){lamp.intensity+=(light.intensity-lamp.intensity)*k;lamp.color.lerp(color,k);}
   for(const m of this.glow){m.emissiveIntensity+=(light.intensity*1.8-m.emissiveIntensity)*k;}
   for(const o of this.nodes)if(o.userData.garden_cosmetic==='night')o.visible=this.garden.state.cosmetics.night&&(h>=17||h<6);
  }
  completed(goal){if(this.garden.interact(goal.target,goal.action))this.refresh();}
 }
 return {Garden,View,lighting,day,hour};
});
