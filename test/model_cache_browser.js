// Run in a browser with selected-assets.js loaded. Uses an isolated database,
// synthetic bytes and no application account, API or model resources.
async function testModelCacheStorage() {
    const {ModelStore}=SelectedAssets,name='pait-model-cache-test-'+Date.now();
    const assert=(ok,message)=>{if(!ok)throw Error(message);};
    const store=new ModelStore(indexedDB,name);
    const entry=(key,byte)=>({key,buffer:new Uint8Array([byte,byte,byte,byte]).buffer,etag:'"'+byte+'"'});
    try {
        await store.put(entry('one',1),8);await store.put(entry('two',2),8);
        assert((await store.get('one')).buffer.byteLength===4,'persist ArrayBuffer');
        // Deterministic access times make this independent of timer precision.
        await store.transaction('readwrite',meta=>{meta.put({key:'one',size:4,used:1});meta.put({key:'two',size:4,used:2});});
        await store.touch('one');await store.put(entry('three',3),8);
        assert(await store.get('one'),'recent entry survives eviction');
        assert(!await store.get('two'),'least recently used entry removed');
        assert(new Uint8Array((await store.get('three')).buffer)[0]===3,'new bytes persisted');
        (await store.open()).close();store.opening=null;
        const reopened=await store.get('one');assert(reopened,'reopening database preserves model');
        await store.put(entry('one',9),8);
        assert(new Uint8Array((await store.get('one')).buffer)[0]===9,'replacement is atomic');
        await store.remove('one');assert(!await store.get('one'),'invalidation removes metadata and bytes');
        return 'PASS real IndexedDB: bytes, LRU, reopen, replacement and invalidation';
    } finally {
        (await store.open()).close();
        await new Promise((resolve,reject)=>{const r=indexedDB.deleteDatabase(name);r.onsuccess=resolve;r.onerror=()=>reject(r.error);});
    }
}
