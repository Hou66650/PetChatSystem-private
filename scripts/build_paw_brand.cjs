/* Build vector-first brand assets and a deterministic, offline roadshow transition.
 * NODE_PATH must provide @resvg/resvg-js and playwright. No remote services used.
 */
const fs=require('node:fs'),path=require('node:path'),http=require('node:http');
const {Resvg}=require('@resvg/resvg-js');
const root=path.resolve(__dirname,'..'),out=path.join(root,'static/brand/five-islands');
fs.mkdirSync(out,{recursive:true});
const cream='#F4E9D3',night='#19243B';
const word=`<g id="wordmark" transform="translate(-32 -110)" fill="none" stroke="${cream}" stroke-width="35" stroke-linecap="round" stroke-linejoin="round"><path d="M250 332V616M250 420C250 371 289 332 338 332S426 371 426 420S387 508 338 508S250 469 250 420"/><path d="M490 420H682C682 370 641 332 588 332S490 370 490 420S532 508 588 508C619 508 647 498 668 478"/><path d="M784 306V502Q784 543 824 532M728 366H846"/></g><circle cx="556" cy="269" r="17" fill="#FFC16A"/>`;
const pads=[
 {key:'sakura',name:'樱花庭院',world:[-15,0],cx:272,cy:680,rx:65,ry:79,angle:-28},
 {key:'snow',name:'雪境木屋',world:[-6,-10],cx:416,cy:520,rx:65,ry:82,angle:-12},
 {key:'room',name:'雾林温室',world:[6,-10],cx:608,cy:520,rx:65,ry:82,angle:12},
 {key:'camp',name:'山岭营地',world:[15,0],cx:752,cy:680,rx:65,ry:79,angle:28},
 {key:'park',name:'爪心乐园',world:[0,11],cx:512,cy:840,d:'M0 -98 C-40 -98 -56 -44 -90 -22 C-136 8 -154 60 -121 93 C-88 126 -40 101 0 101 C40 101 88 126 121 93 C154 60 136 8 90 -22 C56 -44 40 -98 0 -98 Z'}
];
const padMarkup=p=>p.d?`<path data-pad="${p.key}" transform="translate(${p.cx} ${p.cy})" d="${p.d}"/>`:`<ellipse data-pad="${p.key}" cx="${p.cx}" cy="${p.cy}" rx="${p.rx}" ry="${p.ry}" transform="rotate(${p.angle} ${p.cx} ${p.cy})"/>`;
const paw=`<g id="paw" fill="none" stroke="${cream}" stroke-width="23" stroke-linecap="round" stroke-linejoin="round">${pads.map(padMarkup).join('')}</g>`;
const defs='<defs><linearGradient id="sky" x2="0" y2="1"><stop stop-color="#19243B"/><stop offset="1" stop-color="#304E70"/></linearGradient></defs>';
const wrap=body=>`<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024" role="img"><title>派特岛 · 五岛爪印</title>${defs}${body}</svg>`;
const foreground=word+paw,logo=wrap('<rect width="1024" height="1024" fill="url(#sky)"/>'+foreground);
fs.writeFileSync(path.join(root,'static/images/pait-app-icon-f5.svg'),logo);
fs.writeFileSync(path.join(out,'logo-transparent.svg'),wrap(foreground));
fs.writeFileSync(path.join(out,'paw-outline.svg'),wrap(paw));
fs.writeFileSync(path.join(out,'logo-ink.svg'),wrap(foreground.replaceAll(cream,night).replaceAll('#FFC16A',night)));
for(const size of [1024,512,180,32])fs.writeFileSync(path.join(root,`static/images/pait-app-icon-f5${size===1024?'':'-'+size}.png`),new Resvg(logo,{fitTo:{mode:'width',value:size}}).render().asPng());
fs.writeFileSync(path.join(out,'logo-transparent.png'),new Resvg(wrap(foreground)).render().asPng());
fs.writeFileSync(path.join(root,'harmony/AppScope/resources/base/media/app_icon_paw.png'),new Resvg(logo,{fitTo:{mode:'width',value:512}}).render().asPng());
fs.writeFileSync(path.join(out,'brand-data.js'),'window.PawBrand='+JSON.stringify({pads,foreground,cream,night})+';\n');
if(!process.argv.includes('--capture')){console.log('Built five-island SVG and PNG brand assets');process.exit(0);}
(async()=>{
 const {chromium}=require('playwright');
 const capture=`<!doctype html><script src="/static/js/vendor/three.min.js"></script><script src="/static/js/vendor/GLTFLoader.js"></script><script>
 window.capture=async(url,width)=>{const T=THREE,r=new T.WebGLRenderer({alpha:true,antialias:true,preserveDrawingBuffer:true});r.setSize(640,640);r.outputEncoding=T.sRGBEncoding;r.toneMapping=T.ACESFilmicToneMapping;r.toneMappingExposure=1.12;const s=new T.Scene();s.add(new T.HemisphereLight(0xf4f4ed,0x506273,1.5));const l=new T.DirectionalLight(0xfff0d5,2.5);l.position.set(-10,30,8);s.add(l);const g=await new T.GLTFLoader().loadAsync(url),o=g.scene,b=new T.Box3().setFromObject(o),size=b.getSize(new T.Vector3()),c=b.getCenter(new T.Vector3());o.position.sub(c);const k=width/Math.max(size.x,size.z);o.scale.setScalar(k);o.position.multiplyScalar(k);s.add(o);const cam=new T.OrthographicCamera(-width*.66,width*.66,width*.66,-width*.66,.1,150);cam.position.set(0,60,0);cam.up.set(0,0,-1);cam.lookAt(0,0,0);r.render(s,cam);const png=r.domElement.toDataURL('image/png');const ctx=document.createElement('canvas').getContext('2d');ctx.canvas.width=ctx.canvas.height=640;ctx.drawImage(r.domElement,0,0);const a=ctx.getImageData(0,0,640,640).data,points=[];for(let i=0;i<128;i++){const t=i/128*Math.PI*2;let radius=0;for(let q=1;q<318;q++){const x=Math.round(320+Math.cos(t)*q),y=Math.round(320+Math.sin(t)*q);if(a[(y*640+x)*4+3]>100)radius=q;}points.push([Math.cos(t)*radius/640*width*1.32,Math.sin(t)*radius/640*width*1.32]);}r.dispose();return {png,points};};</script>`;
 const server=http.createServer((req,res)=>{if(req.url==='/capture'){res.setHeader('Content-Type','text/html');return res.end(capture);}const file=path.resolve(root,'.'+decodeURIComponent(req.url.split('?')[0]));if(!file.startsWith(root+path.sep)){res.writeHead(403);return res.end();}fs.readFile(file,(e,b)=>{if(e){res.writeHead(404);return res.end();}res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':'application/octet-stream');res.end(b);});});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const browser=await chromium.launch({headless:true,executablePath:process.env.PET_TEST_CHROME||'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 try{const page=await browser.newPage();await page.goto('http://127.0.0.1:'+server.address().port+'/capture');const captures=[];
  for(const p of pads){const model=p.key==='park'?'static/models/paw-commons-v3/preview.glb':`static/models/home-islands/${p.key}.glb`;
   const data=await page.evaluate(async({model,width})=>capture('/'+model,width),{model,width:p.key==='park'?18:9});
   fs.writeFileSync(path.join(out,p.key+'.png'),Buffer.from(data.png.split(',')[1],'base64'));captures.push({...p,points:data.points,model,sha256:require('node:crypto').createHash('sha256').update(fs.readFileSync(path.join(root,model))).digest('hex')});console.log('Captured real overhead:',p.name);
  }
  fs.writeFileSync(path.join(out,'island-data.js'),'window.PawIslands='+JSON.stringify(captures)+';\n');
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
