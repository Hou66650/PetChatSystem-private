const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const THREE = require('../static/js/vendor/three.min.js');
const base = require('../static/js/den/farm-garden');
const FarmGarden = { ...base };
let now = 1000;
const performance = { now: () => now };
const context = { FarmGarden, FarmPlacement: require('../static/js/den/farm-placement'), performance, innerWidth: 200 };
vm.runInNewContext(fs.readFileSync('static/js/den/farm-interaction.js', 'utf8'), context);
// Exercise real picking without a GPU or a user's account.
const camera = new THREE.OrthographicCamera(-10, 10, 10, -10, .1, 30);
camera.position.set(0, 10, 0); camera.up.set(0, 0, -1); camera.lookAt(0, 0, 0); camera.updateMatrixWorld();
const canvas = { getBoundingClientRect: () => ({ left: 0, top: 0, width: 200, height: 200 }) };
let opened = 0, toolPicked = 0, placedOpened = 0, groundPicks = 0;
const view = Object.assign(Object.create(FarmGarden.View.prototype), {
  T: THREE, a: { camera, canvas, active: () => true },
  layout: { beds: [{ id: 'bed-1', x: 0, z: 0, w: 2, d: 2 }], fixtures: [] },
  data: { beds: [], catalog: [{ id: 'cosmos', name: '波斯菊', stages: ['幼苗'] }], arrangements: [] },
  dialog: { open: false }, hover: { style: {} }, toolModels: new Map(), groups: new Map(),
  open() { opened++; }, takeTool() { toolPicked++; }, inspectPlaced() { placedOpened++; }
});
// Load the real island pointer-up listener: a handled farm tap must not reach
// its expensive pet/scenery raycasts, even when no compatibility click arrives.
const template = fs.readFileSync('templates/den.html', 'utf8');
const start = template.indexOf("canvas.addEventListener('pointerup', e => {");
const end = template.indexOf('\n        });', start) + '\n        });'.length;
let pointerUp;
const input = {
  canvas: { addEventListener: (_type, fn) => { pointerUp = fn; } }, performance,
  groundPress: null, portals: null, petModel: {}, spawnBusy: false, grabbed: false, dropping: false,
  farmGarden: view, islandBowls: { pick() { groundPicks++; return 'water'; }, open() {} }
};
vm.runInNewContext(template.slice(start, end), input);
function tap(x = 100, y = 100, travel = 0) {
  input.groundPress = { id: 9, x, y, travel, time: now };
  pointerUp({ pointerId: 9, pointerType: 'touch', clientX: x, clientY: y });
}
// The base module runs in Node; use a separate VM copy so its clock matches.
const baseContext = { module: { exports: {} }, require: () => [], performance, innerWidth: 200, innerHeight: 200 };
vm.runInNewContext(fs.readFileSync('static/js/den/farm-garden.js', 'utf8'), baseContext);
Object.setPrototypeOf(FarmGarden.View.prototype, baseContext.module.exports.View.prototype);
tap(); assert.equal(opened, 1); assert.equal(groundPicks, 0);
view.point({ clientX: 100, clientY: 100, stopImmediatePropagation() { throw Error('duplicate click'); } }, true);
assert.equal(opened, 1, 'compatibility click is suppressed');
now += 600; tap(100, 100, 20); assert.equal(opened, 1, 'drag is not a tap');
tap(190, 190); assert.equal(groundPicks, 1, 'empty ground retains existing interaction');
view.dialog.open = true; now += 600; assert.equal(view.handleTap({ clientX: 100, clientY: 100 }), false); view.dialog.open = false;
view.mode = 'care'; assert.equal(view.handleTap({ clientX: 100, clientY: 100 }), false); view.mode = null;
const mesh = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshBasicMaterial());
mesh.position.set(0, .5, 0); mesh.updateMatrixWorld(); view.toolModels.set('water', mesh);
now += 600; tap(); assert.equal(toolPicked, 1); assert.equal(groundPicks, 1);
view.toolModels.clear(); view.data.arrangements = [{ id: 'p1', species: 'cosmos', stage: 1 }]; view.groups.set('p1', mesh);
now += 600; tap(); assert.equal(placedOpened, 1); assert.equal(groundPicks, 1);

(async () => {
  const v = Object.assign(Object.create(base.View.prototype), {
    request: async () => ({ started: false }), render() {}, sync: async () => {},
    note(text, error = false) { this.message = text; this.error = error; }
  });
  await v.refresh(); assert.match(v.message, /领取/); assert.equal(v.refreshing, false);
  v.request = async () => { throw Error('断线'); }; await v.refresh(); assert.equal(v.error, true);
  v.request = async () => ({ started: true }); await v.refresh(); assert.match(v.message, /已同步/); assert.equal(v.error, false);
  v.sync = async () => v.note('模型失败', true); await v.refresh(); assert.equal(v.message, '模型失败'); assert.equal(v.error, true);
  console.log('PASS farm: pointer-only tap, no island raycast, no duplicate click, drag/mode guards, tools/plants and read-status recovery');
})().catch(e => { console.error(e); process.exitCode = 1; });
