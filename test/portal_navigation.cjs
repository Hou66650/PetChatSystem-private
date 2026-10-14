const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),T=require('../static/js/vendor/three.min.js');
vm.runInNewContext(fs.readFileSync('static/js/vendor/GLTFLoader.js','utf8'),{THREE:T,console,TextDecoder,URL,Blob,self:{URL},setTimeout,clearTimeout});
T.TextureLoader.prototype.load=function(url,onLoad){const t=new T.Texture();queueMicrotask(()=>onLoad(t));return t;};
const context={THREE:T,console};vm.createContext(context);vm.runInContext(fs.readFileSync('static/js/den/portal-pets.js','utf8'),context);
const {Navigation}=require('../static/js/den/scene-navigation');
const layouts=[{...require('../static/js/den/sakura-river-layout'),radius:3.2,obstacles:[{x:-2.1,z:-1.5,r:.55},{x:2.25,z:-1.2,r:.38},{kind:'rect',x:0,z:-2.65,w:3.7,d:.26}]},require('../static/js/den/snow-haven-layout'),require('../static/js/den/mistwood-layout'),require('../static/js/den/alpine-layout')];
(async()=>{for(const [name,height] of [['petchat-shiba-v4/qiuqiu',.95],['petchat-husky-v3/xueqiu',1.05],['petchat-cat-v2/cat',.85],['petchat-shepherd-v2/shepherd',1.12]]){
 const b=fs.readFileSync('static/models/'+name+'.glb'),g=await new Promise((res,rej)=>new T.GLTFLoader().parse(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),'',res,rej)),pet=new context.PortalPets.Pet(T,g,{height});
 const box=new T.Box3().setFromObject(pet.root),radius=Math.hypot(box.max.x-box.min.x,box.max.z-box.min.z)/2+.015;
 for(const layout of layouts){const nav=new Navigation({...layout,bodyRadius:radius});const start=nav.nearest({x:0,z:0});assert(start,name+' has a safe arrival');assert(nav.nodes.filter(n=>n.valid).length>8);for(const p of [{x:-.6,z:0},{x:.6,z:0}]){const target=nav.nearest(p);assert(nav.route(start,target),name+' can meet on destination island');}}
 for(const action of ['walk','sniff','sleep','petting']){pet.play(action);pet.update(.05);pet.model.updateMatrixWorld(true);pet.model.traverse(o=>{if(o.isBone)assert(o.matrixWorld.elements.every(Number.isFinite));});}
 }console.log('PASS all four native GLBs: shared desktop/visitor animation adapter and sixteen island/body navigation combinations');
})().catch(e=>{console.error(e);process.exitCode=1});
