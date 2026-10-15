/* Only the selected theme/time owns a decoded background and a pending request. */
(function(root){
 'use strict';
 class SkyBackground {
  constructor(scene,canvas,baseUrl){
   this.scene=scene;this.canvas=canvas;this.baseUrl=baseUrl;this.mode=null;
   this.key=null;this.texture=null;this.request=null;
  }
  release(){
   this.request?.abort();this.request=null;this.progress?.cancel();this.progress=null;
   if(this.texture){this.texture.dispose();this.texture.image?.close?.();this.texture=null;}
  }
  set(mode,fallback,baseUrl=this.baseUrl){
   const key=mode?`${baseUrl}/${mode}.webp`:null;
   if(key===this.key&&(this.texture||this.request)){this.resize();return;}
   this.release();this.key=key;this.mode=mode;
   this.scene.background=new THREE.Color(fallback);this.canvas.dataset.sky='fallback';
   if(!key)return;
   const request=new AbortController();this.request=request;const progress=this.progress=window.PaitLoading?.start('正在铺开天空背景');
   fetch(key,{signal:request.signal,paitQuiet:true}).then(r=>{if(!r.ok)throw new Error(`Sky HTTP ${r.status}`);return r.blob();})
    .then(blob=>{progress?.update('正在解析天空画面');return createImageBitmap(blob,{imageOrientation:'flipY',premultiplyAlpha:'none'});})
    .then(bitmap=>{
     if(request.signal.aborted||this.request!==request){bitmap.close();return;}
     const texture=new THREE.Texture(bitmap);texture.flipY=false;texture.encoding=THREE.sRGBEncoding;
     texture.minFilter=THREE.LinearFilter;texture.magFilter=THREE.LinearFilter;texture.generateMipmaps=false;texture.needsUpdate=true;
     this.texture=texture;this.request=null;this.scene.background=texture;this.canvas.dataset.sky=mode;this.resize();progress?.done();
    }).catch(error=>{if(error.name==='AbortError'||request.signal.aborted)progress?.cancel();else progress?.fail('天空背景暂未加载，已使用备用天空');
     if(this.request===request)this.request=null;
     if(error.name!=='AbortError'&&!request.signal.aborted)console.warn('Cloud background unavailable; using sky color');
    });
  }
  resize(){
   const texture=this.texture,width=this.canvas.clientWidth,height=this.canvas.clientHeight;
   if(!texture||!width||!height)return;
   const imageAspect=texture.image.width/texture.image.height,viewAspect=width/height;
   const x=Math.min(1,viewAspect/imageAspect),y=Math.min(1,imageAspect/viewAspect);
   texture.repeat.set(x,y);texture.offset.set((1-x)/2,(1-y)/2);texture.updateMatrix();
  }
 }
 root.SkyBackground=SkyBackground;
})(window);
