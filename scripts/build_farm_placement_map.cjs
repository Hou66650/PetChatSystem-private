// Compile server/browser placement rules from the actual island navigation.
const fs=require('fs'),path=require('path'),root=path.resolve(__dirname,'..');
const base=require('../static/js/den/mistwood-layout'),farm=require('../static/js/den/farm-garden'),toys=require('../static/js/den/toy-workshop'),layout=require('../static/data/farm-layout.json'),catalog=require('../static/data/cat-world.json'),{Navigation}=require('../static/js/den/scene-navigation');
const config=farm.navigation(toys.navigation('room',base),layout),nav=new Navigation({...config,bodyRadius:.36}),paths=[];
for(const p of catalog){const target=p.normal?{x:p.x+p.normal.x*(nav.clearance+.04),z:p.z+p.normal.z*(nav.clearance+.04)}:p;const route=nav.route({x:0,z:0},target);if(!route)throw Error('No route '+p.id);let prior={x:0,z:0};for(const next of route){paths.push({a:prior,b:next,r:.72});prior=next;}}
const data={version:1,domains:config.domains,blocked:[...config.obstacles,...base.water.map(w=>({kind:'rect',...w})),{kind:'rect',x:3,z:-3.4,w:4.6,d:3.5},{kind:'rect',x:-3,z:4.5,w:3.3,d:2.8}],paths,
 soil:[{x:0,z:0,rx:7.8,rz:7.8}],soilExcluded:[{kind:'rect',x:0,z:1.8,w:3.6,d:4.2},{kind:'rect',...layout.entry}],height:.035};
fs.writeFileSync(path.join(root,'static/data/farm-placement.json'),JSON.stringify(data,null,2)+'\n');
console.log('Compiled farm placement map, protected route segments:',paths.length);
