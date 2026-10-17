const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),THREE=require('../static/js/vendor/three.min.js');
const ctx={};vm.runInNewContext(fs.readFileSync('static/js/den/portal-transition.js','utf8'),ctx);
const model=new THREE.Group(),material=new THREE.MeshBasicMaterial(),originalPlane=new THREE.Plane();material.clippingPlanes=[originalPlane];material.clipIntersection=true;
model.add(new THREE.Mesh(new THREE.BoxGeometry(),material));model.position.set(1,0,1);model.rotation.y=.3;let calls=0;
const crossing=new ctx.PortalTransition.Crossing(THREE,model,{from:model.position,to:new THREE.Vector3(0,0,-1),gateZ:0,duration:1,onComplete:()=>calls++});
assert(crossing.from.distanceTo(new THREE.Vector3(1,0,1))===0);crossing.update(.1);assert(model.position.z<1);
crossing.dispose(true);assert.equal(model.position.z,1);assert.equal(model.rotation.y,.3);assert.equal(material.clippingPlanes[0],originalPlane);assert.equal(material.clipIntersection,true);crossing.update(.1);assert.equal(calls,0);
const complete=new ctx.PortalTransition.Crossing(THREE,model,{from:model.position,to:new THREE.Vector3(0,0,-1),gateZ:0,duration:1,onComplete:()=>calls++});for(let i=0;i<30;i++)complete.update(.1);assert.equal(calls,1);assert.equal(model.position.z,-1);complete.dispose();assert.equal(material.clippingPlanes[0],originalPlane);
console.log('PASS portal clipping: cloned start position, completion once, cancellation and shared material restoration');
