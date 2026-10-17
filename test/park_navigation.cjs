const assert=require('node:assert/strict'),config=require('../static/models/paw-commons-v2/navigation.json'),nav=require('../static/js/park-navigation.js').create(config);
assert(!nav.inside(.3,-.8));assert(!nav.segment({x:-4,z:-.8},{x:4,z:-.8}));
for(const [from,to] of [[{x:-5,z:0},{x:5,z:0}],[{x:0,z:4},{x:0,z:-4}],[{x:5,z:1},{x:.3,z:-.8}],[{x:-5,z:0},{x:-7.4,z:-4}],[{x:0,z:3},{x:100,z:100}]]){
 const route=nav.route(from,to);assert(route.length);let previous=from;for(const p of route){assert(nav.inside(p.x,p.z));assert(nav.segment(previous,p),'no segment crosses a measured obstacle');previous=p;}
 const nearest=nav.nearest(to);assert(Math.hypot(previous.x-nearest.x,previous.z-nearest.z)<1e-6);
 // At 2.5 m/s, 0.5 s server samples must also form valid collision-free chords.
 let p={...from},i=0,prior={...from};while(i<route.length){let budget=1.25;while(budget>0&&i<route.length){const q=route[i],d=Math.hypot(q.x-p.x,q.z-p.z),step=Math.min(d,budget);if(d<1e-8){i++;continue;}p.x+=(q.x-p.x)/d*step;p.z+=(q.z-p.z)/d*step;budget-=step;}assert(nav.segment(prior,p),'sync chord stays clear');prior={...p};}
}
for(let a=0;a<360;a++){assert(nav.inside(Math.cos(a*Math.PI/180)*5,Math.sin(a*Math.PI/180)*3.5),'all existing spawn positions remain valid');}
assert.deepEqual(nav.route({x:.3,z:-.8},{x:0,z:3}),[]);
console.log('PASS park routes around obstacles, blocked target projection, spawn ring, 2 Hz sync chords');
