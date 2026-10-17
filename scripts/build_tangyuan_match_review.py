"""Package a real UE render and private reference video for local review.

No cloud upload. Requires imageio-ffmpeg and Pillow. This deliberately includes
a hard cut and same-time comparison rather than hiding pose errors in a fade.
"""
import argparse
import hashlib
import html
import json
import subprocess
from pathlib import Path
import imageio_ffmpeg
from PIL import Image,ImageDraw,ImageFont

p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--output',required=True);p.add_argument('--frames',required=True);p.add_argument('--motion',required=True)
p.add_argument('--revision',choices=('initial','sakura'),default='initial')
a=p.parse_args();out=Path(a.output);frames=Path(a.frames);source=Path(a.source);ff=imageio_ffmpeg.get_ffmpeg_exe()
motion=json.loads(Path(a.motion).read_text());report=json.loads((out/'unreal-report.json').read_text(encoding='utf-8'))
if not report.get('render_completed') or report.get('frame_count')!=30:
    raise RuntimeError('An actual completed 30-frame UE render is required')
if Path(report['frames_directory']).resolve()!=frames.resolve():
    raise ValueError('The requested frames do not match the completed UE job')
for i in range(30):
    with Image.open(frames/f'{i:04d}.png') as im:
        if im.size!=(720,1280):raise ValueError('Unexpected render dimensions')
refs=out/'review-real';refs.mkdir(exist_ok=True)

def run(args):
    subprocess.run([ff,'-hide_banner','-loglevel','error','-y',*map(str,args)],check=True)

run(['-i',source,'-vf',r'select=between(n\,42\,71),setpts=N/(30*TB)','-vsync','0','-start_number','0',refs/'%04d.png'])
font="fontfile='C\\:/Windows/Fonts/msyh.ttc':fontsize=30:fontcolor=white:box=1:boxcolor=black@0.5:boxborderw=12:x=22:y=24"
real_label='drawtext='+font+":text='真实影像'"
ue_label='drawtext='+font+":text='UE 5.8 · 动作验证'"
encoding=['-an','-c:v','libx264','-crf','19','-pix_fmt','yuv420p','-movflags','+faststart']
run(['-i',source,'-framerate','30','-start_number','0','-i',frames/'%04d.png','-filter_complex',
     f'[0:v]trim=end_frame=54,setpts=PTS-STARTPTS,setsar=1,{real_label}[r];[1:v]trim=start_frame=12:end_frame=30,setpts=PTS-STARTPTS,setsar=1,{ue_label}[u];[r][u]concat=n=2:v=1:a=0[v]',
     '-map','[v]','-r','30',*encoding,out/'汤圆-实拍接UE-原速验证.mp4'])
comparisons=out/'comparison-frames';comparisons.mkdir(exist_ok=True)
label_font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',30)
for i in range(30):
    canvas=Image.new('RGB',(1440,1280))
    canvas.paste(Image.open(refs/f'{i:04d}.png').convert('RGB'),(0,0))
    canvas.paste(Image.open(frames/f'{i:04d}.png').convert('RGB'),(720,0))
    d=ImageDraw.Draw(canvas);d.rectangle((0,0,1440,64),fill='#122327')
    d.text((20,12),f'真实影像 · {(42+i)/30:.3f} s',font=label_font,fill='white')
    d.text((740,12),f'UE 同帧 · 源帧 {42+i}',font=label_font,fill='white')
    canvas.save(comparisons/f'{i:04d}.png')
run(['-framerate','15/2','-start_number','0','-i',comparisons/'%04d.png','-r','30',*encoding,out/'汤圆-同帧对照-四倍慢放.mp4'])
run(['-framerate','30','-start_number','0','-i',frames/'%04d.png',*encoding,out/'汤圆-UE动作片段.mp4'])
face=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',19)
sheet=Image.new('RGB',(1080,720),'#122327');draw=ImageDraw.Draw(sheet)
for i,(path,title) in enumerate([(refs/'0011.png','实拍最后一帧 · 1.767 s'),(refs/'0012.png','实拍同一时刻 · 1.800 s'),(frames/'0012.png','UE 衔接第一帧 · 1.800 s')]):
    im=Image.open(path).convert('RGB').resize((360,640));sheet.paste(im,(i*360,60));draw.text((i*360+12,20),title,font=face,fill='#f3e9d3')
sheet.save(out/'切点三帧对照.png')
before=Image.open(out/'neutral-front.png').convert('RGB').resize((520,520));after=Image.open(out/'neutral-corrected.png').convert('RGB').resize((520,520))
sheet=Image.new('RGB',(1040,580),'#122327');sheet.paste(before,(0,60));sheet.paste(after,(520,60));draw=ImageDraw.Draw(sheet)
draw.text((20,20),'上一轮：已校正默认歪头' if a.revision=='sakura' else '原始默认姿态：头部朝侧面',font=face,fill='#f3e9d3');draw.text((540,20),'本轮：收肩、下颌与小舌尖' if a.revision=='sakura' else '修正后的默认姿态：头颈朝前',font=face,fill='#f3e9d3');sheet.save(out/'头颈修正对照.png')
relative=frames.relative_to(out).as_posix()
page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>汤圆 · 实拍与 UE 动作衔接</title>
<style>*{box-sizing:border-box}body{margin:0;background:#101c20;color:#ece8db;font:16px/1.75 "Microsoft YaHei",sans-serif}main{max-width:1100px;margin:auto;padding:50px 28px}h1{font-size:40px;line-height:1.2;margin:14px 0}h2{font-size:24px;margin:36px 0 14px}p{color:#bbc6c5}a{color:#e8bd76}section{padding:24px;margin:24px 0;background:#182a2e;border:1px solid #314144;border-radius:18px}.tag{color:#e8bd76;font-size:13px;letter-spacing:2px}video{display:block;background:#080e10;border-radius:12px;max-width:100%;max-height:680px;margin:auto}img{max-width:100%;display:block;border-radius:10px}.pair{display:grid;grid-template-columns:1fr 1fr;gap:14px}.pair img{width:100%}input[type=range]{width:100%;accent-color:#e8bd76}button{border:0;border-radius:8px;background:#e8bd76;color:#15252a;padding:9px 15px;cursor:pointer}small{color:#a7b7b9}.controls{display:flex;gap:12px;align-items:center;margin:12px 0}.stage{position:relative;max-width:420px;margin:auto}.stage .overlay{position:absolute;inset:0;opacity:.5}details{margin:20px 0;color:#bdc8c7}li{margin:8px 0}@media(max-width:600px){main{padding:28px 16px}h1{font-size:31px}section{padding:16px}}</style>
<main><div class="tag">TANGYUAN / SOURCE → UNREAL / LOCAL REVIEW</div><h1>让下一帧，接住汤圆。</h1><p>第一轮 UE 动作衔接验证。原视频 1.80 秒切入三维模型；保留直接切换，方便观察姿态差异。此页用于核对，不作为路演成片。</p>
<section><h2>先看原速衔接</h2><p>2.4 秒，30 fps；真实影像前 1.8 秒，随后 0.6 秒由 UE 5.8.3 实际渲染。环境使用樱花庭院地表贴图的测试场景，完整岛屿镜头尚未接入。</p><video controls playsinline preload="metadata" src="汤圆-实拍接UE-原速验证.mp4"></video></section>
<section><h2>同一时刻，四倍慢放</h2><p>左侧实拍，右侧 UE。覆盖源视频 1.40–2.40 秒；慢放只重复帧，没有生成补帧。</p><video controls playsinline preload="metadata" src="汤圆-同帧对照-四倍慢放.mp4"></video></section>
<section><h2>逐帧检查</h2><div class="controls"><button id="previous">上一帧</button><button id="next">下一帧</button><button id="cut">回到切点</button><output id="time"></output></div><input id="frame" aria-label="源视频帧" type="range" min="0" max="29" value="12"><div class="pair"><div><small>真实影像</small><img id="real" alt="真实视频对应帧"></div><div><small>UE 实际渲染</small><img id="virtual" alt="虚拟模型对应帧"></div></div><details><summary>叠加检查轮廓</summary><p>调节透明度，观察轮廓、头部和脚掌位置。</p><input id="opacity" aria-label="叠加透明度" type="range" min="0" max="100" value="50"><div class="stage"><img id="under" alt="原图"><img id="over" class="overlay" alt="UE 叠加层"></div></details></section>
<section><h2>头颈默认姿态已校正</h2><img src="头颈修正对照.png" alt="头部默认方向修正前后"><p>先修正模型本身保留的侧向头颈，再制作视频中的转头和低头。当前动作与相机由这段视频的人工标点拟合，已取消固定周期行走。</p></section>
<section><h2>切点三帧</h2><img src="切点三帧对照.png" alt="实拍末帧、同时刻实拍与 UE 首帧"></section>
<section><h2>这版的边界</h2><ul><li>鼻尖、头顶、尾尖的位置用于拟合；低重投影误差只说明这些人工标点对齐，不代表全身动作或真实三维姿态完全恢复。</li><li>前腿轮廓、着地时刻和被头部遮挡的脚掌仍需逐帧核对。遮挡腿部按连续姿态推定，尚不能作为精确运动捕捉结果。</li><li>当前模型没有完整下颌、舌头与表情绑定，嘴部细节还未复现；毛色、毛发和肩颈轮廓也仍需艺术修订。</li><li>UE 已实际导入骨骼动画并输出 30 帧；动作在 Blender 中拟合、烘焙为 FBX，经 Sequencer 播放与 Movie Render Queue 渲染。尚未搭建专用 UE Control Rig 控制面板。</li></ul><details><summary>技术记录与工程</summary><p><a href="unreal-report.json">UE 渲染记录</a> · <a href="matched-v3/pose-validation.json">31 帧骨骼检查</a> · <a href="motion-v3.json">镜头与动作拟合数据</a> · <a href="matched-v3/Tangyuan-matched.blend">Blender 工程</a> · <a href="matched-v3/Tangyuan-matched.fbx">UE 动画 FBX</a></p><p>本机 UE 工程：D:/PetChatSystem/roadshow-local/TangyuanUE/TangyuanUE.uproject。未公开上传真实影像，也未修改账号宠物。</p></details></section></main>
<script>const $=id=>document.getElementById(id);function update(){const n=+$('frame').value,s=String(n).padStart(4,'0'),r=`review-real/${s}.png`,u=`RENDER_DIR/${s}.png`;$('real').src=$('under').src=r;$('virtual').src=$('over').src=u;$('time').textContent=`源帧 ${42+n} · ${((42+n)/30).toFixed(3)} s${n===12?' · 切点':''}`;}$('frame').oninput=update;$('previous').onclick=()=>{$('frame').value=Math.max(0,+$('frame').value-1);update()};$('next').onclick=()=>{$('frame').value=Math.min(29,+$('frame').value+1);update()};$('cut').onclick=()=>{$('frame').value=12;update()};$('opacity').oninput=()=>{$('over').style.opacity=$('opacity').value/100};update();</script></html>'''.replace('RENDER_DIR',relative)
page=page.replace('preload="metadata" src="汤圆-实拍接UE-原速验证.mp4"','preload="metadata" poster="'+relative+'/0012.png" src="汤圆-实拍接UE-原速验证.mp4"')
page=page.replace('preload="metadata" src="汤圆-同帧对照-四倍慢放.mp4"','preload="metadata" poster="comparison-frames/0012.png" src="汤圆-同帧对照-四倍慢放.mp4"')
if a.revision=='sakura':
    if not report.get('island'):raise ValueError('Sakura review requires an imported real island')
    page=page.replace('第一轮 UE 动作衔接验证。','第二轮 UE 樱花庭院衔接验证。')
    page=page.replace('环境使用樱花庭院地表贴图的测试场景，完整岛屿镜头尚未接入。','环境已接入项目真实樱花庭院，保留上一轮的动作、1.80 秒切点和机位。')
    page=page.replace('头颈默认姿态已校正','肩颈与嘴部局部修订')
    page=page.replace('先修正模型本身保留的侧向头颈，再制作视频中的转头和低头。当前动作与相机由这段视频的人工标点拟合，已取消固定周期行走。','保留头颈朝前的默认姿态；连续收窄偏方的前肩，并同步移动毛发。新增下颌关节和小舌尖，开合量依据这段实拍手工设定。没有重做已对齐的身体轨迹。')
    page=page.replace('当前模型没有完整下颌、舌头与表情绑定，嘴部细节还未复现；毛色、毛发和肩颈轮廓也仍需艺术修订。','已加入小幅下颌开合与舌尖；口腔内部为艺术推定，完整表情、毛发和肩颈轮廓仍需修订，尚未获得主人对个体外貌的确认。')
    page=page.replace('matched-v3/','matched/').replace('motion-v3.json','motion.json')
    page=page.replace('31 帧骨骼检查</a>','31 帧骨骼检查</a> · <a href="island/placement-validation.json">庭院接地／遮挡检查</a>')
    placement=(Path(report['island']['source_fbx']).parent/'placement-validation.json').relative_to(out).as_posix()
    page=page.replace('island/placement-validation.json',html.escape(placement,quote=True))
    if (out/'樱花庭院-UE全景.png').exists():
        page=page.replace('<section><h2>先看原速衔接','<section><h2>这次进入真实庭院</h2><img src="樱花庭院-UE全景.png" alt="UE 实际渲染的樱花庭院全景"><p>用于核对环境和角色落位的独立全景图，不代表已完成从近景到全景的连续运镜。</p></section><section><h2>先看原速衔接')
if (out/'validation-summary.json').exists():
    checks=json.loads((out/'validation-summary.json').read_text(encoding='utf-8'))
    note=html.escape(checks.get('unresolved_engine_startup',''))
    page=page.replace('技术记录与工程</summary>','技术记录与工程</summary><p>检查记录：'+note+'。渲染完成不等于引擎全量自检通过。<a href="validation-summary.json">完整检查摘要</a></p>')
(out/'汤圆-UE动作衔接审阅.html').write_text(page,encoding='utf-8')
manifest={'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'cut_source_frame':54,'source_fps':30,'output_frames':72,'ue_frames':30,'comparison_source_start_frame':42,'ue_engine':report['engine'],'owner_approved':False,'full_motion_match_approved':False,'limitations':['occluded feet inferred','mouth/tongue not reconstructed','test ground, not full island']}
if a.revision=='sakura':
    manifest.update(revision='sakura',limitations=['occluded feet inferred','mouth interior inferred, small jaw/tongue added','coat and individual likeness still under review','continuous island reveal not yet produced'])
(out/'review-manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(out/'汤圆-UE动作衔接审阅.html')
