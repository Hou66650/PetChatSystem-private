const assert=require('node:assert/strict');
const {Controller}=require('../static/js/den/toy-workshop.js');
let active=false,entered=0,exited=0,resolveEnter;
const wrap={requestFullscreen(){entered++;return new Promise(resolve=>resolveEnter=()=>{document.fullscreenElement=wrap;resolve();});}};
global.document={body:{classList:{toggle(name,on){if(name==='toy-immersive')active=on;}}},getElementById:()=>wrap,fullscreenEnabled:true,fullscreenElement:null,exitFullscreen(){exited++;this.fullscreenElement=null;return Promise.resolve();}};
Object.defineProperty(global,'navigator',{value:{userActivation:{isActive:false}},configurable:true});
const flush=()=>new Promise(r=>setImmediate(r));
(async()=>{
 const w=Object.create(Controller.prototype);
 w.immersiveMode(true);assert(active);assert.equal(entered,0,'camera falls back to viewport without activation');
 w.immersiveMode(false);assert(!active);
 navigator.userActivation.isActive=true;
 w.immersiveMode(true);resolveEnter();await flush();assert(w.ownsFullscreen);
 w.immersiveMode(false);assert.equal(exited,1);assert(!active);
 document.fullscreenElement={userOwned:true};w.immersiveMode(true);w.immersiveMode(false);assert.equal(exited,1,'leave existing user fullscreen intact');
 document.fullscreenElement=null;w.immersiveMode(true);w.immersiveMode(false);resolveEnter();await flush();assert.equal(exited,2,'late fullscreen entry after release exits again');
 wrap.requestFullscreen=()=>Promise.reject(new Error('unsupported'));w.immersiveMode(true);await flush();assert(active,'browser refusal retains immersion');w.immersiveMode(false);
 // Exercise the real render lifecycle with no HUD, so state transitions still restore the page.
 w.held={state:'held'};w.render();assert(active);
 w.held.state='playing';w.render();assert(!active,'throw restores controls');
 w.held=null;w.render();assert(!active);
 w.toggleFullscreen();assert(w.manualFullscreen&&w.fullWanted);w.held={state:'held'};w.render();w.held=null;w.render();assert(w.fullWanted,'manual fullscreen survives toy release');w.toggleFullscreen();assert(!w.fullWanted);
 let animations=0,cancelled=0;w.a={canvas:{animate(frames,options){animations++;assert.equal(options.duration,360);assert.equal(frames.at(-1).transform,'scale(1)');return {cancel(){cancelled++;}};}}};w.animateViewport();w.animateViewport();assert.equal(animations,2);assert.equal(cancelled,1);global.matchMedia=()=>({matches:true});w.animateViewport();assert.equal(animations,2,'reduced motion skips animation');
 console.log('PASS held/throw/reset immersion, camera fallback, owned fullscreen, denial and late entry cleanup');
})();
