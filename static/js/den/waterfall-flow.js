/* Animate authored waterfall UVs; navigation remains independent of decoration. */
(function(root,factory){
    const api=factory();
    if(typeof module==='object'&&module.exports)module.exports=api;
    else root.WaterfallFlow=api;
})(typeof window!=='undefined'?window:globalThis,function(){
    const vertex=`
        vFallUv=uv;
        float sway=sin(uv.y*19.0-waterfallTime*2.4+uv.x*13.0);
        transformed+=normal*sway*0.008*smoothstep(0.03,0.3,uv.y);
    `;
    const fragment=`
        float threads=pow(0.5+0.5*sin(vFallUv.x*61.0+sin(vFallUv.y*13.0-waterfallTime*2.3)*0.6),12.0);
        float glints=pow(max(0.0,sin(vFallUv.y*43.0-waterfallTime*5.4+sin(vFallUv.x*17.0))),14.0);
        diffuseColor.rgb=mix(diffuseColor.rgb,vec3(0.88,0.97,1.0),threads*0.24+glints*0.32);
        diffuseColor.a*=1.0-smoothstep(0.68,1.06,vFallUv.y);
    `;
    class Controller {
        constructor(root){
            this.time={value:0};this.textures=new Set();const materials=new Set();
            root.traverse(o=>{
                if(!o.isMesh||!o.userData.waterfall_role)return;
                o.castShadow=false;o.receiveShadow=false;
                for(const m of Array.isArray(o.material)?o.material:[o.material]){
                    for(const texture of [m.map,m.alphaMap])if(texture)this.textures.add(texture);
                    m.depthWrite=false;
                    if(o.userData.waterfall_role!=='curtain'||materials.has(m))continue;
                    materials.add(m);
                    m.onBeforeCompile=shader=>{
                        shader.uniforms.waterfallTime=this.time;
                        shader.vertexShader='uniform float waterfallTime; varying vec2 vFallUv;\n'+
                            shader.vertexShader.replace('#include <begin_vertex>','#include <begin_vertex>\n'+vertex);
                        shader.fragmentShader='uniform float waterfallTime; varying vec2 vFallUv;\n'+
                            shader.fragmentShader.replace('#include <color_fragment>','#include <color_fragment>\n'+fragment);
                    };
                    m.customProgramCacheKey=()=> 'petchat-waterfall-v1';
                    m.needsUpdate=true;
                }
            });
        }
        update(seconds){this.time.value=Number.isFinite(seconds)?seconds%3600:0;}
        dispose(){for(const texture of this.textures)texture.dispose();this.textures.clear();}
    }
    return {Controller};
});
