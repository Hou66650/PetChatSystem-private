/* CPU-only acceleration build. Render buffers are copied, never transferred. */
importScripts('/static/js/vendor/three.min.js','/static/js/vendor/three-mesh-bvh-0.5.23.js');
self.onmessage=({data})=>{
 try{
  const geometry=new THREE.BufferGeometry();
  geometry.setAttribute('position',new THREE.BufferAttribute(data.position,3));
  if(data.index)geometry.setIndex(new THREE.BufferAttribute(data.index,1));
  geometry.groups=data.groups;
  const bvh=new MeshBVHLib.MeshBVH(geometry,{strategy:MeshBVHLib.CENTER,maxLeafTris:12});
  const tree=MeshBVHLib.MeshBVH.serialize(bvh,{cloneBuffers:false});
  self.postMessage({id:data.id,tree},[tree.index.buffer,...tree.roots]);
  geometry.dispose();
 }catch(error){self.postMessage({id:data.id,error:String(error)});}
};
