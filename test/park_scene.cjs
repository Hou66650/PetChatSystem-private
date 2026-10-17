const assert=require('node:assert/strict'),T=require('../static/js/vendor/three.min.js'),P=require('../static/js/park-scene.js');
const park=P.create(T);let triangles=0,meshes=0;park.updateMatrixWorld(true);
park.traverse(o=>{if(!o.isMesh)return;meshes++;const g=o.geometry;triangles+=(g.index?.count||g.attributes.position.count)/3;assert([...g.attributes.position.array].every(Number.isFinite));});
assert(triangles<30000,'new park has a bounded geometry budget');
assert.equal(P.positions.length,5);assert(P.positions[4][2]>P.positions[0][2],'palm below the four toes');
assert(P.inside(0,0));assert(!P.inside(NaN,0));assert(!P.inside(9,0));
for(let i=0;i<36;i++){const a=i*Math.PI/18;const ray=new T.Raycaster(new T.Vector3(Math.cos(a)*7.8,10,Math.sin(a)*5.8),new T.Vector3(0,-1,0));assert(ray.intersectObject(park,true).some(h=>Math.abs(h.point.y-.02)<.01),'all walking perimeter has lawn support');}
console.log('PASS park finite geometry, lawn boundary support, five-island layout:',triangles,'triangles',meshes,'meshes');
