// Regression for camera-dependent z-fighting where the farm meets the old lawn.
// Inspect shipped triangles, not source constants or a material-offset workaround.
const fs=require('fs'),vm=require('vm'),assert=require('assert'),THREE=require('../static/js/vendor/three.min.js');
vm.runInNewContext(fs.readFileSync('static/js/vendor/GLTFLoader.js','utf8'),{THREE,console,TextDecoder,URL,Blob,self:{URL},setTimeout,clearTimeout});
THREE.TextureLoader.prototype.load=function(url,done){const t=new THREE.Texture();queueMicrotask(()=>done(t));return t;};
const path=process.argv[2]||'static/models/petchat-farm-v1/mistwood-farm.glb',buf=fs.readFileSync(path);
new THREE.GLTFLoader().parse(buf.buffer.slice(buf.byteOffset,buf.byteOffset+buf.byteLength),'',g=>{
 try{
  g.scene.updateMatrixWorld(true);let count=0;
  for(let x=-8.23;x<-3.51;x+=.173)for(let z=3.043;z<7.39;z+=.167){
   const hits=new THREE.Raycaster(new THREE.Vector3(x,.07,z),new THREE.Vector3(0,-1,0)).intersectObject(g.scene,true);
   const ground=hits.filter(h=>h.point.y>.024&&h.point.y<.031&&['Forest_floor','Garden_fine_gravel','Garden_weathered_limestone'].includes(h.object.material?.name));
   const layers=[...new Set(ground.map(h=>h.object.material.name))];
   assert.equal(layers.length,1,JSON.stringify({x,z,layers,problem:'overlapping or missing ground at farm/lawn join'}));
   if(Math.hypot(x,z)<7.83)assert.equal(layers[0],'Forest_floor','preserve original lawn instead of covering it');
   count++;
  }
  console.log('PASS farm seam: one visible ground material at',count,'join samples; original lawn preserved');
 }catch(e){console.error(e.message);process.exitCode=1;}
},e=>{console.error(e);process.exitCode=1;});
