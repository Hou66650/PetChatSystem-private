/* Export the exact seekable SVG timeline to H.264 for PowerPoint/WPS. */
const {chromium}=require('playwright'),fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {spawn,execFileSync}=require('node:child_process');
const {Resvg}=require('@resvg/resvg-js');
const root=path.resolve(__dirname,'..'),out=path.join(root,'static/brand/five-islands');
(async()=>{
 const ffmpeg=process.env.FFMPEG_PATH||execFileSync(path.join(root,'venv/Scripts/python.exe'),['-c','import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())'],{encoding:'utf8'}).trim();
 const browser=await chromium.launch({headless:true,executablePath:process.env.PET_TEST_CHROME||'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 const errors=[];
 try{const page=await browser.newPage({viewport:{width:1920,height:1080},deviceScaleFactor:1});page.on('pageerror',e=>errors.push(e.message));
  await page.goto(require('node:url').pathToFileURL(path.join(out,'index.html')).href+'?clean');await page.evaluate(()=>PawFilm.ready);
  const images=Object.fromEntries(['sakura','snow','room','camp','park'].map(key=>[key+'.png','data:image/png;base64,'+fs.readFileSync(path.join(out,key+'.png')).toString('base64')]));
  await page.evaluate(images=>{document.querySelectorAll('image').forEach(n=>n.setAttribute('href',images[n.getAttribute('href')]));const s=document.getElementById('stage');s.setAttribute('width','1920');s.setAttribute('height','1080');},images);
  const film=spawn(ffmpeg,['-y','-loglevel','error','-f','image2pipe','-vcodec','png','-framerate','30','-i','pipe:0','-an','-c:v','libx264','-preset','medium','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',path.join(out,'five-islands-logo.mp4')],{windowsHide:true});
  let stderr='';film.stderr.on('data',d=>stderr+=d);const finished=new Promise((ok,fail)=>{film.on('error',fail);film.on('close',code=>code?fail(Error(stderr)):ok());});
  const fontFile=path.join(process.env.WINDIR||'C:/Windows','Fonts/msyh.ttc'),font=fs.existsSync(fontFile)?{loadSystemFonts:false,fontFiles:[fontFile],defaultFontFamily:'Microsoft YaHei'}:{loadSystemFonts:true};
  for(let frame=0;frame<270;frame++){const svg=await page.evaluate(t=>{PawFilm.seek(t);return document.getElementById('stage').outerHTML;},Math.min(9,frame/30));const png=new Resvg(svg,{font}).render().asPng();if(!film.stdin.write(png))await new Promise((r,f)=>{const drained=()=>{film.stdin.off('error',failed);r();},failed=e=>{film.stdin.off('drain',drained);f(e);};film.stdin.once('drain',drained);film.stdin.once('error',failed);});if(frame%60===0)console.log('Exported frame',frame,'/ 270');}
  film.stdin.end();await finished;
  for(const [t,name]of [[0,'opening-frame.png'],[3,'outline-frame.png'],[9,'ending-frame.png']]){await page.evaluate(t=>PawFilm.seek(t),t);await page.screenshot({path:path.join(out,name)});}
  if(errors.length)throw Error(errors.join('\n'));console.log('Export complete: 1920×1080, 30 FPS, 9 seconds, H.264, no audio.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
