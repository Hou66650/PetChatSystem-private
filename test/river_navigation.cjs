const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const {Navigation}=require('../static/js/den/scene-navigation.js');
const {Controller}=require('../static/js/den/pet-locomotion.js');
const layout=require('../static/js/den/sakura-river-layout.js');
const source=fs.readFileSync('templates/den.html','utf8');
const courtyard=JSON.parse(source.match(/const SAKURA_NAV = (\{[^\n]+\});/)[1]);
const river=layout.water[0],bridge=layout.bridges[0];
let seed=91;const random=()=>((seed=(1664525*seed+1013904223)>>>0)/2**32);
let checked=0;
function dryOrDeck(p) {
    const inWater=Math.abs(p.x-river.x)<river.w/2 && Math.abs(p.z-river.z)<river.d/2;
    assert(!inWater || Math.abs(p.x-bridge.x)<bridge.w/2-bridge.rail,'No position in uncovered river');
}
function inspectPath(nav,from,path) {
    assert(path,'Path must exist');let a=from;
    for(const b of path) {
        assert(nav.segmentClear(a,b));
        for(let i=0;i<=100;i++){
            const p={x:a.x+(b.x-a.x)*i/100,z:a.z+(b.z-a.z)*i/100};
            assert(nav.isWalkable(p));dryOrDeck(p);checked++;
        }
        a=b;
    }
}
for(const bodyRadius of [.25,.36,.5,.65]) {
    const nav=new Navigation({...courtyard,...layout,bodyRadius});
    assert(nav.isWalkable({x:0,z:0}),'Spawn is safe');
    for(const x of [-2,-1.1,1.1,2]) {
        assert.equal(nav.route({x:0,z:0},{x,z:river.z}),null,'River click must be rejected');
        const p=nav.nearest({x,z:river.z});assert(p && nav.isWalkable(p));dryOrDeck(p);
        const model={position:{x,y:2,z:river.z},rotation:{y:0}};
        new Controller({navigation:nav,model,animate(){},rest(){}}).safePlacement();
        assert(nav.isWalkable(model.position),'Drop onto water is relocated to a safe position');
    }
    inspectPath(nav,{x:0,z:0},nav.route({x:0,z:0},{x:0,z:2.35}));
    inspectPath(nav,{x:0,z:2.35},nav.route({x:0,z:2.35},{x:0,z:0}));
    assert(!nav.segmentClear({x:-1.3,z:.1},{x:1.3,z:2.05}),'No diagonal shortcut through water/rails');
    assert(!nav.isWalkable({x:bridge.w/2-.03,z:bridge.z}),'Rail is blocked');
    let from={x:0,z:0};
    for(let i=0;i<20;i++) {const path=nav.randomDestination(from,random);inspectPath(nav,from,path);from=path.at(-1);}
    // Execute both directions with the production movement controller, including turning/braking.
    const model={position:{x:0,y:.039,z:0},rotation:{y:0}};
    const ctrl=new Controller({navigation:nav,model,animate(){},rest(){},speed:.6,strideSpeed:.6});ctrl.enabled=false;
    for(const dest of [{x:0,z:2.35},{x:0,z:0}]) {
        assert(ctrl.goTo(dest));
        for(let i=0;i<3000 && ctrl.path.length;i++) {
            ctrl.update(1/60);assert(nav.isWalkable(model.position));dryOrDeck(model.position);
            model.position.y=nav.surfaceHeight(model.position);
            assert(model.position.y>=.013);checked++;
        }
        assert(!ctrl.path.length,'Controller reaches other bank');
        assert(Math.hypot(model.position.x-dest.x,model.position.z-dest.z)<.013);
    }
}
const nav=new Navigation(layout);
assert(Math.abs(nav.surfaceHeight({x:0,z:bridge.z})-.193)<1e-9,'Bridge crest height matches authored model');
assert(Math.abs(nav.surfaceHeight({x:0,z:bridge.z-bridge.d/2})-.013)<1e-9);
assert(Math.abs(nav.surfaceHeight({x:0,z:bridge.z+bridge.d/2})-.013)<1e-9);
assert.equal(new Navigation().surfaceHeight({x:0,z:0}),.039,'Legacy rug height retained');
assert.equal(new Navigation().isWalkable({x:1.5,z:1.3}),true,'Other themes do not inherit river');
const noBridge=new Navigation({...layout,bridges:[]});
assert.equal(noBridge.route({x:0,z:0},{x:0,z:2.35}),null,'No route around island edge bypasses river');
// Execute the page's actual release/landing block so navigation cannot be tested
// successfully while the renderer still drops the pet through water or the deck.
const dropCode=source.slice(source.indexOf('if (dropping && petModel) {'),source.indexOf('// 弹跳衰减'));
assert(dropCode.includes('landingY'));
for(const p of [{x:1.5,z:1.3},{x:0,z:1.3},{x:0,z:-.4}]) {
    const petModel={position:{...p,y:2},rotation:{y:0},userData:{}};
    const locomotion=new Controller({navigation:nav,model:petModel,animate(){},rest(){}});
    const context=vm.createContext({petModel,locomotion,dropping:true,modeledStage:true,dt:1/60,
        STAGE_R:nav.radius,grabHomeY:0,bounceBack:0,setAnim(){}});
    for(let i=0;i<60 && context.dropping;i++) {
        vm.runInContext(dropCode,context);
        assert(nav.isWalkable(petModel.position),'Release is safe before the first falling frame');
        assert(petModel.position.y>=nav.surfaceHeight(petModel.position)-1e-8,'No fall through bridge');
    }
    assert(!context.dropping);assert.equal(petModel.position.y,nav.surfaceHeight(petModel.position));
}
console.log(`PASS: ${checked} sampled/animated positions; crossings, wander, river rejection, page release/landing, rails, heights, legacy scenes`);
