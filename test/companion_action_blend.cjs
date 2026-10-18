const assert=require('node:assert/strict'),T=require('../static/js/vendor/three.min.js'),{Controller}=require('../static/js/den/action-blend');
const model=new T.Group(),mixer=new T.AnimationMixer(model),blend=new Controller(T);
const actions=Array.from({length:25},(_,i)=>mixer.clipAction(new T.AnimationClip('pose'+i,1,[new T.NumberKeyframeTrack('.position[y]',[0,1],[i/100,i/100+.01])])));
const tick=dt=>{blend.update(dt);mixer.update(dt);assert(Math.abs([...blend.weights.values()].reduce((a,b)=>a+b,0)-1)<1e-6);assert(Number.isFinite(model.position.y));};
for(let i=0;i<150;i++){blend.play(actions[i%25],{once:i%3===0,speed:1});tick(1/60);}
for(let i=0;i<90;i++)tick(1/60);assert.equal(blend.weights.size,1,'interrupted body actions must be released');
const active=blend.active;blend.play(active,{speed:.5});tick(.05);const time=active.time;blend.play(active,{speed:2});assert.equal(active.time,time,'loop rate changes must preserve phase');tick(.05);assert(active.time>time);
blend.play(actions[0],{once:true});for(let i=0;i<80;i++)tick(1/60);assert(actions[0].paused);assert.equal(actions[0].time,1);
console.log('PASS shared body blending: 25 clips, 150 interruptions, normalized weights, phase continuity, bounded speed smoothing and one-shot clamp');
