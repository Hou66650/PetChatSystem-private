const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
let now=0;
const context={window:{},performance:{now:()=>now},requestAnimationFrame:()=>1,cancelAnimationFrame(){},clearTimeout,clearInterval};
vm.runInNewContext(fs.readFileSync('static/js/den_vision.js','utf8').replace(/^import .*;$/m,''),context);
const D=context.window.DenVision;
function hand(ratio,x=.5){
 const l=Array.from({length:21},()=>({x,y:.4,z:0}));
 l[0]={x,y:.7};l[9]={x,y:.55};l[4]={x:x-.04,y:.4};l[8]={x:x-.04+.15*ratio,y:.4};return l;
}
function fixture(){const d=new D();d.target={clientWidth:1000,clientHeight:700};d.configure({gestures:false});d.running=true;const events=[];d.onGrab=(...e)=>events.push(e);return {d,events};}
const {d,events}=fixture();
function detect(t,ls){now=t;d._detectHand(t,{landmarks:ls});d._followLoop();}
detect(0,[hand(1)]);detect(100,[hand(.2)]);detect(150,[hand(1)]);assert.equal(events.length,0,'single noisy pinch ignored');
detect(200,[hand(.2)]);detect(300,[hand(.2)]);assert.equal(events.length,1);assert.equal(events[0][0],true);
detect(400,[hand(1)]);assert(d.handState.releasing);const frozen=d._smooth.px;
detect(450,[hand(.2)]);assert.equal(events.length,1,'brief opening must not throw');
detect(500,[]);assert(d.handState.trackingLost);assert.equal(events.length,1);
const before=d._smooth.px;detect(600,[]);assert.equal(d._smooth.px,before,'short dropout freezes cursor');
detect(650,[hand(.2)]);assert(!d.handState.trackingLost);assert.equal(events.length,1,'recover without a second grab');
detect(750,[hand(1)]);const releasePoint=d._smooth.px;
detect(850,[hand(1)]);assert.equal(events.length,1);
detect(950,[hand(1)]);assert.equal(events.length,2);assert.equal(events[1][0],false);assert.equal(events[1][1].pinchX,releasePoint,'opening fingers does not shift the drop');
detect(1050,[hand(.2)]);detect(1150,[hand(.2)]);detect(1250,[]);detect(1550,[]);
assert.equal(events.at(-1)[2],'lost');assert.equal(events.at(-1)[1],null,'prolonged loss cancels, never throws');
// Landmark order may change when a second hand enters the camera.
detect(1700,[hand(1,.35)]);detect(1800,[hand(1,.75),hand(1,.36)]);assert.equal(d._trackedPalm.x,.36);
const count=events.length;detect(1900,[hand(.2,.9)]);assert(d.handState.trackingLost);assert.equal(events.length,count,'do not transfer ownership to a distant hand');
function smoothAt(fps){const {d}=fixture();d.handState={present:true,sx:0,sy:0,pinchX:0,pinchY:0};now=0;d._followLoop();d._followAt=0;d.handState={present:true,sx:30,sy:30,pinchX:30,pinchY:30};for(let i=1;i<=fps/2;i++){now=i*1000/fps;d._followLoop();}return d._smooth.px;}
assert(Math.abs(smoothAt(60)-smoothAt(240))<1e-8,'GPU refresh rate does not change response');
const {d:zero}=fixture();zero.handState={present:true,sx:100,sy:100,pinchX:0,pinchY:0};zero._followLoop();assert.equal(zero._smooth.px,0,'screen-edge coordinate zero is valid');
zero._trackedPalm={x:.4,y:.4};zero.stop();assert.equal(zero._trackedPalm,null);
const W=require('../static/js/den/toy-workshop.js');
const w=Object.create(W.Controller.prototype),toy={spec:{name:'小摇铃'}};
w.pick=(x,y)=>x===112&&y===100?toy:null;assert.equal(w.handPick(100,100),toy);assert.equal(w.handPick(70,100),null);
w.pick=()=> 'cabinet';assert.equal(w.handPick(100,100),'cabinet','direct occluder wins');
let moved=0,cancelled=0;w.held={state:'held'};w.move=()=>moved++;w.cancel=()=>cancelled++;
w.hand({present:true,pinching:true,trackingLost:true});w.hand({present:true,pinching:true,releasing:true});assert.equal(moved,0);
w.hand({present:false});assert.equal(cancelled,1);
console.log('PASS pinch debounce, frozen release, dropout grace/cancel, hand identity, FPS-independent smoothing, screen edge, stop cleanup, tolerant targeting');
