const assert=require('node:assert/strict');
const {Navigation}=require('../static/js/den/scene-navigation.js');
const {Controller}=require('../static/js/den/pet-locomotion.js');
const layout=require('../static/js/den/snow-haven-layout.js');
let checked=0,seed=182;const random=()=>((seed=(1664525*seed+1013904223)>>>0)/2**32);
for(const bodyRadius of [.36,.5,.65,.81]){
 const nav=new Navigation({...layout,bodyRadius});const origin={x:0,z:0};assert(nav.isWalkable(origin));
 for(const obstacle of layout.obstacles){
  assert.equal(nav.route(origin,obstacle),null,'Decorations reject walking targets');
  const model={position:{x:obstacle.x,z:obstacle.z,y:2},rotation:{y:0}};
  new Controller({navigation:nav,model,animate(){},rest(){}}).safePlacement();assert(nav.isWalkable(model.position),'Drops relocate to snow');
 }
 for(const point of [{x:.65,z:.5},{x:-.5,z:-.3},...layout.interest_points])assert(nav.route(origin,point),'Central courtyard remains connected');
 let from=origin;
 for(let n=0;n<35;n++){
  const path=nav.randomDestination(from,random);assert(path);
  for(const to of path){for(let i=0;i<=80;i++){
   const p={x:from.x+(to.x-from.x)*i/80,z:from.z+(to.z-from.z)*i/80};assert(nav.isWalkable(p));assert.equal(nav.surfaceHeight(p),.025);checked++;
  }from=to;}
 }
}
console.log(`PASS: snow courtyard connected, props/pond excluded, safe drops, ${checked} walkable path samples`);
