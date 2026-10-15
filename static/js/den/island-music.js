(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.IslandMusic=api;})(typeof window!=='undefined'?window:globalThis,function(){
 'use strict';
 const tracks={sakura:'樱风小径',snow:'雪落星光',camp:'山岭暮歌',room:'雾林午后'};
 class Controller{
  constructor({audio=()=>new Audio(),notify=()=>{},version='1',volume=.3}={}){Object.assign(this,{audio,notify,version,volume});this.theme='sakura';this.enabled=false;this.hidden=false;this.duck=false;this.items=[];this.epoch=0;}
  setTheme(theme){if(!tracks[theme]||theme===this.theme)return;this.theme=theme;if(this.enabled&&!this.hidden)this.start();else this.emit();}
  emit(error=''){this.notify({enabled:this.enabled,theme:this.theme,title:tracks[this.theme],volume:this.volume,error});}
  release(item){item.progress?.cancel();item.audio.pause();item.audio.removeAttribute('src');item.audio.load();this.items=this.items.filter(x=>x!==item);}
  async start(){
   const token=++this.epoch;
   // Keep at most one old track while the selected one loads.
   for(const item of [...this.items])if(!item.ready)this.release(item);
   while(this.items.length>1)this.release(this.items[0]);
   const audio=this.audio(),item={audio,ready:false,level:0,target:0,progress:globalThis.PaitLoading?.start('正在准备小岛背景音乐')};
   audio.preload='none';audio.loop=true;audio.volume=0;audio.src='/static/audio/islands/'+this.theme+'.flac?v='+encodeURIComponent(this.version);
   this.items.push(item);
   audio.onerror=()=>{item.progress?.fail('背景音乐未能加载，请重试');if(token===this.epoch){this.stop();this.emit('音乐暂时无法播放，请重试');}};
   try{await audio.play();if(token!==this.epoch){if(this.items.includes(item))this.release(item);return;}
    item.progress?.done();item.ready=true;for(const old of this.items)old.target=old===item?1:0;this.emit();
   }catch(e){if(token===this.epoch){item.progress?.fail('音乐未能播放，请点击开启重试');this.stop();this.emit('未能播放音乐，请点击开启重试');}}
  }
  toggle(){if(this.enabled)this.stop();else{this.enabled=true;if(!this.hidden)this.start();this.emit();}}
  stop(){this.enabled=false;this.epoch++;for(const item of [...this.items])this.release(item);this.emit();}
  setVolume(value){this.volume=Math.max(0,Math.min(1,Number(value)||0));this.emit();}
  setHidden(hidden){if(this.hidden===hidden)return;this.hidden=hidden;this.epoch++;for(const item of [...this.items])this.release(item);if(!hidden&&this.enabled)this.start();}
  update(dt,duck=false){this.duck=duck;const step=Math.min(.1,Math.max(0,dt))/1.5;
   for(const item of [...this.items]){if(!item.ready)continue;item.level+=Math.max(-step,Math.min(step,item.target-item.level));
    const desired=item.level*this.volume*(duck?.12:1);item.audio.volume+=(desired-item.audio.volume)*(1-Math.exp(-Math.min(.1,dt)*9));
    if(item.target===0&&item.level<=0)this.release(item);
   }
  }
 }
 return {Controller,tracks};
});
