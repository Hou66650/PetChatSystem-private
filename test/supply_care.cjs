// Run the actual den integration against real GLB skeletons and navigation.
const fs=require('fs'),vm=require('vm'),assert=require('assert/strict'),T=require('../static/js/vendor/three.min.js');
const {Navigation}=require('../static/js/den/scene-navigation'),{Controller:Move}=require('../static/js/den/pet-locomotion'),{Controller:Life}=require('../static/js/den/cat-life'),{bowl}=require('../static/js/den/supply-delivery');
vm.runInNewContext(fs.readFileSync('static/js/vendor/GLTFLoader.js','utf8'),{THREE:T,console,TextDecoder,URL,Blob,self:{URL},setTimeout,clearTimeout});T.TextureLoader.prototype.load=function(url,cb){const t=new T.Texture();queueMicrotask(()=>cb(t));return t;};
const source=fs.readFileSync('templates/den.html','utf8'),code=source.slice(source.indexOf('        function finishSupplyCare'),source.indexOf("        for(const [id,action] of [['btn-cat-eat'"));
const load=p=>new Promise((r,j)=>{const b=fs.readFileSync(p);new T.GLTFLoader().parse(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),'',r,j);});
(async()=>{
 for(const [id,file] of [[3,'petchat-cat-v3/cat.glb'],[1,'petchat-shiba-v3/qiuqiu.glb']]){
  // Obtain the project's actual dog path rather than assume a renamed model filename.
  const modelFile=id===3?file:source.match(/1:\s*\{[^\n]*glb:\s*'\/static\/models\/([^'?]+)/)?.[1];assert(modelFile);
  const gltf=await load('static/models/'+modelFile),model=new T.Group();model.add(gltf.scene);const scene=new T.Scene();scene.add(model);
  const box=new T.Box3().setFromObject(gltf.scene);gltf.scene.scale.setScalar(.85/(box.max.y-box.min.y));gltf.scene.updateMatrixWorld(true);const bounds=new T.Box3().setFromObject(gltf.scene);gltf.scene.position.y=-bounds.min.y;
  const nav=new Navigation({...require('../static/js/den/mistwood-layout'),bodyRadius:.619}),anim={state:'idle'},mix=new T.AnimationMixer(gltf.scene),move=new Move({navigation:nav,model,animate(){},rest(){}});move.autonomous=false;
  const life=id===3?new Life(T,model,move):null;const context={THREE:T,scene,petModel:model,locomotion:move,currentPetId:id,catHomeReady:id===3,catLife:life,spawnBusy:false,supplyCare:null,supplyDelivery:null,COMPANION_SCOPE:'fixture',portals:null,grabbed:false,dropping:false,anim,catAgent:{hunger:.8,interrupt(){},saveNeeds(){},emit(){}},toyWorkshop:{held:null,takeSupply:()=>true},window:{addEventListener(){}},toast(){},showBubble(){},movementBlocked:()=>false,interactionBusy:()=>false,performing:()=>false,SelectedAssets:{disposeTree:()=>{}},SupplyDelivery:{bowl,Controller:class{constructor(a){this.a=a;}}},setAnim(state){anim.state=state;move.interrupt();mix.stopAllAction();const clip=gltf.animations.find(a=>a.name===(state==='eat'?'eat':'idle_breathe'));if(clip)mix.clipAction(clip).play();}};
  vm.createContext(context);vm.runInContext(code,context);
  for(const effect of ['eat','drink']){context.catAgent.hunger=.8;const p=context.supplyDelivery.a.use({item:{id:'kibble',kind:'food',effect,name:'测试补给'}});let serving=false;
   for(let i=0;i<2700&&context.supplyCare;i++){life?.beforeFrame();vm.runInContext('updateSupplyCare(.02)',context);move.update(.02,context.supplyCare?.phase==='using');mix.update(.02);model.position.y=nav.surfaceHeight(model.position);life?.pose(.02,anim.state);scene.updateMatrixWorld(true);assert(nav.isWalkable(model.position));if(context.supplyCare?.bowl?.visible){serving=true;assert(context.supplyCare.bowl.position.toArray().every(Number.isFinite));}}
   assert.equal(await p,true,'delivery finishes');assert(serving,'serving dish displayed');assert(Math.abs(context.catAgent.hunger-(effect==='drink'?.8:.45))<1e-8,'water does not change hunger');assert.equal(context.supplyCare,null);
  }
  const p=context.supplyDelivery.a.use({item:{kind:'food',effect:'eat',name:'取消'}});context.petModel=new T.Group();vm.runInContext('updateSupplyCare(.02)',context);assert.equal(await p,false,'switching pets defers unconsumed delivery');
 }
 console.log('PASS actual cat/dog supply care: safe route, feeding/drinking, bowl placement, hunger, cleanup, pet-switch cancellation');
})().catch(e=>{console.error(e);process.exitCode=1;});
