/* Rest-pose bounds for imported skins with nonidentity bind transforms. */
(function(root){
 'use strict';
 root.PetModelBounds={measure(THREE,model){
  model.updateMatrixWorld(true);
  const box=new THREE.Box3(),point=new THREE.Vector3();
  model.traverse(object=>{
   if(!object.isMesh||!object.geometry?.attributes.position)return;
   object.skeleton?.update();
   const positions=object.geometry.attributes.position;
   for(let i=0;i<positions.count;i++){
    point.fromBufferAttribute(positions,i);
    if(object.isSkinnedMesh){
     if(object.applyBoneTransform)object.applyBoneTransform(i,point);
     else object.boneTransform(i,point);
    }
    point.applyMatrix4(object.matrixWorld);box.expandByPoint(point);
   }
  });
  return box;
 }};
})(typeof window!=='undefined'?window:globalThis);
