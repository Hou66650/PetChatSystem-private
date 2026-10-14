const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const THREE=require('../static/js/vendor/three.min.js');
// Geometry/bounds test only: bitmap decoding is covered by the real browser preview.
THREE.TextureLoader.prototype.load=function(url,onload){const t=new THREE.Texture();queueMicrotask(()=>onload(t));return t;};
vm.runInNewContext(fs.readFileSync('static/js/vendor/GLTFLoader.js','utf8'),{THREE,console,TextDecoder,URL,Blob,self:{URL},setTimeout,clearTimeout});
const parse=path=>new Promise((resolve,reject)=>{const b=fs.readFileSync(path);new THREE.GLTFLoader().parse(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),'',resolve,reject)});
(async()=>{
 const stage=await parse('static/models/petchat-snow-v2/snow.glb');let draws=0,triangles=0;
 stage.scene.updateMatrixWorld(true);stage.scene.traverse(o=>{if(!o.isMesh)return;draws+=Math.max(1,o.geometry.groups.length);triangles+=o.geometry.index.count/3;for(const n of o.geometry.attributes.position.array)assert(Number.isFinite(n))});
 assert(draws<=20);assert(triangles<150000);assert(fs.statSync('static/models/petchat-snow-v2/snow.glb').size<5e6);
 const box=new THREE.Box3().setFromObject(stage.scene);assert(box.min.y<-.9&&box.max.y>2);assert(box.max.x<3.4&&box.min.x> -3.4);
 const pet=await parse('static/models/petchat-husky-v2/xueqiu.glb');pet.scene.updateMatrixWorld(true);
 const bounds=new THREE.Box3().setFromObject(pet.scene);
 const template=fs.readFileSync('templates/den.html','utf8');
 const spec=template.match(/2:\s*\{[^\n]+/)[0];const h=Number(spec.match(/h:\s*([.\d]+)/)[1]);
 const radius=Math.hypot(bounds.max.x-bounds.min.x,bounds.max.z-bounds.min.z)*h/(bounds.max.y-bounds.min.y)/2+.015;
 const {Navigation}=require('../static/js/den/scene-navigation.js'),layout=require('../static/js/den/snow-haven-layout.js');
 const nav=new Navigation({...layout,bodyRadius:radius});assert(nav.isWalkable({x:0,z:0}));
 assert(nav.route({x:0,z:0},{x:.65,z:.5}));assert(nav.route({x:0,z:0},{x:-.5,z:-.3}));
 const ray=new THREE.Raycaster(new THREE.Vector3(0,3,0),new THREE.Vector3(0,-1,0));
 const hits=ray.intersectObject(stage.scene,true);assert(hits.length);assert(Math.abs(hits[0].point.y-.018)<.002,'Actual snow surface agrees with navigation floor');
 console.log(JSON.stringify({draws,triangles,huskyBodyRadius:radius,snowFloor:hits[0].point.y}));
})().catch(e=>{console.error(e);process.exitCode=1});
