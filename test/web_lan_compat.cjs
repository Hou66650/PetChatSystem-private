const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const source = fs.readFileSync('static/js/app.js', 'utf8');
function load(crypto) {
  const context = { crypto, window: {}, document: { addEventListener() {} } };
  vm.runInNewContext(source, context);
  return crypto;
}
let calls = 0;
const crypto = load({ getRandomValues(bytes) { calls++; bytes.fill(255); return bytes; } });
assert.equal(crypto.randomUUID(), 'ffffffff-ffff-4fff-bfff-ffffffffffff');
assert.equal(calls, 1);
const native = () => 'native';
assert.equal(load({ randomUUID: native }).randomUUID, native);
assert.doesNotThrow(() => load(undefined));
const real = require('node:crypto').webcrypto;
const fallback = load({ getRandomValues: real.getRandomValues.bind(real) });
const ids = new Set(Array.from({ length: 1000 }, () => fallback.randomUUID()));
assert.equal(ids.size, 1000);
for (const id of ids) assert.match(id, /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
// Exercise the actual scene startup that previously threw on LAN HTTP.
const context = { crypto: fallback, module: { exports: {} }, setInterval() { return 1; }, clearInterval() {} };
vm.runInNewContext(fs.readFileSync('static/js/den/supply-delivery.js', 'utf8'), context);
const delivery = new context.module.exports.Controller({});
assert.match(delivery.client, /^[0-9a-f-]{36}$/);
delivery.dispose();
console.log('PASS LAN UUID fallback, native preservation, secure IDs and supply controller startup');
const startup = fs.readFileSync('static/js/app.js', 'utf8');
function compat(ua) {
 const context = { window: {}, navigator: { userAgent: ua }, document: { addEventListener() {} } };
 vm.runInNewContext(startup, context);return context.window.PaitWebCompat;
}
const events=[],target={};
const renderer={render(scene,camera){events.push(['render',scene,camera]);return 42;},getRenderTarget(){return target;},getActiveCubeFace(){return 3;},getActiveMipmapLevel(){return 2;},resetState(){events.push(['reset']);},setRenderTarget(...args){events.push(['target',...args]);}};
const original=renderer.render;compat('Chrome/132').prepareRenderer(renderer);assert.equal(renderer.render,original);
const ark=compat('OpenHarmony 6.1 ArkWeb/6.1.0.31');ark.prepareRenderer(renderer);const wrapped=renderer.render;ark.prepareRenderer(renderer);assert.equal(renderer.render,wrapped);
assert.equal(renderer.render('scene','camera'),42);
assert.deepEqual(events,[['reset'],['target',target,3,2],['render','scene','camera']]);
console.log('PASS ArkWeb-only renderer reset, target preservation and idempotent setup');
