const fs=require('fs'),vm=require('vm'),assert=require('assert'),THREE=require('../static/js/vendor/three.min.js');
const F=require('../static/js/den/farm-garden'),L=require('../static/data/farm-layout.json'),base=require('../static/js/den/mistwood-layout'),T=require('../static/js/den/toy-workshop'),P=require('../static/js/den/farm-placement'),map=require('../static/data/farm-placement.json'),{Navigation}=require('../static/js/den/scene-navigation');
vm.runInNewContext(fs.readFileSync('static/js/vendor/GLTFLoader.js','utf8'),{THREE,console,TextDecoder,URL,Blob,self:{URL},setTimeout,clearTimeout});
THREE.TextureLoader.prototype.load=function(url,done){const t=new THREE.Texture();queueMicrotask(()=>done(t));return t;};
const path='static/models/petchat-meadow-v1/mistwood-meadow.glb',buf=fs.readFileSync(path);
new THREE.GLTFLoader().parse(buf.buffer.slice(buf.byteOffset,buf.byteOffset+buf.byteLength),'',g=>{try{
 g.scene.updateMatrixWorld(true);let samples=0;
 const config=F.navigation(T.navigation('room',base),L);
 for(const radius of [.36,.619]){
  const nav=new Navigation({...config,bodyRadius:radius});
  // Regression: a smoothed line used to graze the concave old farm/main-island
  // seam, passing coarse samples and then stopping midway through animation.
  let previous={x:-5,z:6.4};const continuous=nav.route(previous,{x:10,z:8});assert(continuous);
  for(const point of continuous){const n=Math.ceil(Math.hypot(point.x-previous.x,point.z-previous.z)/.002);for(let i=0;i<=n;i++)assert(nav.isWalkable({x:previous.x+(point.x-previous.x)*i/n,z:previous.z+(point.z-previous.z)*i/n}),'continuous terrace clearance');previous=point;}
  for(const goal of L.expansion.landmarks){const from={x:0,z:0},route=nav.route(from,goal);assert(route,'reach '+goal.id);assert(nav.route(goal,from),'return from '+goal.id);let a=from;
   for(const b of route){const n=Math.ceil(Math.hypot(a.x-b.x,a.z-b.z)/.18);for(let i=1;i<=n;i++){
    const p={x:a.x+(b.x-a.x)*i/n,z:a.z+(b.z-a.z)*i/n};assert(nav.isWalkable(p));if(p.x<5||p.z<2.4)continue;
    const hits=new THREE.Raycaster(new THREE.Vector3(p.x,.7,p.z),new THREE.Vector3(0,-1,0)).intersectObject(g.scene,true).filter(h=>!/blade|leaf|leaves|Moss|flower|petal|Pollen|Cedar_sprays|Young_leaves/i.test(h.object.material?.name||''));
    assert(hits.length,'ground exists');assert(Math.abs(hits[0].point.y-nav.surfaceHeight(p))<.045,JSON.stringify({p,height:hits[0].point.y,mesh:hits[0].object.name}));samples++;
   }a=b;}
  }
  for(const tree of L.expansion.trees)assert(!nav.isWalkable(tree));
  for(const p of [{x:8,z:1.8},{x:20,z:8},{x:15,z:-4},{x:10,z:15}])assert(!nav.isWalkable(p),'edge/water exclusion');
 }
 let seams=0;
 for(let x=4;x<8;x+=.21)for(let z=3;z<7.6;z+=.23){
  const floor=new THREE.Raycaster(new THREE.Vector3(x,.06,z),new THREE.Vector3(0,-1,0)).intersectObject(g.scene,true).filter(h=>['Meadow_living_turf','Forest_floor'].includes(h.object.material?.name));
  assert(new Set(floor.map(h=>h.object.material.name)).size<=1,'no coincident lawn sheets');seams++;
 }
 for(const container of ['soil','pot'])assert.equal(P.validate(map,{x:11.5,z:8,yaw:0,species:'cosmos',container}),'');
 for(const [x,z] of L.expansion.loop)assert(P.validate(map,{x,z,yaw:0,species:'cosmos',container:'pot'}),'walkway stays clear');
 assert.deepEqual(map.domains.slice(-2),L.expansion.domains);assert.deepEqual(map.soil.slice(-2),L.expansion.domains);
 console.log('PASS meadow:',samples,'physical route samples,',seams,'seam checks; both cat sizes, return paths, water/trees/edge exclusions and placement parity');
}catch(e){console.error(e);process.exitCode=1;}},e=>{console.error(e);process.exitCode=1});
