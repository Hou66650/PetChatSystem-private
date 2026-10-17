/* Self-contained roadshow sample. Original island geometry is never modified. */
(()=>{
 'use strict';
 const $=id=>document.getElementById(id),duration=60,starts=[0,6,16,26,36,46,52];
 const chapters=[
  ['ABOVE THE CLOUDS','在云海尽头，\n与你相遇。','为每一次归来，留一盏灯。','四座岛屿 · 一片属于你的世界','序章 / 云海之上'],
  ['01 / SAKURA GARDEN','樱花庭院','风吹过花瓣，\n它跑过桥来迎接你。','球球 · 柴犬','01 / 热情相迎'],
  ['02 / SNOW CABIN','雪境木屋','踩着松软的雪，\n一起去找新的快乐。','雪球 · 哈士奇','02 / 一起探索'],
  ['03 / MISTY GREENHOUSE','雾林温室','阳光落在叶子上，\n留一会儿给慵懒。','团子 · 猫咪','03 / 安静相伴'],
  ['04 / MOUNTAIN CAMP','山岭营地','山风与远方，\n还有始终陪着你的它。','德牧 · 山岭伙伴','04 / 始终陪伴'],
  ['ONE WORLD, FOUR COMPANIONS','四座岛屿，\n四种相遇。','总有一座小岛，适合今天的你。','在云海之上，找到你的伙伴','尾声 / 回到群岛'],
  ['WELCOME TO PAIT ISLAND','派特岛','一段会慢慢长大的陪伴。','现在，去见一见它。','PAIT ISLAND / 派特岛']
 ];
 let renderer;
 try{renderer=new THREE.WebGLRenderer({canvas:$('world'),antialias:true,powerPreference:'high-performance'});}catch(e){$('loading').textContent='当前设备无法开启三维画面，请使用支持 WebGL 的浏览器。';return;}
 renderer.outputEncoding=THREE.sRGBEncoding;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.08;
 const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(42,16/9,.1,500),env=new HomeAtmosphere.Environment(THREE,scene);
 scene.fog=new THREE.Fog(0xa8bac1,65,230);scene.add(new THREE.HemisphereLight(0xe3eff5,0x627777,1.15));
 const sun=new THREE.DirectionalLight(0xffe0b6,2.3);sun.position.set(-35,32,-45);scene.add(sun);const rim=new THREE.DirectionalLight(0xb6e6ff,1);rim.position.set(20,10,-20);scene.add(rim);
 const positions=[[-10,0,8],[10,1,5],[-9,1.5,-11],[11,-.5,-13]],themes=['sakura','snow','room','camp'];
 const targets=[[-4,0,0],...positions.map(p=>[p[0]-3,p[1],p[2]]),[-4,0,0],[-4,0,0]];
 const eyes=[[31,25,48],...positions.map(p=>[p[0]+9,p[1]+7,p[2]+15]),[29,23,43],[31,25,47]];
 let time=0,playing=false,ready=false,last=0,current=-1,loaded=0;
 const smooth=t=>t*t*t*(t*(t*6-15)+10),vec=a=>new THREE.Vector3(...a);
 function chapter(t){let i=0;for(let n=1;n<starts.length;n++)if(t>=starts[n])i=n;return i;}
 function draw(t){
  const i=chapter(t),local=t-starts[i],blend=i?smooth(Math.min(1,local/3.8)):smooth(Math.min(1,t/6));
  const from=i?eyes[i-1]:[40,33,62],to=eyes[i],fromTarget=i?targets[i-1]:[-4,0,0];
  camera.position.lerpVectors(vec(from),vec(to),blend);camera.position.y+=Math.sin(blend*Math.PI)*(i?2:0);camera.lookAt(vec(fromTarget).lerp(vec(targets[i]),blend));
  if(i!==current){current=i;['eyebrow','title','description','resident','chapter'].forEach((id,k)=>$(id).textContent=chapters[i][k]);$('title').style.whiteSpace='pre-line';}
  const end=i<starts.length-1?starts[i+1]:duration+2;
  $('copy').style.opacity=String(Math.min(1,Math.max(0,(local-(i?1.7:.7))/1.1),Math.max(0,(end-t)/.8)));
  $('copy').style.transform=`translateY(${(1-Math.min(1,Math.max(0,local-1.7)/1.1))*12}px)`;
  $('clock').textContent=`00:${String(Math.floor(t)).padStart(2,'0')} / 01:00`;
  if(t>=60)$('clock').textContent='01:00 / 01:00';
  env.update(t,false);renderer.render(scene,camera);
 }
 function resize(){renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.setSize(innerWidth,innerHeight,false);camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();draw(time);}
 function setPlaying(value){if(!ready)return;if(time>=duration&&value)time=0;playing=value;last=performance.now();$('play').textContent=playing?'暂停':'播放';}
 function seek(t){time=Math.max(0,Math.min(duration,t));last=performance.now();draw(time);}
 $('play').onclick=()=>setPlaying(!playing);$('restart').onclick=()=>{seek(0);setPlaying(true);};$('next').onclick=()=>seek(starts.find(t=>t>time+.1)??duration);
 $('fullscreen').onclick=async()=>{try{if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen();}catch(e){$('fullscreen').textContent='请按 F11 全屏';}};
 addEventListener('keydown',e=>{if(e.target.tagName==='BUTTON'&&(e.code==='Space'||e.code==='Enter'))return;if(e.code==='Space'){e.preventDefault();setPlaying(!playing);}if(e.code==='ArrowRight'){e.preventDefault();$('next').click();}if(e.code==='ArrowLeft'){e.preventDefault();seek([...starts].reverse().find(t=>t<time-.2)??0);}if(e.code==='KeyH')document.body.classList.toggle('clean');});
 document.addEventListener('visibilitychange',()=>{if(document.hidden)setPlaying(false);});
 $('world').addEventListener('webglcontextlost',e=>{e.preventDefault();setPlaying(false);ready=false;$('loading').hidden=false;$('loading').textContent='三维画面已中断，请刷新后重试。';});
 addEventListener('resize',resize);resize();
 function frame(now){requestAnimationFrame(frame);if(playing){time=Math.min(duration,time+Math.min((now-last)/1000,.1));if(time===duration)setPlaying(false);}last=now;if(ready)draw(time);}requestAnimationFrame(frame);
 const loader=new THREE.GLTFLoader();
 Promise.all(themes.map(async(theme,i)=>{
  const gltf=await new Promise((resolve,reject)=>loader.load('../models/home-islands/'+theme+'.glb',resolve,undefined,reject));
  const group=new THREE.Group(),object=gltf.scene,box=new THREE.Box3().setFromObject(object),size=box.getSize(new THREE.Vector3()),center=box.getCenter(new THREE.Vector3()),scale=9/Math.max(size.x,size.z);
  object.position.sub(center).multiplyScalar(scale);object.scale.setScalar(scale);group.position.set(...positions[i]);group.add(object);scene.add(group);env.addIsland(theme,group);$('count').textContent=++loaded+' / 4';
 })).then(()=>{ready=true;$('loading').hidden=true;['play','restart','next'].forEach(id=>$(id).disabled=false);seek(0);}).catch(()=>{$('loading').textContent='岛屿资源加载失败，请检查本机服务并刷新。';});
 window.PaitIntro={get ready(){return ready;},get time(){return time;},seek,play:()=>setPlaying(true),pause:()=>setPlaying(false),duration};
})();
