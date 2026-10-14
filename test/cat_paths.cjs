const assert=require('node:assert/strict'),{Trace}=require('../static/js/den/cat-agent'),paths=require('../static/js/den/cat-paths');
const trace=new Trace();for(let i=0;i<1000;i++)trace.sample({x:i*.001,z:0},i*10);assert(trace.points.length<=32);assert(trace.points.every((p,i,a)=>!i||p[2]-a[i-1][2]>=200));
trace.sample({x:1.1,z:0},11000,true);assert.equal(trace.points.at(-1)[3],1);
const p=paths.trail([[0,0,0],[.2,0,200],[.3,0,400,1],[.4,0,600],[5,0,800],[5.1,0,10000]]);assert.equal((p.d.match(/M/g)||[]).length,4);assert(Math.abs(p.length-.3)<1e-6);assert.equal(paths.trail([[0,0,1],[1,0,2]],1).count,1);
assert.equal(paths.route([0,0],[[0,1],[1,1]]),'M0 0 L0 1 L1 1');assert.equal(paths.route([0,0],[]),'');
console.log('PASS bounded real-position sampling, drag breaks, gaps/teleports, clear cutoff, planned route vertices');
