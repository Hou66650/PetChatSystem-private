const assert=require('assert'),P=require('../static/js/den/farm-placement'),map=require('../static/data/farm-placement.json'),F=require('../static/js/den/farm-garden'),T=require('../static/js/den/toy-workshop'),L=require('../static/js/den/mistwood-layout'),layout=require('../static/data/farm-layout.json'),{Navigation}=require('../static/js/den/scene-navigation');
const items=[];
for(let x=-14;x<8;x+=.4)for(let z=-7;z<8;z+=.4){const p={id:String(items.length),x,z,yaw:0,container:'soil',species:items.length%4?'cosmos':'birch'};if(items.length<80&&!P.validate(map,p,items))items.push(p);}
assert(items.length>15,'free soil locations beyond fixed slots');
const config=F.navigation(T.navigation('room',L),layout),nav=new Navigation({...config,bodyRadius:.36,obstacles:config.obstacles.concat(items.map(p=>({x:p.x,z:p.z,r:P.radius(p.species,p.container)})))});
for(const p of require('../static/data/cat-world.json')){const target=p.normal?{x:p.x+p.normal.x*(nav.clearance+.04),z:p.z+p.normal.z*(nav.clearance+.04)}:p;assert(nav.route({x:0,z:0},target),'garden decorations preserve route to '+p.id);}
assert(P.validate(map,{x:0,z:1.8,yaw:0,species:'cosmos',container:'soil'}));
assert(P.validate(map,{x:-8.1,z:3,yaw:0,species:'cosmos',container:'soil'}));
assert(P.validate(map,{x:0,z:50,yaw:0,species:'cosmos',container:'pot'}));
assert(P.validate(map,{...items[0]},items));
assert.equal(P.validate(map,{...items[0]},items,items[0].id),'');
console.log('PASS placement: '+items.length+' free arrangements preserve every catalog destination, water/bed/edge exclusions, overlap and self-move');
