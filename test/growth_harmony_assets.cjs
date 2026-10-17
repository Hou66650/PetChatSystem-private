const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const root=path.resolve(__dirname,'..'),manifest=JSON.parse(fs.readFileSync(path.join(root,'static/data/pet-growth-models.json'),'utf8'));
const native=fs.readFileSync(path.join(root,'harmony/entry/src/main/ets/model/NativeAssets.ets'),'utf8');
const bridge=fs.readFileSync(path.join(root,'static/js/den/native-den.js'),'utf8');
for(const item of manifest.stages){
 for(const asset of Object.values(item.assets)){
  assert(native.includes(`'${asset.path}'`),'missing native asset registration '+asset.path);
  assert(fs.statSync(path.join(root,asset.path.slice(1))).size<=32*1024*1024,'native download limit '+asset.path);
 }
}
assert(!native.includes('/api/pet-studio/'),'private models must not enter the public native whitelist');
assert(bridge.includes('const PATHS = new Set();'),'native paths stay disabled until same-layer device verification');
console.log('Growth Harmony assets: manifest, native registration, safe Web fallback and size limits passed');
