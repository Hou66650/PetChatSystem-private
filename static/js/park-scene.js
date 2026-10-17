/* Public park assets derived from the detailed master; original four islands stay intact. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.PetParkScene=api;})(globalThis,function(){
 'use strict';
 const positions=[[-15,0,0],[-6,1,-10],[6,1,-10],[15,0,0],[0,-.6,11]];
 function create(T){
  const group=new T.Group(),mats={};
  for(const [k,c] of Object.entries({grass:0x829b63,edge:0x536e50,stone:0x9b9b82,path:0xe6c477,cream:0xf4eee0,wood:0xb18c60,teal:0x527f77,rose:0xc28270,water:0x78b9b7,dark:0x3e5147}))mats[k]=new T.MeshStandardMaterial({color:new T.Color(c).convertSRGBToLinear(),roughness:.88});
  function mesh(g,m,x,y,z){const o=new T.Mesh(g,mats[m]);o.position.set(x,y,z);group.add(o);return o;}
  const box=(w,h,d,m,x,y,z)=>mesh(new T.BoxGeometry(w,h,d),m,x,y,z);
  const cyl=(r,h,m,x,y,z)=>mesh(new T.CylinderGeometry(r,r,h,20),m,x,y,z);
  const shape=new T.Shape();shape.moveTo(0,8);shape.bezierCurveTo(-5,10,-12,6,-11,-1);shape.bezierCurveTo(-11,-8,-6,-10,0,-8);shape.bezierCurveTo(6,-10,11,-8,11,-1);shape.bezierCurveTo(12,6,5,10,0,8);
  const soil=mesh(new T.ExtrudeGeometry(shape,{depth:1.6,bevelEnabled:true,bevelSize:.55,bevelThickness:.4,bevelSegments:2,steps:1,curveSegments:20}),'edge',0,-2.1,0);soil.rotation.x=-Math.PI/2;
  // Faceted floating rock base ties the new island to the existing landscapes.
  for(let i=0;i<28;i++){const a=i/28*Math.PI*2,rock=mesh(new T.DodecahedronGeometry(.8+(i%4)*.12,0),'stone',Math.cos(a)*9.8,-1.4-(i%3)*.17,Math.sin(a)*7.2);rock.scale.set(1.4,1.2,.85);rock.rotation.y=a;}
  const lawn=mesh(new T.ShapeGeometry(shape,28),'grass',0,.02,0);lawn.rotation.x=-Math.PI/2;
  const track=mesh(new T.RingGeometry(8.9,9.65,96),'path',0,.04,0);track.rotation.x=-Math.PI/2;track.scale.y=.78;
  const border=mesh(new T.RingGeometry(9.7,9.77,96),'cream',0,.045,0);border.rotation.x=-Math.PI/2;border.scale.y=.78;
  // Small paw inlays on the circular promenade; repeated geometry/materials.
  const pad=new T.CircleGeometry(.12,10),toe=new T.CircleGeometry(.055,8);
  for(let i=0;i<20;i++){const a=i/20*Math.PI*2,x=Math.cos(a)*9.25,z=Math.sin(a)*7.2;
   const p=mesh(pad,'cream',x,.06,z);p.rotation.x=-Math.PI/2;
   for(let n=0;n<3;n++){const q=mesh(toe,'cream',x+(n-1)*.12,.065,z-.18);q.rotation.x=-Math.PI/2;}}
  // Play equipment sits outside the unobstructed multiplayer lawn.
  for(let i=0;i<4;i++){const hoop=mesh(new T.TorusGeometry(.65,.07,6,24,Math.PI),'cream',-4+i*1.35,.1,-7.25);}
  box(2.8,.18,.75,'wood',-7,.7,-5.5).rotation.z=.16;
  cyl(.2,.8,'teal',-7,.4,-5.5);
  const tunnel=mesh(new T.CylinderGeometry(.65,.65,2,24,1,true),'teal',6.8,.65,-5.6);tunnel.rotation.z=Math.PI/2;
  for(const x of [5.8,7.8]){const trim=mesh(new T.TorusGeometry(.65,.08,6,24),'cream',x,.65,-5.6);trim.rotation.y=Math.PI/2;}
  for(let i=0;i<3;i++)cyl(.45,.18+i*.12,'wood',-3+i*1.1,.09+i*.06,-7.7);
  // Quiet corner, drinking bowls, shaded benches and a toy basket.
  for(const x of [-8,8]){box(2,.15,.65,'wood',x,.65,3.8);for(const dx of [-.75,.75])box(.12,.65,.4,'dark',x+dx,.32,3.8);box(2,.55,.12,'wood',x,1,4.1);}
  for(const x of [5.8,6.7]){cyl(.32,.15,'cream',x,.08,5.3);cyl(.25,.01,'water',x,.16,5.3);}
  box(1.2,.35,.7,'wood',-5,.18,5.9);
  for(let i=0;i<4;i++)mesh(new T.SphereGeometry(.19,12,8),i%2?'rose':'path',-5.4+i*.27,.45,5.9);
  for(const [x,z,s] of [[-9,-2,1],[9,-2,1.1],[-7,5.6,.9],[7,5.6,.85],[-2,-8.2,.7],[2,-8.2,.7]]){
   cyl(.16,1.6*s,'wood',x,.8*s,z);mesh(new T.SphereGeometry(1*s,12,8),'edge',x,2*s,z);mesh(new T.SphereGeometry(.8*s,12,8),'grass',x+.4,2.55*s,z+.15);
  }
  // Open welcome pergola faces the central lawn, without enclosing the pets.
  for(const x of [-1.4,1.4])box(.18,2,.18,'wood',x,1,7.2);
  box(3.2,.2,.55,'cream',0,2.1,7.2);
  // Batch static props by material: repeated trim must not cost 100+ draws.
  const buckets=new Map(),originals=new Set();
  for(const o of group.children){o.updateMatrix();originals.add(o.geometry);const g=o.geometry.index?o.geometry.toNonIndexed():o.geometry.clone();g.applyMatrix4(o.matrix);if(!buckets.has(o.material))buckets.set(o.material,[]);buckets.get(o.material).push(g);}
  group.clear();for(const [material,parts] of buckets){const geometry=new T.BufferGeometry();for(const attr of ['position','normal','uv']){const length=parts.reduce((sum,g)=>sum+g.attributes[attr].array.length,0),values=new Float32Array(length);let offset=0;for(const g of parts){values.set(g.attributes[attr].array,offset);offset+=g.attributes[attr].array.length;}geometry.setAttribute(attr,new T.BufferAttribute(values,attr==='uv'?2:3));}geometry.computeBoundingSphere();group.add(new T.Mesh(geometry,material));for(const g of parts)g.dispose();}for(const g of originals)g.dispose();
  group.userData.walkRadius={x:8,z:6};return group;
 }
 function inside(x,z){return Number.isFinite(x)&&Number.isFinite(z)&&(x/8)**2+(z/6)**2<=1;}
 async function load(T,{tier='play',loader,ticket,version=''}){
  if(!['play','preview'].includes(tier))throw new Error('Unknown park tier');
  const gltf=await loader.glb('/static/models/paw-commons-v2/'+tier+'.glb?v='+encodeURIComponent(version),ticket);
  gltf.scene.name='Paw Commons '+tier;gltf.scene.userData.parkTier=tier;
  gltf.scene.traverse(o=>{if(!o.isMesh)return;o.castShadow=false;o.receiveShadow=false;});
  return gltf;
 }
 return {create,positions,inside,load};
});
