const assert=require('node:assert/strict');
const fs=require('node:fs');
const THREE=require('../static/js/vendor/three.min.js');
const template=fs.readFileSync('templates/den.html','utf8');
const start=template.indexOf('        function resize() {');
const end=template.indexOf('        // S1-11/S1-12：旋转',start);
assert(start>=0&&end>start);
const canvas={clientWidth:1280,clientHeight:652,width:1280,height:652};
let ratio=1,allocations=0,skyUpdates=0;
const renderer={getPixelRatio:()=>ratio,setSize(w,h){allocations++;canvas.width=Math.floor(w*ratio);canvas.height=Math.floor(h*ratio);}};
const camera=new THREE.PerspectiveCamera(42,1,.1,100);
const resize=Function('canvas','renderer','camera','skyBackground',template.slice(start,end)+';return resize;')(canvas,renderer,camera,{resize(){skyUpdates++;}});
function verify(){
 resize();assert.equal(camera.aspect,canvas.clientWidth/canvas.clientHeight);
 const x=new THREE.Vector3(1,0,-5).project(camera),y=new THREE.Vector3(0,1,-5).project(camera);
 assert(Math.abs(x.x*canvas.clientWidth-y.y*canvas.clientHeight)<1e-8,'equal world lengths retain equal pixel lengths');
}
verify();assert.equal(allocations,0,'initial buffer can already match before camera is updated');
for(const [w,h,dpr] of [[1920,960,1.28],[390,780,.85],[844,330,1],[1280,652,1.5]]){
 canvas.clientWidth=w;canvas.clientHeight=h;ratio=dpr;
 renderer.setSize(w,h); // quality controller updates first
 const before=allocations;verify();assert.equal(allocations,before);
}
canvas.clientWidth=900;canvas.clientHeight=700;verify();assert.equal(canvas.width,1350);
const saved=camera.aspect;canvas.clientHeight=0;resize();assert.equal(camera.aspect,saved,'hidden canvas cannot poison projection');
assert.equal(skyUpdates,6);
console.log('PASS initial pre-sized buffer, DPR/quality changes, portrait/landscape, normal resize, hidden canvas, undistorted projection');
