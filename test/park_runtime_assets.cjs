const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),zlib=require('node:zlib'),crypto=require('node:crypto');
const THREE=require('../static/js/vendor/three.min.js');
vm.runInNewContext(fs.readFileSync('static/js/vendor/GLTFLoader.js','utf8'),{THREE,console,TextDecoder,URL,Blob,self:{URL},setTimeout,clearTimeout});
THREE.TextureLoader.prototype.load=function(url,onLoad){const t=new THREE.Texture();queueMicrotask(()=>onLoad(t));return t;};
const parse=b=>new Promise((resolve,reject)=>new THREE.GLTFLoader().parse(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),'',resolve,reject));
(async()=>{
 const report=JSON.parse(fs.readFileSync('static/models/paw-commons-v2/runtime-report.json'));
 for(const tier of ['preview','play']){
  const file='static/models/paw-commons-v2/'+tier+'.glb',raw=fs.readFileSync(file),stats=report.tiers[tier];
  assert.deepEqual(zlib.gunzipSync(fs.readFileSync(file+'.gz')),raw);
  assert.equal(crypto.createHash('sha256').update(raw).digest('hex'),stats.sha256);
  const {scene}=await parse(raw);scene.updateMatrixWorld(true);let triangles=0,meshes=0;
  scene.traverse(o=>{if(!o.isMesh)return;meshes++;const g=o.geometry;triangles+=(g.index?.count||g.attributes.position.count)/3;for(const a of Object.values(g.attributes))assert([...a.array].every(Number.isFinite));});
  assert.equal(triangles,stats.triangles);assert.equal(meshes,stats.meshes);assert(meshes<=20);assert(triangles<(tier==='preview'?180000:470000));
  // The promenade must remain an annulus after reduction, never span the lawn.
  const gravel=[];scene.traverse(o=>{if(o.isMesh&&o.material.name==='Warm gravel')gravel.push(o);});assert(gravel.length);
  for(let x=-7;x<=7;x++)for(let z=-5;z<=5;z++){
   if((x/8)**2+(z/6)**2>1)continue;
   const ray=new THREE.Raycaster(new THREE.Vector3(x,1,z),new THREE.Vector3(0,-1,0));
   assert.equal(ray.intersectObjects(gravel,true).length,0,`${tier}: gravel crosses lawn at ${x},${z}`);
   assert(ray.intersectObject(scene,true).some(h=>Math.abs(h.point.y)<.03),'lawn supports walking area');
  }
  console.log('PASS runtime',tier,stats);
 }
})().catch(e=>{console.error(e);process.exitCode=1;});
