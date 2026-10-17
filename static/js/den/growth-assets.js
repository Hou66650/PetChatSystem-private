/* Resolve a pet's current appearance and calendar stage to one public GLB. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.GrowthAssets=api;})(typeof window!=='undefined'?window:globalThis,function(){
 'use strict';
 const stages=new Set(['幼年','少年','成年']);
 function validate(manifest){
  if(!manifest||manifest.version!==1||!Array.isArray(manifest.stages))throw new Error('成长模型清单格式不正确');
  const keys=new Set();
  for(const item of manifest.stages){
   if(!Number.isInteger(item.pet)||item.pet<1||item.pet>4||!stages.has(item.stage)||!Number.isFinite(item.height)||item.height<=0||item.height>2||!item.assets)throw new Error('成长模型阶段配置不正确');
   const key=item.pet+':'+item.stage;if(keys.has(key))throw new Error('成长模型阶段重复');keys.add(key);
   for(const asset of Object.values(item.assets)){
    if(typeof asset.path!=='string'||!asset.path.startsWith('/static/models/')||!asset.path.endsWith('.glb')||!/^[0-9a-f]{64}$/.test(asset.sha256))throw new Error('成长模型资源记录不正确');
   }
  }
  return manifest;
 }
 function resolve(manifest,{petId,stage,appearance='default',custom=false}){
  if(custom)return {supported:false,reason:'private-preserved'};
  const item=manifest?.stages?.find(value=>value.pet===Number(petId)&&value.stage===stage);
  if(!item)return {supported:false,reason:'stage-unsupported'};
  const id=appearance||'default',asset=item.assets[id]||item.assets.default;
  if(!asset)return {supported:false,reason:'appearance-unsupported',appearance:id};
  return {supported:true,path:asset.path,sha256:asset.sha256,height:item.height,stage,appearance:id,key:item.pet+':'+stage+':'+id};
 }
 let pending=null;
 function load(version){
  if(!pending)pending=fetch('/static/data/pet-growth-models.json?v='+encodeURIComponent(version||''),{cache:'default'}).then(async response=>{
   if(!response.ok)throw new Error('成长模型清单加载失败');return validate(await response.json());
  }).catch(error=>{pending=null;throw error;});
  return pending;
 }
 return {load,resolve,validate};
});
