(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.HomeAtmosphere=api;})(typeof window!=='undefined'?window:globalThis,function(){
 'use strict';
 const noise=`float hash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
 float noise2(vec2 p){vec2 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);return mix(mix(hash(i),hash(i+vec2(1.,0.)),f.x),mix(hash(i+vec2(0.,1.)),hash(i+vec2(1.)),f.x),f.y);}
 float fbm(vec2 p){float n=0.;float a=.55;for(int i=0;i<4;i++){n+=a*noise2(p);p=p*2.03+vec2(3.1,7.2);a*=.48;}return n;}`;
 function mountains(T){
  const vertices=[],colors=[],indices=[],segments=256,rings=8;
  for(let r=0;r<=rings;r++)for(let i=0;i<=segments;i++){
   const a=i/segments*Math.PI*2,dist=58+r*10;
   const ridge=(Math.sin(a*7+1)*.5+.5)*12+(Math.sin(a*13-2)*.5+.5)*9+Math.sin(a*29)*2;
   const y=-19+Math.sin(r/rings*Math.PI)*ridge+(Math.sin(a*37+r)*1.2);
   vertices.push(Math.cos(a)*dist,y,Math.sin(a)*dist);
   const shade=.40+r/rings*.18+Math.max(0,y)/100;colors.push(shade*.72,shade*.92,shade);
   if(r<rings&&i<segments){const q=r*(segments+1)+i;indices.push(q,q+segments+1,q+1,q+1,q+segments+1,q+segments+2);}
  }
  const g=new T.BufferGeometry();g.setAttribute('position',new T.Float32BufferAttribute(vertices,3));g.setAttribute('color',new T.Float32BufferAttribute(colors,3));g.setIndex(indices);g.computeVertexNormals();
  return new T.Mesh(g,new T.MeshStandardMaterial({vertexColors:true,roughness:1,side:T.DoubleSide}));
 }
 class Environment{
  constructor(T,scene,{lightweight=false}={}){
   this.T=T;this.time={value:0};this.group=new T.Group();scene.add(this.group);
   const sky=new T.Mesh(new T.SphereGeometry(290,32,16),new T.ShaderMaterial({side:T.BackSide,depthWrite:false,uniforms:{},vertexShader:'varying vec3 vDir;void main(){vDir=position;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}',fragmentShader:`varying vec3 vDir;void main(){vec3 d=normalize(vDir);float h=clamp(d.y,0.,1.);vec3 color=mix(vec3(.76,.80,.78),vec3(.18,.35,.48),pow(h,.48));float sun=dot(d,normalize(vec3(-.6,.26,-.65)));color+=vec3(.34,.23,.10)*pow(max(sun,0.),10.);color+=vec3(.7,.53,.3)*pow(max(sun,0.),180.);color+=vec3(1.,.9,.68)*smoothstep(.9994,.9998,sun);gl_FragColor=vec4(color,1.);}` }));sky.renderOrder=-10;this.group.add(sky);
   this.group.add(mountains(T));
   const floor=new T.Mesh(new T.CircleGeometry(230,80),new T.MeshBasicMaterial({color:0xadbfc4}));floor.rotation.x=-Math.PI/2;floor.position.y=-19;this.group.add(floor);
   this.clouds=[];
   const cloudNoise=lightweight?noise.replace('i<4','i<2'):noise;
   for(let i=0;i<(lightweight?2:4);i++){
    const material=new T.ShaderMaterial({transparent:true,depthWrite:false,side:T.DoubleSide,uniforms:{uTime:this.time,uLayer:{value:i}},vertexShader:'varying vec3 vWorld;void main(){vec4 w=modelMatrix*vec4(position,1.);vWorld=w.xyz;gl_Position=projectionMatrix*viewMatrix*w;}',fragmentShader:`varying vec3 vWorld;uniform float uTime;uniform float uLayer;${cloudNoise}
     void main(){vec2 p=vWorld.xz*.043+vec2(uTime*.006,uLayer*5.3);float n=fbm(p);float detail=fbm(p*3.1+uLayer);float density=smoothstep(.24,.64,n*.8+detail*.2);float edge=1.-smoothstep(130.,210.,length(vWorld.xz));float light=fbm(p+vec2(-.25,-.35))-n;vec3 col=mix(vec3(.42,.55,.61),vec3(.91,.91,.84),clamp(.54+light*3.+detail*.25,0.,1.));gl_FragColor=vec4(col,density*edge*.72);}`});
    const cloud=new T.Mesh(new T.PlaneGeometry(440,440),material);cloud.rotation.x=-Math.PI/2;cloud.position.y=-7-i*2.8;cloud.renderOrder=-4+i;this.group.add(cloud);this.clouds.push(cloud);
   }
   this.effects=[];
  }
  addIsland(theme,group){
   const T=this.T,count=theme==='snow'?150:theme==='sakura'?90:45,positions=new Float32Array(count*3),seeds=[];
   for(let i=0;i<count;i++){const x=Math.sin(i*78.23)*3.8,z=Math.sin(i*21.71)*3.8,y=(i*.618%1)*4;positions.set([x,y,z],i*3);seeds.push([x,y,z]);}
   const geometry=new T.BufferGeometry();geometry.setAttribute('position',new T.BufferAttribute(positions,3));
   const color=theme==='sakura'?0xf4cfce:theme==='snow'?0xf0f6ff:theme==='room'?0xcbe1af:0xf8d394;
   const points=new T.Points(geometry,new T.ShaderMaterial({transparent:true,depthWrite:false,uniforms:{color:{value:new T.Color(color)},size:{value:theme==='snow'?2.4:2.8}},vertexShader:'uniform float size;void main(){vec4 p=modelViewMatrix*vec4(position,1.);gl_Position=projectionMatrix*p;gl_PointSize=clamp(size*20./-p.z,1.,7.);}',fragmentShader:'uniform vec3 color;void main(){float r=length(gl_PointCoord-.5);float a=1.-smoothstep(.12,.5,r);gl_FragColor=vec4(color,a*.62);}'}));group.add(points);this.effects.push({theme,points,seeds});
  }
  update(seconds,reduced){this.time.value=reduced?0:seconds;
   if(reduced)return;
   for(const effect of this.effects){const p=effect.points.geometry.attributes.position;effect.seeds.forEach(([x,y,z],i)=>{p.setXYZ(i,x+Math.sin(seconds*.2+i)*.4,((y-seconds*(effect.theme==='snow'?.22:.13))%4+4)%4,z+Math.cos(seconds*.15+i)*.2);});p.needsUpdate=true;}
  }
 }
 return {Environment,mountains};
});
