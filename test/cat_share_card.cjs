const assert=require('node:assert/strict'),{summary}=require('../static/js/den/cat-share-card');
const data={serverTime:101,streams:[{stream:'private-A',updated:100,snapshot:{phase:'walking',trail:[[0,0,1],[.5,0,201],[6,0,401,1],[6.5,0,601]]}}],events:[{stream:'private-A',snapshot:{target:'garden',reason:'private text'}},{stream:'private-B',snapshot:{target:'home'}}],catalog:[{id:'garden',name:'花园'},{id:'home',name:'猫窝'}],memory:[{target:'home',visits:999}]};
const s=summary(data,'private-A');assert.equal(s.distance,1);assert.equal(s.points,4);assert.deepEqual(s.names,['花园']);assert.equal(s.stale,false);assert(!JSON.stringify(s).includes('private'));assert(!JSON.stringify(s).includes('999'));assert.equal(summary(data,'missing'),null);assert.equal(summary(data,'private-A',401).points,1);data.serverTime=120;assert(summary(data,'private-A').stale);data.streams[0].snapshot.trail=[];assert.equal(summary(data,'private-A').distance,0);
console.log('PASS share card: session isolation, discontinuities, cutoff, stale/empty data, no private reasons or cumulative counts');
const {labels}=require('../static/js/den/cat-share-card'),catalog=require('../static/data/cat-world.json');
const map=summary({...data,catalog,events:[{stream:'private-A',updated:100,snapshot:{target:'garden',reason:'secret'}},{stream:'private-B',updated:100,snapshot:{target:'home'}}]},'private-A');
assert.equal(map.landmarks.length,catalog.length);assert(map.landmarks.find(p=>p.name==='林间花园').recorded);assert(!map.landmarks.find(p=>p.name==='木屋软垫').recorded);
assert(!JSON.stringify(map).includes('secret'));assert(!JSON.stringify(map).includes('private'));
const placements=labels(map.landmarks);for(const left of [true,false]){
 const side=placements.filter(p=>p.left===left).sort((a,b)=>a.labelY-b.labelY);
 for(let i=0;i<side.length;i++){assert(side[i].labelY>=375&&side[i].labelY<=875);if(i)assert(side[i].labelY-side[i-1].labelY>=38,'map label boxes cannot overlap');}
}
const cleared=summary({...data,catalog,events:[{stream:'private-A',updated:100,snapshot:{target:'garden'}}]},'private-A',100001);assert(cleared.landmarks.every(p=>!p.recorded),'cleared trail cannot highlight old place events');
console.log('PASS share map: catalog coordinates, session-only highlights, cutoff, '+placements.length+' nonoverlapping place labels');
