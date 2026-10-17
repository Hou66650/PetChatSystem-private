/* One selected scene owns its pending downloads. No speculative model requests. */
(function(root,factory){
    const api=factory();
    if(typeof module==='object'&&module.exports)module.exports=api;
    else root.SelectedAssets=api;
})(typeof window!=='undefined'?window:globalThis,function(){
    const aborted=()=>Object.assign(new Error('Selection changed'),{name:'AbortError'});
    const MiB=1024*1024;
    const check=signal=>{if(signal?.aborted)throw aborted();};
    function validGlb(buffer){
        if(!(buffer instanceof ArrayBuffer)||buffer.byteLength<20)return false;
        const h=new DataView(buffer);
        return h.getUint32(0,true)===0x46546c67&&h.getUint32(4,true)===2&&h.getUint32(8,true)===buffer.byteLength;
    }
    // Separate metadata from large blobs: eviction never reads every model into RAM.
    class ModelStore {
        constructor(idb,name='pait-models-v1'){
            if(idb===undefined)try{idb=globalThis.indexedDB;}catch(_){}
            this.idb=idb;this.name=name;this.opening=null;
        }
        open(){
            if(!this.opening)this.opening=new Promise((resolve,reject)=>{
                if(!this.idb){reject(new Error('Model storage unavailable'));return;}
                let settled=false;
                const request=this.idb.open(this.name,1);
                const fail=()=>{if(!settled){settled=true;clearTimeout(timer);reject((request.readyState==='done'&&request.error)||new Error('Model storage blocked'));}};
                const timer=setTimeout(fail,1500);
                request.onupgradeneeded=()=>{const db=request.result;db.createObjectStore('meta',{keyPath:'key'});db.createObjectStore('data');};
                request.onerror=fail;request.onblocked=fail;
                request.onsuccess=()=>{const db=request.result;if(settled){db.close();return;}settled=true;clearTimeout(timer);
                    db.onversionchange=()=>{db.close();this.opening=null;};resolve(db);};
            }).catch(error=>{this.opening=null;throw error;});
            return this.opening;
        }
        async transaction(mode,work){
            const db=await this.open();
            return new Promise((resolve,reject)=>{
                const tx=db.transaction(['meta','data'],mode),meta=tx.objectStore('meta'),data=tx.objectStore('data');
                let result;
                const timer=setTimeout(()=>{try{tx.abort();}catch(_){}reject(new Error('Model storage timeout'));},5000);
                tx.oncomplete=()=>{clearTimeout(timer);resolve(result);};
                tx.onabort=tx.onerror=event=>{clearTimeout(timer);reject(tx.error||event.target?.error||new Error('Model storage failed'));};
                try{work(meta,data,value=>{result=value;});}catch(error){tx.abort();clearTimeout(timer);reject(error);}
            });
        }
        get(key){return this.transaction('readonly',(meta,data,done)=>{
            const m=meta.get(key),b=data.get(key);let info,buffer;
            m.onsuccess=()=>{info=m.result;done(info&&buffer?{...info,buffer}:null);};
            b.onsuccess=()=>{buffer=b.result;done(info&&buffer?{...info,buffer}:null);};
        });}
        remove(key){return this.transaction('readwrite',(meta,data)=>{meta.delete(key);data.delete(key);});}
        touch(key){return this.transaction('readwrite',meta=>{const r=meta.get(key);r.onsuccess=()=>{if(r.result)meta.put({...r.result,used:Date.now()});};});}
        put(entry,budget){return this.transaction('readwrite',(meta,data)=>{
            const request=meta.getAll();request.onsuccess=()=>{
                const others=request.result.filter(x=>x.key!==entry.key).sort((a,b)=>a.used-b.used);
                let size=others.reduce((n,x)=>n+x.size,entry.buffer.byteLength);
                for(const old of others){if(size<=budget)break;meta.delete(old.key);data.delete(old.key);size-=old.size;}
                const {buffer,...info}=entry;data.put(buffer,entry.key);meta.put({...info,size:buffer.byteLength,used:Date.now()});
            };
        });}
    }
    class ModelCache {
        constructor({store=new ModelStore(),base=globalThis.location?.href,budget=384*MiB,maxEntry=128*MiB}={}){
            Object.assign(this,{store,base,budget,maxEntry});
        }
        key(url){
            try{
                const u=new URL(url,this.base),base=new URL(this.base);
                // Only public self-contained models. Private uploads and API results
                // retain their existing authentication and cache semantics.
                if(u.origin!==base.origin||!/^\/static\/models\/.+\.glb$/.test(u.pathname))return null;
                if([...u.searchParams.keys()].some(k=>k!=='v'))return null;
                u.search='';u.hash='';return u.href;
            }catch(_){return null;}
        }
        async forget(url){const key=this.key(url);if(key)try{await this.store.remove(key);}catch(_){};}
        async read(url,{signal,progress,fetcher,force=false}){
            check(signal);const key=this.key(url);let saved=null;
            if(key&&!force)try{saved=await this.store.get(key);}catch(_){}
            check(signal);
            if(saved&&!validGlb(saved.buffer)){await this.forget(url);saved=null;}
            const headers={};
            if(saved?.etag)headers['If-None-Match']=saved.etag;
            else if(saved?.modified)headers['If-Modified-Since']=saved.modified;
            let response,timedOut=false;
            const controller=new AbortController(),cancel=()=>controller.abort();
            signal?.addEventListener('abort',cancel,{once:true});check(signal);
            const timer=saved?setTimeout(()=>{timedOut=true;controller.abort();},3000):null;
            try {
            try{
                progress?.update(saved?'正在检查模型更新':'正在下载三维模型');
                response=await fetcher(key||url,{signal:controller.signal,paitTask:progress,paitCacheFallback:!!saved,...(key?{headers,cache:'no-store'}:{})});
            }catch(error){
                check(signal);
                // Never make cancellation look like a successful cached load.
                if(!saved||(error.name==='AbortError'&&!timedOut))throw error;
                progress?.update('网络暂不可用，正在读取本地模型');
                return {buffer:saved.buffer,cached:true};
            }
            clearTimeout(timer);
            check(signal);
            if(response.status===304&&saved){
                progress?.update('正在读取本地模型');
                this.store.touch(key).catch(()=>{});
                return {buffer:saved.buffer,cached:true};
            }
            if(!response.ok){if(key&&(response.status===404||response.status===410))await this.forget(url);throw new Error(`Model HTTP ${response.status}`);}
            const buffer=await (globalThis.PaitLoading?.buffer?globalThis.PaitLoading.buffer(response):response.arrayBuffer());
            check(signal);
            return {buffer,cached:false,entry:key&&validGlb(buffer)&&buffer.byteLength<=Math.min(this.budget,this.maxEntry)?{
                key,buffer,etag:response.headers?.get('ETag')||'',modified:response.headers?.get('Last-Modified')||''
            }:null};
            } finally {clearTimeout(timer);signal?.removeEventListener('abort',cancel);}
        }
        async save(entry){
            if(!entry)return;
            try{await this.store.put(entry,this.budget);}catch(error){
                if(error.name==='QuotaExceededError')try{await this.store.put(entry,entry.buffer.byteLength);}catch(_){}
            }
        }
    }
    const modelCache=new ModelCache();
    function disposeTree(root){
        const geometries=new Set(),materials=new Set(),textures=new Set(),skeletons=new Set();
        root.traverse(o=>{
            if(o.geometry)geometries.add(o.geometry);
            if(o.skeleton)skeletons.add(o.skeleton);
            for(const m of o.material?(Array.isArray(o.material)?o.material:[o.material]):[]){
                materials.add(m);
                for(const value of Object.values(m))if(value?.isTexture)textures.add(value);
            }
        });
        for(const s of skeletons)s.dispose?.();
        for(const t of textures){t.dispose();t.image?.close?.();}
        for(const m of materials)m.dispose();
        for(const g of geometries)g.dispose();
    }
    class Loader {
        constructor(loader,fetcher=(...args)=>fetch(...args),cache=modelCache){this.loader=loader;this.fetcher=fetcher;this.cache=cache;this.current=null;}
        begin(){this.current?.abort();this.current=new AbortController();return this.current;}
        active(ticket){return ticket===this.current&&!ticket.signal.aborted;}
        async glb(url,ticket){
            if(!this.active(ticket))throw aborted();
            const progress=globalThis.PaitLoading?.start('正在准备三维模型');
            const cancel=()=>progress?.cancel();ticket.signal.addEventListener('abort',cancel,{once:true});
            try {
            let loaded=await this.cache.read(url,{signal:ticket.signal,progress,fetcher:this.fetcher});
            const parse=async()=>{
                if(!this.active(ticket))throw aborted();
                progress?.update(loaded.cached?'正在解析本地模型与材质':'正在解析模型与材质');
                return new Promise((resolve,reject)=>this.loader.parse(loaded.buffer,url.slice(0,url.lastIndexOf('/')+1),resolve,reject));
            };
            let gltf;
            try{gltf=await parse();}catch(error){
                if(!loaded.cached||!this.active(ticket))throw error;
                await this.cache.forget(url);
                loaded=await this.cache.read(url,{signal:ticket.signal,progress,fetcher:this.fetcher,force:true});
                gltf=await parse();
            }
            if(!this.active(ticket)){disposeTree(gltf.scene);throw aborted();}
            // Only persist successfully parsed GLB files; storage failure never
            // prevents display. Avoid retaining extra decoded scene/GPU copies.
            await this.cache.save(loaded.entry);
            if(!this.active(ticket)){disposeTree(gltf.scene);throw aborted();}
            progress?.done();
            return gltf;
            } catch(error){if(error.name==='AbortError')progress?.cancel();else progress?.fail('模型未能加载，请重试');throw error;}
            finally{ticket.signal.removeEventListener('abort',cancel);}
        }
    }
    return {Loader,disposeTree,ModelCache,ModelStore,validGlb};
});
