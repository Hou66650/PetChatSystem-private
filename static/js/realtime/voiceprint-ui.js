/* Enrollment sends PCM only to this app's local backend. No raw recording is retained. */
(function(){
 'use strict';
 let panel,recording=null,epoch=0;
 async function request(url,options){const r=await fetch(url,options);const d=await r.json();if(!r.ok)throw Error(d.error||'声纹操作失败');return d;}
 function message(text){panel.querySelector('[data-status]').textContent=text;}
 function stop(){epoch++;if(recording){clearInterval(recording.timer);clearTimeout(recording.end);recording.stream?.getTracks().forEach(t=>t.stop());recording.node?.disconnect();recording.ctx?.close().catch(()=>{});recording=null;}if(panel){panel.querySelector('[data-record]').disabled=false;panel.querySelector('[data-cancel]').hidden=true;}}
 async function refresh(){const s=await request('/api/voiceprint');const list=panel.querySelector('[data-list]');list.replaceChildren();panel.querySelector('[data-enable]').checked=s.requestedEnabled ?? s.enabled;
  panel.querySelector('[data-enable-hint]').textContent=!s.profiles.length?(s.requestedEnabled?'已保存开启意愿；请在下方录入声音，完成后识别才会生效。':'可以先勾选，再录入声音；录入前仍使用普通通话。'):(s.enabled?'已开启，下次通话生效。':'已关闭，下次通话使用普通模式。');
  for(const p of s.profiles){const row=document.createElement('p'),name=document.createElement('span'),del=document.createElement('button');name.textContent=p.name+' ';del.textContent='删除声纹';del.type='button';del.onclick=async()=>{try{await request('/api/voiceprint/'+p.id,{method:'DELETE'});await refresh();}catch(e){message(e.message);}};row.append(name,del);list.append(row);}
  message(s.ready?(s.profiles.length?'已录入 '+s.profiles.length+' 位熟人。新设置在下次通话生效。':'先录入自己的声音，宠物才有熟悉声音可比较。'):'本地声纹模型尚未安装。');
 }
 async function record(){
  const name=panel.querySelector('[data-name]').value.trim();if(!name){message('请先填写希望宠物怎样称呼你。');return;}
  stop();const token=epoch;panel.querySelector('[data-record]').disabled=true;panel.querySelector('[data-cancel]').hidden=false;message('正在申请麦克风…');
  try{
   let device;try{device=localStorage.getItem('rt_mic_id');}catch(e){}
   const stream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true,...(device?{deviceId:{exact:device}}:{})}});
   if(token!==epoch){stream.getTracks().forEach(t=>t.stop());return;}
   const ctx=new AudioContext({sampleRate:16000});recording={stream,ctx};await ctx.resume();await ctx.audioWorklet.addModule('/static/js/realtime/audio-capture-worklet.js');if(token!==epoch)return;
   const node=new AudioWorkletNode(ctx,'petchat-capture'),chunks=[];recording.node=node;
   node.port.onmessage=e=>{if(token===epoch&&e.data.type==='chunk')chunks.push(e.data.buffer);};ctx.createMediaStreamSource(stream).connect(node);
   let seconds=14;message('请自然说话：'+seconds+' 秒。可以介绍自己、聊聊今天做了什么。');recording.timer=setInterval(()=>message('继续自然说话，还剩 '+(--seconds)+' 秒…'),1000);
   recording.end=setTimeout(async()=>{
    if(token!==epoch)return;
    const pcm=new Uint8Array(chunks.reduce((n,b)=>n+b.byteLength,0));let n=0;for(const b of chunks){pcm.set(new Uint8Array(b),n);n+=b.byteLength;}
    stop();const uploadEpoch=epoch;message('正在本机提取声纹，首次运行可能稍慢…');panel.querySelector('[data-record]').disabled=true;
    try{await request('/api/voiceprint/enroll?name='+encodeURIComponent(name),{method:'POST',headers:{'Content-Type':'application/octet-stream'},body:pcm});if(uploadEpoch===epoch)await refresh();}catch(e){if(uploadEpoch===epoch)message(e.message);}finally{if(uploadEpoch===epoch)panel.querySelector('[data-record]').disabled=false;}
   },14000);
  }catch(e){if(token===epoch){stop();message(e.message||'麦克风不可用');}}
 }
 async function open(){
  document.dispatchEvent(new Event('voiceprint-settings-open'));
  if(!panel){panel=document.createElement('dialog');panel.className='toy-dialog';panel.id='voiceprint-dialog';panel.innerHTML='<header><h2>让它记住你的声音</h2><button type="button" data-close>关闭</button></header><p>录入本人或已同意录入的熟人声音。录音只送到当前应用后端提取特征，不保存原始录音；声纹可随时删除。</p><p>熟人更亲近，陌生人礼貌克制；听不清或不确定时保持中性。不是身份认证，也不能防录音冒充。</p><label><input type="checkbox" data-enable aria-describedby="voiceprint-enable-hint"> 通话中辨认熟悉声音</label><p id="voiceprint-enable-hint" data-enable-hint role="status"></p><div data-list></div><label>称呼 <input data-name maxlength="24" placeholder="例如：小林"></label><p>请在安静环境连续说话14秒，只有你一个人说话，尽量使用平时通话的麦克风。</p><button type="button" data-record>录入我的声音 · 14秒</button> <button type="button" data-cancel hidden>取消录音</button><p data-status role="status"></p><p>开启后先辨认再回复，会比普通通话稍慢；为避免把别人的话记成你的事，此模式不读写个人陪伴记忆。</p>';document.body.append(panel);panel.querySelector('[data-close]').onclick=()=>panel.close();panel.addEventListener('close',stop);panel.querySelector('[data-record]').onclick=record;panel.querySelector('[data-cancel]').onclick=()=>{stop();message('录音已取消。');};panel.querySelector('[data-enable]').onchange=async e=>{const checkbox=e.target,previous=!checkbox.checked;checkbox.disabled=true;try{await request('/api/voiceprint',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:e.target.checked})});await refresh();}catch(err){checkbox.checked=previous;message(err.message);}finally{checkbox.disabled=false;}};}
  panel.showModal();try{await refresh();}catch(e){message(e.message);}
 }
 window.VoiceprintUI={open};
})();
