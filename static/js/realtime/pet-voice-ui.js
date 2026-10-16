/* Separate from speaker recognition: these voices speak the pet's new replies. */
(()=>{'use strict';
 let panel,scope,petId,petName,epoch=0,timer,raw=null,requestId=null,busy=false,enabled=false,sourceUrl,previewUrl,recording=null,recordEpoch=0;
 const $=key=>panel.querySelector('[data-'+key+']');
 function message(text){$('status').textContent=text;}
 function lock(value){busy=value;$('create').disabled=value||!!recording||!enabled||!raw||!$('consent').checked;$('file').disabled=value||!!recording;$('record').disabled=value||!!recording||!enabled;for(const b of $('list').querySelectorAll('button'))b.disabled=value||!!recording;$('reset').disabled=value||!!recording||!panel.dataset.activeVoice;}
 function publish(d){window.PetVoiceChanges?.publish({scope:d.scope,petId:d.petId,activeId:d.activeId});}
 async function api(url,options={}){const r=await fetch(url,{...options,headers:{'X-Profile-Scope':scope,...options.headers}});if(!r.ok){let d;try{d=await r.json();}catch{}throw Error(d?.error||'声音操作失败，请稍后再试');}return r;}
 function clearAudio(){for(const key of ['source','preview']){const audio=$(key);audio.pause();audio.hidden=true;audio.removeAttribute('src');audio.load();}if(sourceUrl)URL.revokeObjectURL(sourceUrl);if(previewUrl)URL.revokeObjectURL(previewUrl);sourceUrl=previewUrl=null;}
 function close(){epoch++;cancelRecording();clearTimeout(timer);raw=null;requestId=null;clearAudio();lock(false);}
 function button(text,fn){const b=document.createElement('button');b.type='button';b.textContent=text;b.onclick=async()=>{if(busy||recording)return;const token=epoch;lock(true);try{await fn();}catch(e){if(token===epoch)message(e.message);}finally{if(token===epoch)lock(false);}};return b;}
 async function refresh(token=epoch){
  const d=await (await api('/api/pet-voices?petId='+petId)).json();if(token!==epoch)return;
  scope=d.scope;enabled=d.enabled;$('hint').textContent=d.hint;lock(busy);
  $('list').replaceChildren();
  const labels={creating:'正在创建',ready:'可使用',failed:'未完成',uncertain:'结果待核查'};
  for(const p of d.profiles){
   const row=document.createElement('article'),title=document.createElement('strong'),meta=document.createElement('p'),actions=document.createElement('div');
   title.textContent=p.name+(p.id===d.activeId?' · 当前使用':'');meta.textContent=(labels[p.status]||p.status)+' · '+p.duration.toFixed(1)+' 秒参考录音';
   row.append(title,meta,actions);if(p.error){const e=document.createElement('p');e.textContent=p.error;row.append(e);}
   if(p.status==='ready'){
    actions.append(button('试听新声音',async()=>{const audio=$('preview');audio.pause();message('正在用这个声音说一句新话…');const task=window.PaitLoading?.start('生成音色试听');try{const blob=await (await api('/api/pet-voices/'+p.id+'/preview',{method:'POST'})).blob();if(token!==epoch)return;if(previewUrl)URL.revokeObjectURL(previewUrl);previewUrl=URL.createObjectURL(blob);audio.src=previewUrl;audio.hidden=false;try{await audio.play();message('试听满意后，点击“应用给'+petName+'”。');}catch{message('试听已生成，请点击播放器的播放按钮。');}task?.done();}catch(e){task?.fail();throw e;}finally{task?.cancel();}}));
    if(p.id!==d.activeId)actions.append(button('应用给'+petName,async()=>{const changed=await (await api('/api/pet-voices/selection',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({petId,id:p.id})})).json();publish(changed);if(token!==epoch)return;await refresh(token);message('已应用给'+petName+'。后续回复会使用这个音色；点击语音对话即可继续。');}));
   }
   if(p.status==='uncertain')actions.append(button('核查云端结果',async()=>{await api('/api/pet-voices/'+p.id+'/reconcile',{method:'POST'});if(token===epoch){await refresh(token);message('已找回云端创建的声音，可以试听。');}}));
   if(!['creating','uncertain'].includes(p.status))actions.append(button('删除',async()=>{await api('/api/pet-voices/'+p.id,{method:'DELETE'});if(p.id===d.activeId)publish({...d,activeId:null});if(token===epoch){await refresh(token);message('已删除声音及对应云端文件。');}}));
   $('list').append(row);
  }
  if(!d.profiles.length)$('list').textContent='还没有专属声音。直接录音或上传文件，给它一个熟悉的声音。';
  panel.dataset.activeVoice=d.activeId||'';
  $('current').textContent=d.activeId?'正在使用专属音色 · '+(d.profiles.find(p=>p.id===d.activeId)?.name||''):'正在使用默认音色';lock(busy);
  clearTimeout(timer);
  if(d.profiles.some(p=>p.status==='creating'))timer=setTimeout(()=>refresh(token).catch(e=>{if(token===epoch)message(e.message);}),2000);
  return d;
 }
 async function convert(file){
  if(file.size>20*1024*1024)throw Error('原始文件不能超过 20MB，请截取 3–30 秒录音。');
  const ctx=new AudioContext();let decoded;
  try{decoded=await ctx.decodeAudioData(await file.arrayBuffer());}finally{await ctx.close();}
  if(decoded.duration<3||decoded.duration>30)throw Error('请选择 3–30 秒录音，推荐 10–20 秒；不会自动裁掉你的录音。');
  const offline=new OfflineAudioContext(1,Math.round(decoded.duration*24000),24000),node=offline.createBufferSource();node.buffer=decoded;node.connect(offline.destination);node.start();
  const samples=(await offline.startRendering()).getChannelData(0),buffer=new ArrayBuffer(44+samples.length*2),view=new DataView(buffer);
  const string=(at,s)=>{for(let i=0;i<s.length;i++)view.setUint8(at+i,s.charCodeAt(i));};
  string(0,'RIFF');view.setUint32(4,36+samples.length*2,true);string(8,'WAVE');string(12,'fmt ');view.setUint32(16,16,true);view.setUint16(20,1,true);view.setUint16(22,1,true);view.setUint32(24,24000,true);view.setUint32(28,48000,true);view.setUint16(32,2,true);view.setUint16(34,16,true);string(36,'data');view.setUint32(40,samples.length*2,true);
  for(let i=0;i<samples.length;i++)view.setInt16(44+i*2,Math.round(Math.max(-1,Math.min(1,samples[i]))*32767),true);
  return new Blob([buffer],{type:'audio/wav'});
 }

 function releaseRecording(r){if(!r)return;clearInterval(r.timer);clearTimeout(r.limit);r.stream?.getTracks().forEach(t=>t.stop());r.source?.disconnect();r.ctx?.close().catch(()=>{});}
 function cancelRecording(){recordEpoch++;const r=recording;recording=null;if(r){r.cancelled=true;if(r.recorder?.state==='recording')r.recorder.stop();releaseRecording(r);}if(panel){$('recording').hidden=true;$('record').textContent='直接录音';lock(busy);}}
 async function prepare(file,token=epoch){
  raw=null;requestId=null;clearAudio();lock(true);const task=window.PaitLoading?.start('检查参考录音');
  try{const audio=await convert(file);if(token!==epoch)return;raw=audio;requestId=crypto.randomUUID();sourceUrl=URL.createObjectURL(raw);$('source').src=sourceUrl;$('source').hidden=false;message('录音已准备好，可先听原音再创建。');task?.done();}
  catch(e){if(token===epoch)message(e.message);task?.fail();}finally{task?.cancel();if(token===epoch)lock(false);}
 }
 async function record(){
  if(busy||recording||!enabled)return;
  if(!navigator.mediaDevices?.getUserMedia||!window.MediaRecorder){message('当前浏览器无法直接录音，请用 Chrome / Edge 打开 HTTPS 或本机页面，或上传录音文件。');return;}
  cancelRecording();const token=epoch,take=recordEpoch,r={cancelled:false};recording=r;clearAudio();raw=null;requestId=null;$('file').value='';$('recording').hidden=false;$('record-stop').disabled=true;lock(false);message('正在申请麦克风，请允许访问…');
  try{
   let device;try{device=localStorage.getItem('rt_mic_id');}catch{}
   const audio={channelCount:1,echoCancellation:true,noiseSuppression:true};
   try{r.stream=await navigator.mediaDevices.getUserMedia({audio:{...audio,...(device?{deviceId:{exact:device}}:{})}});}catch(e){if(e.name!=='OverconstrainedError'||!device)throw e;r.stream=await navigator.mediaDevices.getUserMedia({audio});}
   if(token!==epoch||take!==recordEpoch){releaseRecording(r);return;}
   r.ctx=new AudioContext();await r.ctx.resume();if(token!==epoch||take!==recordEpoch){releaseRecording(r);return;}
   const analyser=r.ctx.createAnalyser();analyser.fftSize=256;r.source=r.ctx.createMediaStreamSource(r.stream);r.source.connect(analyser);const levels=new Float32Array(analyser.fftSize);
   const mime=['audio/webm;codecs=opus','audio/webm','audio/mp4'].find(t=>MediaRecorder.isTypeSupported(t));r.recorder=new MediaRecorder(r.stream,mime?{mimeType:mime}:{});const chunks=[];
   r.recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data);};
   r.recorder.onerror=()=>{if(token===epoch&&take===recordEpoch){cancelRecording();message('录音中断，请检查麦克风后重试。');}};
   r.recorder.onstop=async()=>{releaseRecording(r);if(r.cancelled||token!==epoch||take!==recordEpoch)return;recording=null;$('recording').hidden=true;$('record').textContent='重新录音';await prepare(new Blob(chunks,{type:r.recorder.mimeType}),token);};
   r.recorder.start(200);r.started=performance.now();$('record-stop').disabled=false;message('请自然说话，推荐 10–20 秒。录音不会自动上传。');
   const tick=()=>{const seconds=(performance.now()-r.started)/1000;$('record-time').textContent=seconds.toFixed(1)+' 秒 / 29 秒';analyser.getFloatTimeDomainData(levels);const rms=Math.sqrt(levels.reduce((n,v)=>n+v*v,0)/levels.length);$('record-level').value=Math.min(1,rms*8);};tick();r.timer=setInterval(tick,100);r.limit=setTimeout(()=>{if(recording===r)stopRecording();},29000);
  }catch(e){if(token===epoch&&take===recordEpoch){cancelRecording();message(e.name==='NotAllowedError'?'麦克风权限未获允许，请在浏览器地址栏允许麦克风后重试。':e.name==='NotFoundError'?'没有找到麦克风，请连接后重试。':'无法开始录音，请检查麦克风是否被占用。');}}
 }
 function stopRecording(){const r=recording;if(!r?.recorder||r.recorder.state!=='recording')return;$('record-stop').disabled=true;clearInterval(r.timer);clearTimeout(r.limit);message('正在整理录音…');r.recorder.stop();releaseRecording(r);}
 window.addEventListener('pagehide',()=>{if(panel)close();});
 async function upload(){
  if(busy||!raw||!$('consent').checked)return;const token=epoch,task=window.PaitLoading?.start('上传录音并创建专属音色');lock(true);
  try{
   const name=$('name').value.trim();if(!name)throw Error('请给这段声音取一个名字。');
   const data=new FormData();data.set('audio',raw,'reference.wav');data.set('petId',petId);data.set('name',name);data.set('transcript',$('transcript').value.trim());data.set('consent','true');data.set('requestId',requestId);
   const created=await (await api('/api/pet-voices',{method:'POST',body:data})).json();
   if(token!==epoch)return;message('正在创建，通常需要等待一会儿；可以关闭窗口，稍后回来查看。');task?.update('智谱正在创建专属音色');
   for(let i=0;i<150&&token===epoch;i++){
    const d=await refresh(token);const row=d?.profiles.find(p=>p.id===created.id);
    if(row?.status!=='creating'){if(row?.status==='ready'){task?.done();message('专属声音已创建。先试听，再应用给'+petName+'。');}else{task?.fail();message(row?.error||'创建结果尚未确认，请稍后查看。');}return;}
    clearTimeout(timer);await new Promise(r=>setTimeout(r,2000));
   }
  }catch(e){if(token===epoch)message(e.message);task?.fail();}
  finally{task?.cancel();if(token===epoch)lock(false);}
 }
 async function open(id,name){
  if(!panel){
   const css=document.createElement('link');css.rel='stylesheet';css.href='/static/css/pet-voice.css';document.head.append(css);
   panel=document.createElement('dialog');panel.id='pet-voice-dialog';panel.innerHTML=`<header><div><small>派特岛 · 专属声音</small><h2 data-title></h2></div><button type="button" data-close aria-label="关闭声音设置">✕</button></header><p data-current></p><p>上传人的说话录音，让它用这个音色说出新的回复。这里改变宠物的说话声音，不影响熟人声纹识别或动物叫声。</p><p data-hint></p><section><label>声音名称<input data-name maxlength="32" placeholder="例如：温柔的陪伴"></label><label>上传参考录音<input data-file type="file" accept="audio/*,.wav,.mp3,.m4a"></label><button type="button" data-record>直接录音</button><div data-recording hidden><strong data-record-time>0.0 秒 / 29 秒</strong><progress data-record-level max="1" value="0" aria-label="麦克风音量"></progress><button type="button" data-record-stop>停止并试听</button><button type="button" data-record-cancel>取消录音</button></div><p class="pet-voice-note">可自然读一段话：“今天想和你一起在岛上散散步，看看新开的花。听到我的声音，就慢慢走过来吧。”录满 29 秒自动停止。</p><small>3–30 秒，推荐 10–20 秒清晰单人说话，无背景音乐。支持浏览器可解码的 WAV、MP3、M4A，文件不超过 20MB。</small><audio data-source controls hidden></audio><label>录音原文（可选）<textarea data-transcript maxlength="1000" rows="2" placeholder="如填写，请与录音实际说的话一致"></textarea></label><label class="pet-voice-consent"><input data-consent type="checkbox">这是本人或已获授权用于声音复刻的录音，同意发送至智谱生成音色。</label><button type="button" data-create disabled>创建专属声音</button></section><p data-status role="status" aria-live="polite"></p><audio data-preview controls hidden></audio><h3>为这只宠物保存的声音</h3><div data-list></div><button type="button" data-reset>恢复默认声音</button><p class="pet-voice-note">设置按账号和宠物独立保存。语音通话会先生成回复，再用专属音色朗读，等待可能比默认声音稍长。样本在本机只作临时处理；删除会请求清理云端音色和样本。</p>`;
   document.body.append(panel);$('close').onclick=()=>panel.close();panel.addEventListener('close',()=>{if(!panel.open)close();});
   $('consent').onchange=()=>lock(busy);$('create').onclick=upload;
   $('file').onchange=()=>{const file=$('file').files[0];if(file)void prepare(file);};
   $('record').onclick=record;$('record-stop').onclick=stopRecording;$('record-cancel').onclick=()=>{cancelRecording();message('录音已取消，可以重新录制或上传文件。');};
   $('reset').onclick=async()=>{if(busy||recording)return;const token=epoch;lock(true);try{const d=await (await api('/api/pet-voices/selection',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({petId,id:null})})).json();publish(d);if(token===epoch){await refresh(token);message('已恢复默认声音，后续回复将使用默认音色。');}}catch(e){if(token===epoch)message(e.message);}finally{if(token===epoch)lock(false);}};
  }
  if(panel.open)panel.close();close();petId=Number(id);petName=name||'这只宠物';enabled=false;scope=window.COMPANION_SCOPE;const token=epoch;
  $('title').textContent=petName+'的声音';$('name').value='';$('file').value='';$('transcript').value='';$('consent').checked=false;$('source').hidden=$('preview').hidden=true;$('list').replaceChildren();message('正在读取声音设置…');lock(false);
  document.dispatchEvent(new Event('pet-voice-settings-open'));panel.showModal();
  try{await refresh(token);if(token===epoch)message('上传录音或点击“直接录音”，生成后不会自动替换当前声音。');}catch(e){if(token===epoch)message(e.message);}
 }
 window.PetVoiceUI={open};
})();
