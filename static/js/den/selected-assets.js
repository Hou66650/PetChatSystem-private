/* One selected scene owns its pending downloads. No speculative model requests. */
(function(root,factory){
    const api=factory();
    if(typeof module==='object'&&module.exports)module.exports=api;
    else root.SelectedAssets=api;
})(typeof window!=='undefined'?window:globalThis,function(){
    const aborted=()=>Object.assign(new Error('Selection changed'),{name:'AbortError'});
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
        constructor(loader,fetcher=(...args)=>fetch(...args)){this.loader=loader;this.fetcher=fetcher;this.current=null;}
        begin(){this.current?.abort();this.current=new AbortController();return this.current;}
        active(ticket){return ticket===this.current&&!ticket.signal.aborted;}
        async glb(url,ticket){
            if(!this.active(ticket))throw aborted();
            const progress=globalThis.PaitLoading?.start('正在准备三维模型');
            const cancel=()=>progress?.cancel();ticket.signal.addEventListener('abort',cancel,{once:true});
            try {
            const fetcher=this.fetcher;
            const response=await fetcher(url,{signal:ticket.signal,paitTask:progress});
            if(!response.ok)throw new Error(`Model HTTP ${response.status}`);
            const buffer=await (globalThis.PaitLoading?.buffer?globalThis.PaitLoading.buffer(response):response.arrayBuffer());
            if(!this.active(ticket))throw aborted();
            progress?.update('正在解析模型与材质');
            const gltf=await new Promise((resolve,reject)=>this.loader.parse(buffer,url.slice(0,url.lastIndexOf('/')+1),resolve,reject));
            if(!this.active(ticket)){disposeTree(gltf.scene);throw aborted();}
            progress?.done();
            return gltf;
            } catch(error){if(error.name==='AbortError')progress?.cancel();else progress?.fail('模型未能加载，请重试');throw error;}
            finally{ticket.signal.removeEventListener('abort',cancel);}
        }
    }
    return {Loader,disposeTree};
});
