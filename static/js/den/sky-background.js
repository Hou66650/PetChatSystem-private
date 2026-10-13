/* Painted cloud backgrounds, with cover cropping and safe asynchronous theme changes. */
(function(root){
 'use strict';
 class SkyBackground {
  constructor(scene,canvas,baseUrl){
   this.scene=scene;this.canvas=canvas;this.baseUrl=baseUrl;this.mode=null;
   this.cache=new Map();this.pending=new Set();this.loader=new THREE.TextureLoader();
  }
  set(mode,fallback){
   this.mode=mode;
   const texture=this.cache.get(mode);
   this.scene.background=texture||new THREE.Color(fallback);
   this.canvas.dataset.sky=texture?mode:'fallback';
   if(texture){this.resize();return;}
   if(!mode||this.pending.has(mode))return;
   this.pending.add(mode);
   this.loader.load(this.baseUrl+'/'+mode+'.webp',loaded=>{
    loaded.encoding=THREE.sRGBEncoding;
    loaded.minFilter=THREE.LinearFilter;loaded.magFilter=THREE.LinearFilter;
    loaded.generateMipmaps=false;
    this.cache.set(mode,loaded);this.pending.delete(mode);
    if(this.mode===mode){this.scene.background=loaded;this.canvas.dataset.sky=mode;this.resize();}
   },undefined,()=>{
    this.pending.delete(mode);
    console.warn('云海背景暂未加载，使用天空底色');
   });
  }
  resize(){
   const texture=this.cache.get(this.mode);
   const width=this.canvas.clientWidth,height=this.canvas.clientHeight;
   if(!texture||!width||!height)return;
   const imageAspect=texture.image.width/texture.image.height,viewAspect=width/height;
   // Preserve cloud and moon proportions on phones and ultra-wide displays.
   const x=Math.min(1,viewAspect/imageAspect),y=Math.min(1,imageAspect/viewAspect);
   texture.repeat.set(x,y);texture.offset.set((1-x)/2,(1-y)/2);
   texture.updateMatrix();
  }
 }
 root.SkyBackground=SkyBackground;
})(window);
