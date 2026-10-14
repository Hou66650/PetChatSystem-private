/* Adaptive render cost; never substitutes or preloads pet assets. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.RenderBudget=api;})(typeof window!=='undefined'?window:globalThis,function(){
 'use strict';
 const levels=[
  {name:'细腻',ratio:1.5,shadow:1024,shadowHz:20,glass:true},
  {name:'均衡',ratio:1,shadow:1024,shadowHz:12,glass:true},
  {name:'流畅',ratio:.85,shadow:512,shadowHz:8,glass:false}
 ];
 class Policy {
  constructor(mode='auto',low=false){this.mode=mode;this.level=low?1:0;this.reset();this.setMode(mode);}
  reset(){this.frames=0;this.elapsed=0;this.fps=0;this.slow=0;this.fast=0;this.windows=0;}
  setMode(mode){this.mode=['auto','high','low'].includes(mode)?mode:'auto';this.level=this.mode==='high'?0:this.mode==='low'?2:this.level;this.reset();}
  sample(seconds){
   if(!Number.isFinite(seconds)||seconds<=0)return false;
   this.elapsed+=seconds;this.frames++;
   if(this.elapsed<1.5)return false;
   this.fps=this.frames/this.elapsed;this.elapsed=0;this.frames=0;this.windows++;
   if(this.mode!=='auto'||this.windows<3)return false; // skip startup compilation
   this.slow=this.fps<38?this.slow+1:0;this.fast=this.fps>56?this.fast+1:0;
   if(this.slow>=2&&this.level<2){this.level++;this.slow=this.fast=0;return true;}
   if(this.fast>=10&&this.level>0){this.level--;this.slow=this.fast=0;return true;}
   return false;
  }
 }
 class Controller {
  constructor(renderer,sun,{mode='auto',low=false}={}){
   this.renderer=renderer;this.sun=sun;this.policy=new Policy(mode,low);this.lastShadow=-Infinity;
   const gl=renderer.getContext(), ext=gl.getExtension('WEBGL_debug_renderer_info');
   this.device=ext?gl.getParameter(ext.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER);
   this.software=/swiftshader|llvmpipe|software|basic render/i.test(this.device);
   if(this.software&&mode==='auto')this.policy.level=2;
   this.apply();
  }
  apply(){
   const r=this.renderer,s=this.sun.shadow,p=levels[this.policy.level];
   // DPR cap plus pixel budget keeps a 4K display from silently quadrupling work.
   const c=r.domElement,area=Math.max(1,c.clientWidth*c.clientHeight);
   const ratio=Math.min(typeof devicePixelRatio==='number'?devicePixelRatio:1,p.ratio,Math.sqrt(2400000/area));
   r.setPixelRatio(ratio);r.setSize(Math.max(1,c.clientWidth),Math.max(1,c.clientHeight),false);
   if(s.mapSize.x!==p.shadow){s.mapSize.set(p.shadow,p.shadow);if(s.map){s.map.dispose();s.map=null;}}
   r.shadowMap.autoUpdate=false;r.shadowMap.needsUpdate=true;this.lastShadow=-Infinity;
   if(typeof document!=='undefined')document.getElementById('den-wrap')?.classList.toggle('render-simple-glass',!p.glass);
  }
  setMode(mode){this.policy.setMode(mode);this.apply();}
  frame(dt,now){if(this.policy.sample(dt))this.apply();if(now-this.lastShadow>=1000/levels[this.policy.level].shadowHz){this.renderer.shadowMap.needsUpdate=true;this.lastShadow=now;}}
  reset(){this.policy.reset();this.lastShadow=-Infinity;}
  stats(){return {device:this.device,software:this.software,fps:this.policy.fps,level:levels[this.policy.level].name,ratio:this.renderer.getPixelRatio(),calls:this.renderer.info.render.calls,triangles:this.renderer.info.render.triangles};}
 }
 return {Policy,Controller,levels};
});
