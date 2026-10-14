const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),THREE=require('../static/js/vendor/three.min.js');
let disposed=0,selected='1',notices=0;const pending=[],scene=new THREE.Scene();
const loader={begin(){return {};},glb(url){return new Promise(resolve=>pending.push({url,resolve}));}};
const context={THREE,performance,SelectedAssets:{disposeTree(){disposed++;}},PortalPets:{Pet:class{constructor(){this.root=new THREE.Group();}play(a){this.action=a;}update(){}}}};
vm.runInNewContext(fs.readFileSync('static/js/den/portal-visitors.js','utf8'),context);
const nav={nearest:p=>p,surfaceHeight:()=>0,segmentClear:()=>true};
const visitors=new context.PortalVisitors.Visitors({THREE,scene,loader,getPet:()=>({id:selected}),getNavigation:()=>nav,notify:()=>notices++});
const trip={id:'trip1',mine:false,kind:'neighbor',status:'active',hostPet:{id:'1'},petSpec:{name:'猫咪',model:'/cat.glb'},snapshot:{visitor:{x:1,z:1,yaw:1,action:'walk'}}};
const flush=()=>new Promise(r=>setImmediate(r));
(async()=>{
 visitors.sync([{...trip,mine:true},{...trip,hostPet:{id:'2'}}]);assert.equal(pending.length,0,'no loading on own departure or unselected host island');
 visitors.sync([trip]);assert.equal(pending.length,1);visitors.sync([trip]);assert.equal(pending.length,1,'polls do not duplicate loads');pending.shift().resolve({scene:new THREE.Group()});await flush();assert.equal(scene.children.length,1);assert.equal(notices,1);
 visitors.sync([{...trip,snapshot:{visitor:{x:2,z:1,yaw:2,action:'sniff'}}}]);visitors.update(.05);assert(visitors.pet.root.position.x>1);assert.equal(visitors.pet.action,'sniff');
 visitors.sync([{...trip,status:'returned'}]);assert.equal(scene.children.length,0);assert.equal(disposed,1,'return disposes visitor');
 visitors.sync([trip]);visitors.clear();selected='2';pending.shift().resolve({scene:new THREE.Group()});await flush();assert.equal(scene.children.length,0);assert.equal(disposed,2,'late model cannot leak into next island');
 selected='1';visitors.sync([trip]);pending.shift().resolve({scene:new THREE.Group()});await flush();visitors.sync([]);assert.equal(scene.children.length,0,'revoked or absent visit is removed');
 console.log('PASS host island visitor: selected assets, movement/animation sync, return, revocation and selection race');
})().catch(e=>{console.error(e);process.exitCode=1;});
