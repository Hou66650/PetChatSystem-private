const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const layout=require('../static/models/paw-commons-v2/navigation.json'),nav=require('../static/js/park-navigation.js').create(layout),F=require('../static/js/park-facilities.js'),{Agent}=require('../static/js/park-agent.js');
const THREE=require('../static/js/vendor/three.min.js');
vm.runInNewContext(fs.readFileSync('static/js/vendor/GLTFLoader.js','utf8'),{THREE,console,TextDecoder,URL,Blob,self:{URL},setTimeout,clearTimeout});
THREE.TextureLoader.prototype.load=function(url,onLoad){const t=new THREE.Texture();queueMicrotask(()=>onLoad(t));return t;};
(async()=>{
 const raw=fs.readFileSync('static/models/paw-commons-v2/play.glb');const gltf=await new Promise((resolve,reject)=>new THREE.GLTFLoader().parse(raw.buffer.slice(raw.byteOffset,raw.byteOffset+raw.byteLength),'',resolve,reject));gltf.scene.updateMatrixWorld(true);
 const structural=[];gltf.scene.traverse(o=>{if(o.isMesh&&!/leaf|flower|daisy|verbena|moss/i.test(o.material.name))structural.push(o);});
 for(const f of layout.facilities){
  const total=F.length(f),start=F.sample(f,0),end=F.sample(f,total);assert(nav.inside(start.x,start.z));assert(nav.inside(end.x,end.z));assert(nav.route({x:3,z:3},start).length);
  let maxY=0;
  for(let d=0;d<=total;d+=.18){const p=F.sample(f,d);maxY=Math.max(maxY,p.y);
   // Ray from just above authored feet checks real GLB support, including ramps/deck.
   const hits=[-.07,0,.07].flatMap(dz=>new THREE.Raycaster(new THREE.Vector3(p.x,p.y+.12,p.z+dz),new THREE.Vector3(0,-1,0),0,.28).intersectObjects(structural,true));
   assert(hits.length,`${f.id} unsupported feet at ${JSON.stringify(p)}`);
   // Central body clearance: no fixed structure through torso/head along the route.
   const blocked=[-.18,0,.18].flatMap(offset=>new THREE.Raycaster(new THREE.Vector3(p.x+Math.cos(p.yaw)*offset,p.y+.22,p.z-Math.sin(p.yaw)*offset),new THREE.Vector3(0,1,0),0,f.maxHeight-.22).intersectObjects(structural,true));
   assert(!blocked.length,`${f.id} body intersects ${blocked[0]?.object.material.name} at ${JSON.stringify(p)}`);
  }
  if(f.id==='bridge')assert(maxY>.5,'walk up onto actual bridge');
 }
 const a=new Agent({navigation:nav,random:()=>0});a.facilities=layout.facilities;a.height=1.12;
 let c=a.tick({now:0,dt:.25,pos:{x:3,z:3}});assert.equal(c.activity,'facility');assert.equal(a.plan[1].facility,'bridge','large dog never enters low tunnel');
 a.recent.set('bridge',0);a.plan=null;a.activity='idle';a.choose(1,{x:3,z:3},[]);assert.notEqual(a.activity,'facility');
 a.height=.85;a.recent.delete('facility');a.choose(1,{x:3,z:3},[]);assert.equal(a.plan[1].facility,'tunnel');
 a.plan=null;a.choose(100,{x:3,z:3},[{x:4,z:4,behavior:{facility:{id:'bridge'}}}]);assert.notEqual(a.activity,'facility','occupied west lane is not selected');
 console.log('PASS real GLB support/headroom, bridge height, reachable entry/exit, body size and occupancy decisions');
})().catch(e=>{console.error(e);process.exitCode=1;});
