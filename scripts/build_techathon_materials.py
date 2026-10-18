"""Build a curated judging bundle. Private team/reference inputs stay outside Git.

Use the PDF and Presentations skill workflows before running the corresponding
authoring steps. This builder never copies the repository, uploads or databases.
"""
from __future__ import annotations
import argparse
import hashlib
import html
import json
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / 'docs/techathon-materials/content.json'
STYLE = '''body{margin:0;background:#f4f1e8;color:#18383b;font:17px/1.8 "Microsoft YaHei",sans-serif}main{max-width:960px;margin:50px auto;padding:0 32px}h1{font-size:42px;line-height:1.3}h2{font-size:27px;margin-top:38px}h3{font-size:20px;margin-bottom:8px}p{white-space:pre-line}a{color:#206b70}section{padding:24px 0;border-bottom:1px solid #c9d5ce}.tag{font-size:13px;letter-spacing:2px;color:#657c78}small{color:#657c78}nav a{display:block;padding:8px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#e5eae2;padding:24px}video{width:100%;background:#15253a}label{display:block;margin:12px 0}input{width:18px;height:18px}table{border-collapse:collapse;width:100%}td,th{padding:10px;text-align:left;border-bottom:1px solid #c9d5ce}@media print{body{background:white;font-size:11pt}main{margin:0;max-width:none}h1{font-size:26pt}h2{font-size:18pt}section{break-before:page;border:0}.no-print{display:none}a{color:inherit}pre{font-size:10pt}}'''

def write_html(path, title, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(title)+'</title><style>'+STYLE+'</style><main>'+body+'</main></html>',encoding='utf-8')

def sha(path):
    return hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()

def prepare(a):
    data=json.loads(CONTENT.read_text('utf-8'))
    team=json.loads(Path(a.team).read_text('utf-8'))
    out=Path(a.out); build=Path(a.build)
    out.mkdir(parents=True,exist_ok=True); (build/'assets').mkdir(parents=True,exist_ok=True)
    rep={'{{TEAM}}':'\n\n'.join(f"{m['name']}｜{m['role']}\n{m['school']}，{m['program']}" for m in team['members']), '{{TEAM_NAME}}':team.get('team_name') or '________________', '{{CONTACT}}':team.get('contact') or '________________（待填写）'}
    for page in data['pages']:
        for block in page['blocks']:
            for key,value in rep.items(): block['p']=block['p'].replace(key,value)
    data['team']=team
    assert len(data['slides'])==11 and sum(s['seconds'] for s in data['slides'])==285
    assert all(s.get('notes') for s in data['slides']), 'Each slide needs reviewed narration'
    (build/'deck-data.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),'utf-8')
    sources={
      'tangyuan.png':Path(a.reference),
      'opening-frame.png':ROOT/'static/brand/five-islands/opening-frame.png',
      'ending-frame.png':ROOT/'static/brand/five-islands/ending-frame.png',
      'husky-stages.png':ROOT/'art/pet-growth-v1/review/husky-stages.png',
      'shiba-stages.png':ROOT/'art/pet-growth-v1/review/shiba-stages.png',
      'park.png':build/'assets/park.png' if (build/'assets/park.png').exists() else ROOT/'art/paw-commons-v2/review/10-runtime-park.png',
      'memory-detail.png':build/'assets/memory-detail.png',
      'den.png':build/'assets/den.png',
    }
    assetdir=out/'03_展示材料/素材'; assetdir.mkdir(parents=True,exist_ok=True)
    provenance=[]
    for name,source in sources.items():
        if source.resolve()!=(build/'assets'/name).resolve():shutil.copy2(source,build/'assets'/name)
        shutil.copy2(source,assetdir/name)
        origin='主人提供视频的草坪参考帧 V1-06.5s；比赛展示素材' if name=='tangyuan.png' else ('隔离 Demo 实际运行截图，2026-10-18' if source.is_relative_to(build) else source.relative_to(ROOT).as_posix())
        provenance.append({'file':name,'source':origin,'sha256':sha(source)})
    (assetdir/'来源.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2),'utf-8')

    manual=out/'01_说明文档'
    sections=[]
    for i,p in enumerate(data['pages']):
        sections.append(f'<section id="p{i+1}"><p class="tag">{html.escape(p["tag"])}</p><h2>{i+1:02d}　{html.escape(p["title"])}</h2>'+''.join('<h3>'+html.escape(b['h'])+'</h3><p>'+html.escape(b['p'])+'</p>' for b in p['blocks'])+'</section>')
    write_html(manual/'项目说明与技术资料.html',data['project'], '<p class="tag">TECHATHON 2026 · 提交材料</p><h1>派特岛<br>PAIT ISLAND</h1><p>说明、实现与来源，均可追溯。</p><p>团队名称留空；签署与仓库权限需由团队完成。</p>'+''.join(sections))
    write_html(manual/'原创声明_待签署.html','原创声明签署稿','<h1>原创与资源使用声明</h1>'+sections[3])
    write_html(manual/'成员信息.html','参赛成员','<h1>参赛成员信息</h1><p>团队名称：'+html.escape(rep['{{TEAM_NAME}}'])+'</p><p>'+html.escape(rep['{{TEAM}}'])+'</p><p>联系人：'+html.escape(rep['{{CONTACT}}'])+'</p>')
    render_pdf(data,manual/'项目说明与技术资料.pdf')

    project=out/'02_项目内容'; project.mkdir(exist_ok=True)
    write_html(project/'仓库与技术入口.html','代码与技术入口','<h1>代码与技术入口</h1><p><a href="'+data['repo']+'/tree/cfe0c74">查看核对基线 cfe0c74</a></p><p><a href="'+data['repo']+'/tree/codex/v1.4.0">查看工作分支 codex/v1.4.0</a></p><p>这是私有仓库，评委需先获得访问权限。代码通过仓库提供，本包不含完整离线源码与大型模型。</p>'+sections[2]+sections[6])
    write_html(project/'第三方资源说明.html','第三方资源说明','<h1>第三方资源说明</h1>'+sections[4]+sections[5])
    tech=project/'技术文档';tech.mkdir(exist_ok=True)
    docs=['pet-imprint.md','desktop-agent-implementation.md','PORTALS.md','public-pet-park.md','pet-quality-gates.md','five-island-brand.md']
    for name in docs:
        if not (ROOT/'docs'/name).exists():raise FileNotFoundError(name)
        shutil.copy2(ROOT/'docs'/name,tech/name)
    for name in ['requirements.txt','desktop/package.json','desktop/package-lock.json']:
        target=project/'依赖'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/name,target)
    shutil.copy2(ROOT/'CHANGELOG.md',tech/'CHANGELOG.md')
    source_files=['app/services/pet_imprint_service.py','app/services/pet_call_service.py','static/js/den/pet-imprint-runtime.js','test/imprint_review_server.py','requirements.txt','desktop/package-lock.json']
    source_manifest=[]
    for source_name in source_files:
        raw=subprocess.check_output(['git','show',data['baseline']+':'+source_name],cwd=ROOT)
        source_manifest.append({'path':source_name,'baseline':data['baseline'],'sha256':hashlib.sha256(raw).hexdigest()})
    (project/'源码基线摘要.json').write_text(json.dumps(source_manifest,ensure_ascii=False,indent=2),'utf-8')
    license_dir=project/'第三方许可';license_dir.mkdir(exist_ok=True)
    if a.ppt_master:
        shutil.copy2(Path(a.ppt_master)/'LICENSE',license_dir/'PPT-Master-MIT.txt')
    for name,target in [('desktop/vendor/openpets/LICENSE','OpenPets-MIT.txt'),('desktop/vendor/openpets/README.md','OpenPets-适配说明.md'),('static/js/vendor/three-mesh-bvh-LICENSE.txt','three-mesh-bvh-MIT.txt')]:
        shutil.copy2(ROOT/name,license_dir/target)
    for name in ['three.min.js','marked.min.js','html2canvas.min.js','jspdf.umd.min.js']:
        raw=(ROOT/'static/js/vendor'/name).read_text('utf-8')
        match=re.search(r'/\*[\s\S]*?\*/',raw)
        (license_dir/(name+'-原文件声明.txt')).write_text(match.group(0) if match else '未找到文件头声明','utf-8')
    metadata_script='''import importlib.metadata as m,json,pathlib,shutil,sys
out=pathlib.Path(sys.argv[1]); rows=[]
for name in ['Flask','requests','PyJWT','Pillow','imageio-ffmpeg']:
 d=m.distribution(name);md=d.metadata
 rows.append(dict(name=name,version=d.version,license=md.get('License-Expression') or md.get('License'),project_urls=md.get_all('Project-URL'),home=md.get('Home-page'),requirements=d.requires))
 for f in d.files or []:
  if ('.dist-info/licenses/' in str(f).replace('\\\\','/') or '.dist-info/LICENSE' in str(f)) and pathlib.Path(d.locate_file(f)).is_file():
   dst=out/'第三方许可'/name/pathlib.Path(str(f)).name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(d.locate_file(f),dst)
(out/'Python依赖快照.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
'''
    subprocess.run([a.project_python,'-X','utf8','-c',metadata_script,str(project)],check=True)

    demo=out/'03_展示材料'
    commands='''# PowerShell，先进入完整克隆的仓库根目录
git clone --branch codex/v1.4.0 https://github.com/Hou66650/PetChatSystem-private.git
Set-Location PetChatSystem-private
# 可选：固定到材料核对基线，避免后续改动影响彩排
git checkout cfe0c74
py -3.11 -m venv .venv
.\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt
$env:PET_IMPRINT_PORT = "5094"
.\\.venv\\Scripts\\python.exe -X utf8 test/imprint_review_server.py
# 浏览器打开 http://127.0.0.1:5094/__qa/tangyuan
'''
    demo_body='<h1>现场 Demo 操作手册</h1><p>先完成依赖与模型准备，再上台。本手册不使用生产账号。</p><h2>1. 独立启动</h2><pre>'+html.escape(commands)+'</pre><h2>2. 回忆演示，建议 30 秒</h2><p>打开回忆页，说明活泼和安静偏好来自主人的真实描述。展示“前伏邀玩”仍为待确认草稿。进入小窝 → 动作 → 熟悉的样子 → 一起玩一会儿，检查未确认动作不会冒充个体记忆执行。不要现场随意勾选确认，也不要把未知音轨称为汤圆叫声。</p><h2>3. 桌面传送与审批，另行彩排</h2><p>按附带技术文档连接完整服务与 Electron 客户端。同一账号在网页发起桌面传送，检查客户端认领和抵达；提出一个短提醒，核对内容后批准，观察实际完成和通知回执；召回宠物。出现未知结果时如实展示状态。该链路不由上述隔离回忆服务器提供。</p><pre>Set-Location desktop\nnpm ci\nnpm start</pre><h2>4. 离线备用</h2><p>使用《离线演示.html》播放回忆模块录屏或 9 秒 Logo 动画。前者是实际浏览器录屏，后者是品牌转场，两者均不是完整汤圆个体还原影片。PPT 使用楷体标题、微软雅黑正文，含淡入转场和分步显现。第 02 页已嵌入 Logo 视频，放映时点击右侧岛屿播放；同包 MP4 与 HTML 为备用。换页由讲述人控制。</p><h2>5. 故障与停止</h2><p>端口占用时换 PET_IMPRINT_PORT，并同时更换浏览器地址；模型空白时检查 GLB/Vendor 路径和完整签出。Ctrl+C 停止隔离服务，其临时演示库不保留。不要公开这个测试账号入口或将它用作生产服务。</p>'
    write_html(demo/'Demo操作手册.html','Demo操作手册',demo_body)
    # Rebuild the delivery outline from the actual deck rather than shipping
    # historical market figures, stale team placeholders or broken local links.
    speech_body='<h1>五分钟口播与彩排</h1><p>汤圆主人第一人称。11 页共 285 秒，预留 15 秒。按正常语速和彩排结果删减，不加速真实影像。</p>'
    for i,slide in enumerate(data['slides'],1):
        speech_body+=f'<section><p class="tag">{i:02d} / {slide["seconds"]} 秒</p><h2>{html.escape(slide["title"]).replace(chr(10)," ")}</h2><p>{html.escape(slide["notes"])}</p><small>{html.escape(slide["footer"])}</small></section>'
    speech_body+='<h2>播放安排</h2><p>第 02 页点击右侧岛屿播放内嵌 9 秒 Logo 动画；第 04 页可用回忆模块录屏；第 07 页只演示已经在比赛电脑彩排过的桌面传送与审批。未完成汤圆专属模型审核时使用真实照片和标准伙伴演示。Logo 已嵌入，回忆录屏通过离线播放页单独打开。</p><p><a href="离线演示.html">打开离线演示播放器</a></p>'
    write_html(demo/'五分钟路演大纲.html','五分钟口播与彩排',speech_body)
    brand=demo/'五岛Logo动画';shutil.copytree(ROOT/'static/brand/five-islands',brand,dirs_exist_ok=True)
    # Runtime support files are local; no GLB is needed for this animation.
    write_html(demo/'离线演示.html','派特岛离线演示','<h1>派特岛离线演示</h1><h2>真实回忆模块</h2><p>隔离服务实机录屏；标准柴犬作为动作载体。汤圆的专属模型与步态仍待审核。草稿未确认，不触发其对应的回忆动作。视频无解说音轨。</p><video controls preload="metadata" src="回忆模块实机演示_标准柴犬载体.mp4"></video><h2>五岛轮廓与品牌标志</h2><p>9 秒品牌动画，不是完整产品演示。</p><video controls preload="metadata" src="五岛Logo动画/five-islands-logo.mp4"></video><p><a href="五岛Logo动画/index.html">打开可拖动进度的 Logo 动画</a></p>')
    script='''<script>document.querySelectorAll('input[type=checkbox]').forEach((e,i)=>{try{e.checked=localStorage.getItem('pait-submission-'+i)==='1';e.addEventListener('change',()=>localStorage.setItem('pait-submission-'+i,e.checked?'1':'0'))}catch(_){}})</script>'''
    checks=['成员资料与联系人已核对','原创声明已由成员审阅签署','评委账号能打开私有仓库','旧模型、动作库和生成记录来源已核对','主人已确认比赛影像展示范围','五分钟计时与比赛设备彩排完成']
    write_html(out/'开始阅读.html','派特岛提交材料','<p class="tag">TECHATHON / 2026</p><h1>派特岛<br>比赛提交材料</h1><p>按评委要求整理为三类。团队名称留空。需要签名、账号授权与来源补齐的事项列在下方。</p><h2>01 说明文档</h2><nav><a href="01_说明文档/项目说明与技术资料.pdf">项目说明与技术资料 · PDF</a><a href="01_说明文档/项目说明与技术资料.html">可编辑 HTML 版本</a><a href="01_说明文档/成员信息.html">成员信息</a><a href="01_说明文档/原创声明_待签署.html">原创声明 · 待签署</a></nav><h2>02 项目内容</h2><nav><a href="02_项目内容/仓库与技术入口.html">私有代码仓库与技术入口</a><a href="02_项目内容/第三方资源说明.html">第三方代码、API、模型与数据来源</a></nav><h2>03 展示材料</h2><nav><a href="03_展示材料/派特岛_五分钟路演.pptx">11 页可编辑 PPT</a><a href="03_展示材料/PPT预览.html">浏览器逐页预览 PPT</a><a href="03_展示材料/五分钟路演大纲.html">口播与路演大纲</a><a href="03_展示材料/Demo操作手册.html">现场 Demo 操作手册</a><a href="03_展示材料/离线演示.html">离线 MP4 备用演示与 Logo 动画</a></nav><h2>提交前由团队确认</h2>'+''.join('<label><input type="checkbox"> '+c+'</label>' for c in checks)+'<p><small>复选框仅保存在当前浏览器；不代表系统已签署声明或授权评委。代码通过私有仓库提供，本包未包含完整离线代码、大型模型和运行数据。</small></p>'+script)
    print(json.dumps({'prepared':str(out),'pages':len(data['pages']),'slides':len(data['slides'])},ensure_ascii=False))

def render_pdf(data,target):
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Paragraph
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    pdfmetrics.registerFont(TTFont('YaHei','C:/Windows/Fonts/msyh.ttc',subfontIndex=0))
    pdfmetrics.registerFont(TTFont('YaHeiBold','C:/Windows/Fonts/msyhbd.ttc',subfontIndex=0))
    target.parent.mkdir(parents=True,exist_ok=True)
    c=canvas.Canvas(str(target),pagesize=A4);c.setTitle(data['project']+' - 项目说明与技术资料');c.setAuthor('派特岛参赛团队')
    w,h=A4;style=ParagraphStyle('body',fontName='YaHei',fontSize=10.6,leading=17.5,textColor='#243e42',wordWrap='CJK',splitLongWords=True)
    for num,p in enumerate(data['pages'],1):
        c.setFillColorRGB(.973,.969,.945);c.rect(0,0,w,h,stroke=0,fill=1)
        c.setFillColorRGB(.37,.48,.45);c.setFont('YaHei',9);c.drawString(44,h-46,p['tag'])
        c.setFillColorRGB(.08,.19,.23);c.setFont('YaHeiBold',22);c.drawString(44,h-91,p['title'])
        y=h-125
        for block in p['blocks']:
            c.setFont('YaHeiBold',12);c.setFillColorRGB(.14,.35,.34);c.drawString(44,y,block['h']);y-=12
            para=Paragraph(html.escape(block['p']).replace('\n','<br/>'),style)
            _,ph=para.wrap(w-88,1000)
            if y-ph<56:raise ValueError(f'PDF page {num} overflow at {block["h"]}, y={y-ph}')
            para.drawOn(c,44,y-ph);y-=ph+23
        c.setStrokeColorRGB(.73,.79,.75);c.line(44,40,w-44,40)
        c.setFillColorRGB(.37,.48,.45);c.setFont('YaHei',8);c.drawString(44,26,'派特岛 PAIT ISLAND   /   TECHATHON 2026');c.drawRightString(w-44,26,f'{num:02d} / {len(data["pages"]):02d}')
        c.showPage()
    c.save()

def finalize(a):
    out=Path(a.out)
    if a.build:
        build=Path(a.build); preview=out/'03_展示材料/PPT逐页预览';preview.mkdir(exist_ok=True)
        for i in range(1,12):shutil.copy2(build/'rendered'/f'slide-{i:02d}.png',preview/f'slide-{i:02d}.png')
        body='<h1>五分钟路演 · 逐页预览</h1><p>楷体标题、微软雅黑正文。11 页原生可编辑 PPTX 含淡入转场、分步显现与第 02 页点击播放的 Logo 视频。下方是 PowerPoint 导出的静态预览。</p><p><a href="派特岛_五分钟路演.pptx">打开 PPTX</a></p>'
        if (out/'03_展示材料/派特岛_五分钟路演_静态预览.pdf').exists():
            body+='<p><a href="派特岛_五分钟路演_静态预览.pdf">打开静态 PDF</a></p>'
        if (out/'03_展示材料/PPT制作源文件/README.md').exists():
            body+='<p><a href="PPT制作源文件/README.md">PPT Master 源文件说明</a></p>'
        body+=''.join(f'<section><p class="tag">{i:02d} / 11</p><img style="width:100%;height:auto" src="PPT逐页预览/slide-{i:02d}.png" alt="第 {i} 页"></section>' for i in range(1,12))
        write_html(out/'03_展示材料/PPT预览.html','PPT逐页预览',body)
    from html.parser import HTMLParser
    from urllib.parse import urlsplit,unquote
    class Links(HTMLParser):
        def __init__(self):super().__init__();self.links=[]
        def handle_starttag(self,tag,attrs):
            for k,v in attrs:
                if k in ('href','src') and v:self.links.append(v)
    for page in out.rglob('*.html'):
        parser=Links();parser.feed(page.read_text('utf-8'))
        for href in parser.links:
            url=urlsplit(href)
            if url.scheme or not url.path:continue
            dest=(page.parent/unquote(url.path)).resolve()
            assert dest.is_relative_to(out.resolve()) and dest.exists(),(page,href)
    needed=['开始阅读.html','01_说明文档/项目说明与技术资料.pdf','03_展示材料/派特岛_五分钟路演.pptx','03_展示材料/回忆模块实机演示_标准柴犬载体.mp4','03_展示材料/五岛Logo动画/five-islands-logo.mp4']
    for rel in needed:
        assert (out/rel).is_file(),rel
    forbidden={'.db','.sqlite','.p12','.p7b','.key','.pem','.cer','.blend','.glb','.webm'}
    records=[]
    for f in sorted(out.rglob('*')):
        if not f.is_file() or f.name=='manifest.json':continue
        assert f.suffix.lower() not in forbidden and not f.name.startswith('.env'),f
        records.append({'path':f.relative_to(out).as_posix(),'bytes':f.stat().st_size,'sha256':sha(f)})
    (out/'manifest.json').write_text(json.dumps({'project':'派特岛','source_baseline':'cfe0c74','files':records},ensure_ascii=False,indent=2),'utf-8')
    archive=out.with_suffix('.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for f in sorted(out.rglob('*')):
            if f.is_file():z.write(f,Path(out.name)/f.relative_to(out))
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    print(json.dumps({'zip':str(archive),'bytes':archive.stat().st_size,'files':len(records)+1,'sha256':sha(archive)},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['prepare','finalize']);p.add_argument('--out',required=True);p.add_argument('--build');p.add_argument('--team');p.add_argument('--reference');p.add_argument('--ppt-master',help='Local PPT Master root; copy its MIT notice');p.add_argument('--project-python',default=str(ROOT/'venv/Scripts/python.exe'));a=p.parse_args()
    if a.phase=='prepare':prepare(a)
    else:finalize(a)
