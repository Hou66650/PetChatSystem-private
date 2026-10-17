"""Build editable SVG concept sheets for the Paw Heart Park visual proposal."""
from pathlib import Path
import math

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'art' / 'paw-heart-park-v1' / 'design'
OUT.mkdir(parents=True, exist_ok=True)

PALETTE = {
    'paper': '#f7f3e9', 'ink': '#3e5147', 'muted': '#718072', 'grass': '#829b63',
    'forest': '#536e50', 'stone': '#9b9b82', 'path': '#e6c477', 'cream': '#f4eee0',
    'wood': '#b18c60', 'teal': '#527f77', 'rose': '#c28270', 'water': '#78b9b7',
    'darkwood': '#6f5138', 'sky': '#dfe9e5', 'shadow': '#40584a33', 'white': '#fffdf7',
}
DEFS = '''
<defs>
  <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="8" stdDeviation="10" flood-color="#40584a" flood-opacity=".18"/></filter>
  <filter id="soft" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="10"/></filter>
  <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#dfe9e5"/><stop offset="1" stop-color="#f7f3e9"/></linearGradient>
  <linearGradient id="grass" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#a9ba83"/><stop offset="1" stop-color="#829b63"/></linearGradient>
  <linearGradient id="rock" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#b7b7a1"/><stop offset="1" stop-color="#6f7d6b"/></linearGradient>
  <linearGradient id="wood" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#8d6845"/><stop offset=".45" stop-color="#c29a6c"/><stop offset=".55" stop-color="#b18c60"/><stop offset="1" stop-color="#7c593d"/></linearGradient>
  <linearGradient id="water" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#b9e0dc"/><stop offset="1" stop-color="#78b9b7"/></linearGradient>
  <pattern id="woodgrain" width="42" height="18" patternUnits="userSpaceOnUse"><rect width="42" height="18" fill="#b18c60"/><path d="M0 4 C12 1 25 8 42 3 M0 13 C16 9 28 17 42 11" fill="none" stroke="#7c593d" stroke-opacity=".34" stroke-width="1.2"/></pattern>
  <pattern id="stonetexture" width="46" height="34" patternUnits="userSpaceOnUse"><rect width="46" height="34" fill="#9b9b82"/><circle cx="8" cy="9" r="1.2" fill="#68705e" opacity=".32"/><circle cx="29" cy="20" r="1.6" fill="#d0cbb6" opacity=".45"/><path d="M2 28L18 25M31 5l12 3" stroke="#68705e" stroke-opacity=".22"/></pattern>
  <pattern id="grasstexture" width="34" height="30" patternUnits="userSpaceOnUse"><rect width="34" height="30" fill="#829b63"/><path d="M6 24l2-7 2 7M23 12l2-6 2 6M28 28l1-5 2 5M13 9l1-4 2 4" stroke="#536e50" stroke-opacity=".35" stroke-width="1.1"/></pattern>
  <pattern id="pathgrain" width="52" height="32" patternUnits="userSpaceOnUse"><rect width="52" height="32" fill="#e6c477"/><path d="M0 16H52M26 0v32" stroke="#c49f5e" stroke-opacity=".35" stroke-width="1"/></pattern>
  <pattern id="rope" width="12" height="12" patternUnits="userSpaceOnUse" patternTransform="rotate(35)"><rect width="12" height="12" fill="#b69a72"/><path d="M0 0V12M6 0V12" stroke="#7b6447" stroke-width="2"/></pattern>
  <clipPath id="clip-card"><rect width="100" height="100" rx="12"/></clipPath>
  <clipPath id="clip-material"><rect width="100%" height="100%" rx="18"/></clipPath>
</defs>'''


def esc(value):
    return str(value).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def embed_assets(content):
    import base64
    import re
    def replace(match):
        href = match.group(1)
        if href.startswith('../../art/'):
            path = ROOT / 'art' / href.removeprefix('../../art/')
        elif href == 'five-islands-draft.png':
            path = OUT.parent / 'reference' / href
        else:
            return match.group(0)
        data = base64.b64encode(path.read_bytes()).decode('ascii')
        return f'href="data:image/png;base64,{data}"'
    return re.sub(r'href="([^"]+)"', replace, content)


def svg(name, width, height, body, background=None):
    background = background or f'<rect width="100%" height="100%" fill="{PALETTE["paper"]}"/>'
    content = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
{DEFS}
{body}
</svg>'''
    if background:
        content = content.replace('</defs>', '</defs>\n' + background)
    (OUT / name).write_text(embed_assets(content), encoding='utf-8')


def title(number, heading, subheading, x=60, y=40):
    return f'''<text x="{x}" y="{y}" font-family="sans-serif" font-size="20" letter-spacing="4" fill="{PALETTE['teal']}">{esc(number)}</text>
<text x="{x}" y="{y+48}" font-family="sans-serif" font-size="38" font-weight="700" fill="{PALETTE['ink']}">{esc(heading)}</text>
<text x="{x}" y="{y+82}" font-family="sans-serif" font-size="17" fill="{PALETTE['muted']}">{esc(subheading)}</text>'''


def panel(x, y, w, h, heading=''):
    text = f'<text x="{x+20}" y="{y+32}" font-family="sans-serif" font-size="16" font-weight="700" fill="{PALETTE["ink"]}">{esc(heading)}</text>' if heading else ''
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="18" fill="{PALETTE["white"]}" filter="url(#shadow)"/>{text}'


def paw(x, y, scale=1, fill=None, opacity=1):
    fill = fill or PALETTE['cream']
    return f'''<g transform="translate({x} {y}) scale({scale})" fill="{fill}" opacity="{opacity}">
<ellipse cx="0" cy="12" rx="18" ry="15"/><ellipse cx="-18" cy="-10" rx="7" ry="9"/><ellipse cx="-6" cy="-20" rx="7" ry="9"/><ellipse cx="7" cy="-20" rx="7" ry="9"/><ellipse cx="19" cy="-9" rx="7" ry="9"/></g>'''


def dog(x, y, scale=1, coat='#d49a68', facing=1):
    return f'''<g transform="translate({x} {y}) scale({facing*scale} {scale})" stroke="{PALETTE['darkwood']}" stroke-width="2" stroke-linejoin="round">
<ellipse cx="0" cy="0" rx="29" ry="17" fill="{coat}"/><circle cx="25" cy="-17" r="16" fill="{coat}"/>
<path d="M18-29l3-17 11 13M31-29l10-12 3 17" fill="{coat}"/>
<ellipse cx="36" cy="-14" rx="10" ry="7" fill="#f4eee0"/><circle cx="42" cy="-17" r="2.5" fill="#3e5147"/>
<path d="M-27-5q-18-13-15-25" fill="none" stroke="{coat}" stroke-width="9" stroke-linecap="round"/>
<path d="M-17 11v20M-2 12v20M13 10v21M25 7v22" stroke="{coat}" stroke-width="7" stroke-linecap="round"/>
<path d="M17 0q8 5 14 0" fill="#f4eee0" stroke="none"/></g>'''


def cat(x, y, scale=1, coat='#a9a9a0', facing=1):
    return f'''<g transform="translate({x} {y}) scale({facing*scale} {scale})" stroke="{PALETTE['ink']}" stroke-width="1.8" stroke-linejoin="round">
<ellipse cx="0" cy="0" rx="25" ry="14" fill="{coat}"/><circle cx="22" cy="-16" r="14" fill="{coat}"/>
<path d="M13-26l1-15 10 11M25-28l10-10 2 15" fill="{coat}"/>
<ellipse cx="31" cy="-13" rx="8" ry="6" fill="#f4eee0"/><circle cx="34" cy="-17" r="2" fill="#3e5147"/>
<path d="M-22-4q-20-18-8-35" fill="none" stroke="{coat}" stroke-width="7" stroke-linecap="round"/>
<path d="M-13 9v18M0 10v18M12 9v18M22 5v20" stroke="{coat}" stroke-width="5" stroke-linecap="round"/></g>'''


def tree(x, y, scale=1, autumn=False):
    colors = ['#789263', '#829b63', '#97ab73'] if not autumn else ['#c69a83', '#d6b0a0', '#a98678']
    return f'''<g transform="translate({x} {y}) scale({scale})" filter="url(#shadow)">
<path d="M-8 60L-4 5H5L10 60Z" fill="url(#woodgrain)"/>
<circle cx="-18" cy="2" r="25" fill="{colors[0]}"/><circle cx="13" cy="-8" r="28" fill="{colors[1]}"/><circle cx="0" cy="-29" r="26" fill="{colors[2]}"/></g>'''


def callout(x1, y1, x2, y2, text, align='start'):
    anchor = 'start' if align == 'start' else 'end'
    dx = 8 if align == 'start' else -8
    return f'''<path d="M{x1} {y1}L{x2} {y2}" stroke="{PALETTE['teal']}" stroke-width="1.5" stroke-dasharray="4 4"/>
<circle cx="{x1}" cy="{y1}" r="4" fill="{PALETTE['teal']}"/><text x="{x2+dx}" y="{y2-6}" text-anchor="{anchor}" font-family="sans-serif" font-size="15" fill="{PALETTE['ink']}">{esc(text)}</text>'''


def dimension(x1, y1, x2, y2, text):
    return f'''<path d="M{x1} {y1}L{x2} {y2}" stroke="{PALETTE['muted']}" stroke-width="1.2"/><path d="M{x1} {y1}l8-3M{x1} {y1}l8 3M{x2} {y2}l-8-3M{x2} {y2}l-8 3" stroke="{PALETTE['muted']}" stroke-width="1.2"/>
<text x="{(x1+x2)/2}" y="{(y1+y2)/2-8}" text-anchor="middle" font-family="sans-serif" font-size="13" fill="{PALETTE['muted']}">{esc(text)}</text>'''


def wood_rect(x, y, w, h, rx=5, stroke=None):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="url(#woodgrain)" stroke="{stroke or PALETTE["darkwood"]}" stroke-width="1.5"/>'


def stone_rect(x, y, w, h, rx=5):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="url(#stonetexture)" stroke="#68705e" stroke-width="1.2"/>'


def make_style_reference():
    cards = []
    islands = [
        ('樱花庭院', '../../art/sakura-grand-v1/courtyard.png', '原木桥、花瓣、暖色柔光'),
        ('雪境木屋', '../../art/snow-haven-v2/courtyard.png', '分块木材、麻绳、积雪边缘'),
        ('雾林温室', '../../art/mistwood-v1/mistwood-studio.png', '石灰岩、林地、雾气层次'),
        ('山岭营地', '../../art/shepherd-v1/alpine-studio.png', '石塔、松林、木构与山岩'),
    ]
    for i, (name, href, note) in enumerate(islands):
        x = 60 + i * 450
        cards.append(f'''<g>{panel(x,150,420,260)}
<image href="{href}" x="{x+12}" y="{x*0+162}" width="396" height="180" preserveAspectRatio="xMidYMid slice"/>
<text x="{x+20}" y="376" font-family="sans-serif" font-size="19" font-weight="700" fill="{PALETTE['ink']}">{name}</text>
<text x="{x+20}" y="400" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">{note}</text></g>''')
    materials = [
        ('真实木材', '../../art/snow-haven-v2/lodge-detail.png', '保留板缝、端面与圆角，不做塑料同色块'),
        ('麻绳连接', '../../art/snow-haven-v2/courtyard.png', '只用于真实受力和收束位置'),
        ('石材', '../../art/mistwood-v1/limestone-albedo.png', '灰绿石灰岩、粗糙度差异和边缘磨损'),
        ('草地', '../../art/mistwood-v1/forest-floor-albedo.png', '草叶、落叶与地表色差，不做纯色地毯'),
        ('柔光', '../../art/shepherd-v1/alpine-studio.png', '暖主光＋冷色环境光，低对比、无强镜面'),
    ]
    for i, (name, href, note) in enumerate(materials):
        x = 60 + i * 360
        cards.append(f'''<g>{panel(x,450,330,260)}
<image href="{href}" x="{x+12}" y="462" width="306" height="142" preserveAspectRatio="xMidYMid slice"/>
<text x="{x+18}" y="636" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['ink']}">{name}</text>
<text x="{x+18}" y="662" font-family="sans-serif" font-size="13" fill="{PALETTE['muted']}">{note}</text></g>''')
    colors = [('奶油黄', '#e6c477'), ('鼠尾草绿', '#829b63'), ('森林绿', '#536e50'), ('石灰岩', '#9b9b82'), ('暖木色', '#b18c60'), ('灰青', '#527f77'), ('雾玫瑰', '#c28270'), ('溪水青', '#78b9b7')]
    swatches = []
    for i, (name, color) in enumerate(colors):
        x = 95 + i * 205
        swatches.append(f'<circle cx="{x}" cy="805" r="26" fill="{color}"/><text x="{x}" y="850" text-anchor="middle" font-family="sans-serif" font-size="13" fill="{PALETTE["muted"]}">{name}</text><text x="{x}" y="870" text-anchor="middle" font-family="monospace" font-size="11" fill="{PALETTE["muted"]}">{color}</text>')
    rules = [
        ('01 结构先行', '厚度、支撑、排水和连接都能成立，再添加装饰。'),
        ('02 自然材质', '木纹、绳纹、石纹和草地只出现在正确材料上。'),
        ('03 可爱限量', '爪印、花瓣和圆角作为点缀，不把设施做成动物脸。'),
        ('04 宠物尺度', '中央留白，路线清楚，入口、出口和休息区始终可见。'),
    ]
    for i, (heading, note) in enumerate(rules):
        x = 60 + i * 450
        cards.append(f'''{panel(x,910,420,150)}<text x="{x+20}" y="950" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">{heading}</text><text x="{x+20}" y="980" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">{note}</text>
<text x="{x+20}" y="1004" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">以四座生活岛的实际画面为统一基准。</text>''')
    body = title('01 / STYLE', '统一风格参考板', '真实自然材质＋圆润可爱细节；四座生活岛模型、主题和入口全部保留') + ''.join(cards) + ''.join(swatches)
    svg('01-style-reference.svg', 1920, 1120, body)


def make_five_island_plan():
    parts = [title('02 / MASTER PLAN', '五岛爪印俯视总图', '沿用现有坐标和四岛模型；中央掌垫只调整内部功能，不改变五岛入口')]
    map_points = [(-15, 0, '樱花庭院', 'sakura'), (-6, -10, '雪境木屋', 'snow'), (6, -10, '雾林温室', 'room'), (15, 0, '山岭营地', 'camp')]
    colors = {'sakura': '#d6b0a0', 'snow': '#b9d0d2', 'room': '#9fb88c', 'camp': '#91a687'}
    for x, z, name, key in map_points:
        px, py = 600 + x * 30, 560 + z * 30
        parts.append(f'''<g>{panel(px-125,py-95,250,190)}
<ellipse cx="{px}" cy="{py}" rx="116" ry="82" fill="{colors[key]}" stroke="{PALETTE['forest']}" stroke-opacity=".25" stroke-width="3"/>
<text x="{px}" y="{py-5}" text-anchor="middle" font-family="sans-serif" font-size="20" font-weight="700" fill="{PALETTE['ink']}">{name}</text>
<text x="{px}" y="{py+22}" text-anchor="middle" font-family="sans-serif" font-size="13" fill="{PALETTE['muted']}">现有模型与入口保留</text>
<text x="{px}" y="{py+48}" text-anchor="middle" font-family="monospace" font-size="13" fill="{PALETTE['muted']}">({x}, {z})</text></g>''')
    parts.append(f'''{panel(360,620,480,340)}
<path d="M600 660C520 620 430 680 450 770C465 850 525 900 600 900C675 900 735 850 750 770C770 680 680 620 600 660Z" fill="url(#grasstexture)" stroke="{PALETTE['forest']}" stroke-width="3"/>
<path d="M600 700C545 670 490 710 500 765C510 820 555 850 600 850C645 850 690 820 700 765C710 710 655 670 600 700Z" fill="#a9ba83" opacity=".65"/>
<text x="600" y="760" text-anchor="middle" font-family="sans-serif" font-size="25" font-weight="700" fill="{PALETTE['ink']}">爪心乐园</text>
<text x="600" y="790" text-anchor="middle" font-family="sans-serif" font-size="15" fill="{PALETTE['muted']}">中央掌垫 · 重新分区</text>
<path d="M600 900V940" stroke="{PALETTE['teal']}" stroke-width="4" stroke-linecap="round"/><text x="600" y="968" text-anchor="middle" font-family="sans-serif" font-size="14" fill="{PALETTE['teal']}">主入口朝向南侧</text>''')
    parts.append(dimension(150, 545, 1050, 545, '外侧两岛中心距 30 m（原布局）'))
    parts.append(dimension(420, 560, 780, 560, '内侧两岛中心距 12 m（原布局）'))
    parts.append(dimension(600, 545, 600, 610, '掌垫中心纵向间距 11 m'))
    parts.append(f'''{panel(1120,120,740,420)}
<text x="1150" y="165" font-family="sans-serif" font-size="20" font-weight="700" fill="{PALETTE['ink']}">比例与间距核对</text>
<text x="1150" y="205" font-family="sans-serif" font-size="15" fill="{PALETTE['muted']}">• 四个趾垫保持原中心坐标和入口，不重排生活岛。</text>
<text x="1150" y="240" font-family="sans-serif" font-size="15" fill="{PALETTE['muted']}">• 中央掌垫约 18 m 展示宽度，四趾垫约 9 m。</text>
<text x="1150" y="275" font-family="sans-serif" font-size="15" fill="{PALETTE['muted']}">• 趾垫之间保留云海负空间，不增加桥或额外岛屿。</text>
<text x="1150" y="310" font-family="sans-serif" font-size="15" fill="{PALETTE['muted']}">• 中央内部只调整步道、设施和植被，不扩大占地。</text>
<image href="five-islands-draft.png" x="1150" y="340" width="680" height="170" preserveAspectRatio="xMidYMid slice"/>
<text x="1150" y="530" font-family="sans-serif" font-size="12" fill="{PALETTE['muted']}">首版布局截图，仅作坐标复核，不作为本次完成图。</text>''')
    parts.append(f'''{panel(1120,580,740,380)}
<text x="1150" y="625" font-family="sans-serif" font-size="20" font-weight="700" fill="{PALETTE['ink']}">中央分区草案</text>
<text x="1150" y="665" font-family="sans-serif" font-size="15" fill="{PALETTE['teal']}">A 入口缓冲区</text><text x="1350" y="665" font-family="sans-serif" font-size="15" fill="{PALETTE['muted']}">看清全场后再分流</text>
<text x="1150" y="700" font-family="sans-serif" font-size="15" fill="{PALETTE['teal']}">B 互动草坪</text><text x="1350" y="700" font-family="sans-serif" font-size="15" fill="{PALETTE['muted']}">追逐、彩球、跳跃，中央留白</text>
<text x="1150" y="735" font-family="sans-serif" font-size="15" fill="{PALETTE['teal']}">C 设施环</text><text x="1350" y="735" font-family="sans-serif" font-size="15" fill="{PALETTE['muted']}">隧道、跳圈、平衡木和猫爬架</text>
<text x="1150" y="770" font-family="sans-serif" font-size="15" fill="{PALETTE['teal']}">D 安静休息区</text><text x="1350" y="770" font-family="sans-serif" font-size="15" fill="{PALETTE['muted']}">遮阴、饮水、低矮座椅，远离跑线</text>
<text x="1150" y="805" font-family="sans-serif" font-size="15" fill="{PALETTE['teal']}">E 后勤边界</text><text x="1350" y="805" font-family="sans-serif" font-size="15" fill="{PALETTE['muted']}">玩具收纳、排水与溢水，不占通道</text>
<text x="1150" y="850" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">所有尺寸为视觉比例草案；第 4 批再输出工程尺寸。</text>''')
    body = ''.join(parts)
    svg('02-five-island-plan.svg', 1920, 1120, body)


def make_park_birdseye():
    p = [title('03 / AERIAL', '中央乐园鸟瞰效果图', '真实材质分区、清晰动线和设施尺度；概念方案，非线上模型')]
    p.append(f'''<rect x="0" y="130" width="1920" height="990" fill="url(#sky)"/>
<ellipse cx="960" cy="1000" rx="740" ry="100" fill="#718072" opacity=".12" filter="url(#soft)"/>
<path d="M960 230C740 170 430 290 360 520C300 720 510 900 770 970C1030 1040 1420 980 1540 800C1660 620 1480 360 1220 270C1130 240 1040 220 960 230Z" fill="url(#rock)" stroke="#68705e" stroke-width="3"/>
<path d="M960 205C740 145 450 270 390 500C340 680 540 840 790 900C1040 960 1390 900 1500 740C1610 570 1450 340 1210 255C1120 225 1040 195 960 205Z" fill="url(#grasstexture)" stroke="#536e50" stroke-width="4"/>
<path d="M470 570C650 390 1050 320 1330 470C1450 530 1450 640 1330 700C1080 830 660 830 490 670C440 625 440 600 470 570Z" fill="none" stroke="url(#pathgrain)" stroke-width="62" stroke-linecap="round"/>
<path d="M530 590C710 450 1040 400 1260 500" fill="none" stroke="#a9ba83" stroke-width="160" stroke-linecap="round" opacity=".82"/>
<path d="M740 890C760 940 770 980 770 1010" stroke="url(#pathgrain)" stroke-width="72" stroke-linecap="round"/>
<text x="850" y="640" font-family="sans-serif" font-size="26" font-weight="700" fill="{PALETTE['ink']}" opacity=".7">互动草坪 · 中央留白</text>''')
    for x, y, s in [(450,380,.9),(620,290,.8),(1040,260,.85),(1360,420,.9),(1420,700,.85),(1180,850,.8),(520,760,.8)]:
        p.append(tree(x, y, s))
    p.append(f'''<g>{wood_rect(560,390,155,38,10)}{wood_rect(585,428,32,74,8)}{wood_rect(625,428,32,74,8)}
<path d="M555 390Q635 340 715 390" fill="none" stroke="url(#rope)" stroke-width="9"/>
<path d="M560 440Q635 520 710 440" fill="none" stroke="{PALETTE['teal']}" stroke-width="8" opacity=".55"/>
<text x="635" y="360" text-anchor="middle" font-family="sans-serif" font-size="16" fill="{PALETTE['ink']}">钻行隧道 · 可见出口</text></g>
<g>{wood_rect(840,330,22,105,6)}{wood_rect(960,330,22,105,6)}{wood_rect(810,342,200,20,9)}
<path d="M830 330Q900 260 970 330" fill="none" stroke="{PALETTE['rose']}" stroke-width="12"/>
<text x="910" y="295" text-anchor="middle" font-family="sans-serif" font-size="16" fill="{PALETTE['ink']}">低矮跳圈与跨杆</text></g>
<g>{wood_rect(1120,500,230,34,8)}{wood_rect(1140,535,24,70,6)}{wood_rect(1300,535,24,70,6)}
<path d="M1120 500L1350 500L1350 532L1120 534Z" fill="url(#woodgrain)" stroke="{PALETTE['darkwood']}" stroke-width="2"/>
<path d="M1160 512h45M1240 512h45" stroke="{PALETTE['cream']}" stroke-width="5" stroke-linecap="round"/>
<text x="1240" y="480" text-anchor="middle" font-family="sans-serif" font-size="16" fill="{PALETTE['ink']}">平衡木与小坡桥</text></g>
<g>{wood_rect(1320,300,28,180,8)}{wood_rect(1400,300,28,180,8)}{wood_rect(1280,330,190,26,12)}
<path d="M1320 330Q1365 280 1410 330L1410 370L1320 370Z" fill="{PALETTE['teal']}" opacity=".72"/>
<path d="M1320 420h108M1300 460h148" stroke="{PALETTE['wood']}" stroke-width="16" stroke-linecap="round"/>
<text x="1370" y="265" text-anchor="middle" font-family="sans-serif" font-size="16" fill="{PALETTE['ink']}">猫咪攀爬与躲藏区</text></g>
<g>{wood_rect(460,700,150,40,8)}{wood_rect(475,740,25,55,6)}{wood_rect(570,740,25,55,6)}
<path d="M460 700Q535 640 610 700" fill="none" stroke="{PALETTE['rose']}" stroke-width="12"/>
<circle cx="500" cy="680" r="13" fill="{PALETTE['path']}"/><circle cx="540" cy="680" r="13" fill="{PALETTE['rose']}"/><circle cx="580" cy="680" r="13" fill="{PALETTE['teal']}"/>
<text x="535" y="660" text-anchor="middle" font-family="sans-serif" font-size="16" fill="{PALETTE['ink']}">彩球收纳</text></g>
<g>{wood_rect(1180,730,180,26,8)}{wood_rect(1200,756,24,52,6)}{wood_rect(1320,756,24,52,6)}
<path d="M1160 730Q1270 620 1380 730L1360 760Q1270 690 1180 760Z" fill="{PALETTE['cream']}" stroke="{PALETTE['rose']}" stroke-width="3"/>
<ellipse cx="1240" cy="795" rx="28" ry="10" fill="url(#water)"/><ellipse cx="1310" cy="795" rx="28" ry="10" fill="url(#water)"/>
<text x="1270" y="840" text-anchor="middle" font-family="sans-serif" font-size="16" fill="{PALETTE['ink']}">遮阴休息与饮水区</text></g>
<g>{wood_rect(690,875,26,150,8)}{wood_rect(850,875,26,150,8)}{wood_rect(660,875,246,28,10)}
<path d="M690 875Q770 830 850 875" fill="none" stroke="url(#rope)" stroke-width="8"/>
<text x="770" y="850" text-anchor="middle" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['ink']}">入口 · 先看全场再分流</text></g>''')
    p.append(dog(900, 700, .75, '#d49a68') + cat(1030, 740, .7, '#a9a9a0', -1) + dog(630, 560, .6, '#6f756f', -1) + cat(1240, 620, .55, '#b4a091', -1))
    p.append(callout(770, 1010, 500, 1040, '主入口与视线轴', 'start'))
    p.append(callout(1020, 620, 1040, 1030, '宽阔追球区，不放大型障碍', 'start'))
    p.append(callout(1370, 730, 1600, 850, '安静区避开奔跑路线', 'end'))
    svg('03-park-birdseye.svg', 1920, 1120, ''.join(p))


def make_pet_perspective():
    p = [title('04 / PET EYE VIEW', '宠物视角：进入乐园', '入口、中央草坪与休息区同时可见；用空间亲切感而非夸张造型吸引宠物')]
    p.append(f'''<rect x="0" y="130" width="1920" height="990" fill="url(#sky)"/>
<path d="M0 950Q960 650 1920 950V1120H0Z" fill="url(#grasstexture)"/>
<path d="M770 1120L900 480H1020L1150 1120Z" fill="url(#pathgrain)"/>
<path d="M850 1120L930 500H990L1070 1120Z" fill="#f2d996" opacity=".65"/>
<path d="M280 850Q960 550 1640 850" fill="none" stroke="#a9ba83" stroke-width="110" opacity=".6"/>
<g>{wood_rect(350,380,54,480,14)}{wood_rect(1516,380,54,480,14)}{wood_rect(310,350,300,54,16)}{wood_rect(1310,350,300,54,16)}
<path d="M350 380Q960 220 1570 380" fill="none" stroke="url(#rope)" stroke-width="14"/>
<path d="M420 430Q960 330 1500 430" fill="none" stroke="{PALETTE['cream']}" stroke-width="5" opacity=".55"/>
<text x="960" y="350" text-anchor="middle" font-family="sans-serif" font-size="25" font-weight="700" fill="{PALETTE['ink']}">欢迎来到爪心乐园</text></g>
<g>{wood_rect(480,510,150,28,8)}{wood_rect(500,538,26,85,8)}{wood_rect(590,538,26,85,8)}
<path d="M480 510Q555 450 630 510" fill="none" stroke="{PALETTE['teal']}" stroke-width="10"/>
<text x="555" y="490" text-anchor="middle" font-family="sans-serif" font-size="16" fill="{PALETTE['ink']}">钻行隧道</text></g>
<g>{wood_rect(820,400,18,110,6)}{wood_rect(940,400,18,110,6)}{wood_rect(800,420,180,18,8)}
<path d="M820 400Q890 330 960 400" fill="none" stroke="{PALETTE['rose']}" stroke-width="11"/>
<text x="890" y="370" text-anchor="middle" font-family="sans-serif" font-size="16" fill="{PALETTE['ink']}">低跳圈</text></g>
<g>{wood_rect(1200,500,190,26,8)}{wood_rect(1210,526,22,75,6)}{wood_rect(1360,526,22,75,6)}
<path d="M1200 500L1390 500L1390 526L1200 526Z" fill="url(#woodgrain)"/>
<text x="1295" y="480" text-anchor="middle" font-family="sans-serif" font-size="16" fill="{PALETTE['ink']}">小坡桥</text></g>
<g>{wood_rect(1370,650,180,24,8)}{wood_rect(1385,674,22,55,6)}{wood_rect(1520,674,22,55,6)}
<path d="M1350 650Q1460 540 1570 650L1550 680Q1460 610 1370 680Z" fill="{PALETTE['cream']}" stroke="{PALETTE['rose']}" stroke-width="3"/>
<ellipse cx="1430" cy="710" rx="26" ry="9" fill="url(#water)"/><ellipse cx="1490" cy="710" rx="26" ry="9" fill="url(#water)"/>
<text x="1460" y="750" text-anchor="middle" font-family="sans-serif" font-size="16" fill="{PALETTE['ink']}">安静休息区</text></g>''')
    for x, y, s in [(240,470,.9),(680,350,.7),(1130,330,.75),(1660,470,.9)]:
        p.append(tree(x, y, s))
    p.append(dog(650, 820, 1.05, '#d49a68') + cat(1220, 850, .95, '#a9a9a0', -1))
    p.append(f'''{panel(1160,850,650,130)}<text x="1190" y="890" font-family="sans-serif" font-size="17" font-weight="700" fill="{PALETTE['teal']}">进入后的第一眼</text>
<text x="1190" y="922" font-family="sans-serif" font-size="15" fill="{PALETTE['muted']}">通道向中央打开；能看到同伴、设施出口和安静休息区。</text>
<text x="1190" y="950" font-family="sans-serif" font-size="15" fill="{PALETTE['muted']}">大型装饰不挡入口，也不遮挡宠物的退后空间。</text>''')
    svg('04-pet-perspective.svg', 1920, 1120, ''.join(p))


make_style_reference()
make_five_island_plan()
make_park_birdseye()
make_pet_perspective()


def facility_sheet(filename, number, heading, subheading, main, views, material, structure, interaction, notes):
    body = title(number, heading, subheading)
    body += panel(60, 150, 960, 630) + main
    body += panel(1040, 150, 820, 300) + views
    body += panel(1040, 480, 400, 300) + material
    body += panel(1460, 480, 400, 300) + structure
    body += panel(60, 810, 960, 260) + interaction
    body += panel(1040, 810, 820, 260) + notes
    svg(filename, 1920, 1120, body)


def make_entry_closeup():
    main = f'''<text x="90" y="190" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">入口近景 / 木构、麻绳与落脚缓冲</text>
<path d="M180 710Q550 510 930 700V760H180Z" fill="url(#grasstexture)"/>
<path d="M510 760L610 470H690L790 760Z" fill="url(#pathgrain)"/>
{wood_rect(350,280,62,410,14)}{wood_rect(790,280,62,410,14)}{wood_rect(310,250,580,58,16)}
<path d="M350 280Q600 160 850 280" fill="none" stroke="url(#rope)" stroke-width="13"/>
<path d="M390 330Q600 240 810 330" fill="none" stroke="{PALETTE['cream']}" stroke-width="5" opacity=".5"/>
{stone_rect(330,680,100,42,10)}{stone_rect(770,680,100,42,10)}
<path d="M375 300q25 22 0 45q25 22 0 45M815 300q25 22 0 45q25 22 0 45" fill="none" stroke="url(#rope)" stroke-width="7"/>
{paw(600,530,.8,PALETTE['cream'])}{paw(600,650,.65,PALETTE['cream'])}
{dog(520,680,.9,'#d49a68')}
<text x="600" y="245" text-anchor="middle" font-family="sans-serif" font-size="20" font-weight="700" fill="{PALETTE['ink']}">圆润门楣，不做动物脸</text>'''
    views = f'''<text x="1070" y="190" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">三视图 / 比例草案</text>
<g>{wood_rect(1090,250,24,130,7)}{wood_rect(1200,250,24,130,7)}{wood_rect(1070,240,175,22,8)}<text x="1160" y="410" text-anchor="middle" font-family="sans-serif" font-size="13" fill="{PALETTE['muted']}">正视：开口完全可见</text></g>
<g>{wood_rect(1320,250,24,130,7)}{wood_rect(1300,240,70,22,8)}<path d="M1320 265l45-25" stroke="url(#rope)" stroke-width="6"/><text x="1345" y="410" text-anchor="middle" font-family="sans-serif" font-size="13" fill="{PALETTE['muted']}">侧视：梁厚与出挑</text></g>
<g><ellipse cx="1570" cy="300" rx="85" ry="48" fill="url(#pathgrain)"/><ellipse cx="1570" cy="300" rx="45" ry="22" fill="#a9ba83"/>{paw(1570,300,.55,PALETTE['forest'])}<text x="1570" y="410" text-anchor="middle" font-family="sans-serif" font-size="13" fill="{PALETTE['muted']}">顶视：直行不穿流</text></g>'''
    material = f'''<text x="1065" y="520" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">材质细节</text>
{wood_rect(1080,555,120,85,10)}<path d="M1230 560q35 20 0 40q35 20 0 40q35 20 0 40" fill="none" stroke="url(#rope)" stroke-width="9"/>
{stone_rect(1080,670,120,55,10)}
<text x="1220" y="700" font-family="sans-serif" font-size="13" fill="{PALETTE['muted']}">板缝、绳纹、石灰岩独立呈现</text>'''
    structure = f'''<text x="1485" y="520" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">结构连接图</text>
{wood_rect(1530,555,180,28,8)}{wood_rect(1590,585,28,100,8)}
<path d="M1580 570q35 20 0 40q35 20 0 40" fill="none" stroke="url(#rope)" stroke-width="8"/>
<path d="M1530 640h-45M1620 690h55" stroke="{PALETTE['teal']}" stroke-width="2"/>
<text x="1475" y="655" font-family="sans-serif" font-size="12" fill="{PALETTE['muted']}">绳结只作收束</text>
<text x="1640" y="705" font-family="sans-serif" font-size="12" fill="{PALETTE['muted']}">柱脚落到石基</text>'''
    interaction = f'''<text x="90" y="850" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">宠物互动示意</text>
<path d="M250 1030L500 900H700L900 1030Z" fill="url(#pathgrain)"/>
{dog(540,960,.85,'#d49a68')}<path d="M590 950h170" stroke="{PALETTE['teal']}" stroke-width="4" stroke-dasharray="10 7"/><path d="M760 950l-18-10v20z" fill="{PALETTE['teal']}"/>
<text x="720" y="900" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">先看全场，再进入；无需绕过装饰</text>'''
    notes = f'''<text x="1070" y="850" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">设计约束</text>
<text x="1070" y="885" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">• 木柱落在独立石基上，横梁可见厚度。</text>
<text x="1070" y="915" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">• 麻绳只连接横梁和柱顶，不形成障碍。</text>
<text x="1070" y="945" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">• 爪印仅在铺装，入口净宽与退后空间不变。</text>
<text x="1070" y="975" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">• 入口同时看到草坪、休息区和隧道出口。</text>'''
    facility_sheet('05-entry-closeup.svg', '05 / CLOSE-UP', '入口近景：先看见，再进入', '真实木构与麻绳连接，圆润但不做整栋动物造型', main, views, material, structure, interaction, notes)


def make_play_lawn_closeup():
    main = f'''<text x="90" y="190" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">互动草坪近景 / 追逐、收纳与排水</text>
<path d="M130 650Q500 330 950 610V760H130Z" fill="url(#grasstexture)"/>
<path d="M200 690Q550 480 880 660" fill="none" stroke="#a9ba83" stroke-width="140" opacity=".75"/>
<ellipse cx="560" cy="650" rx="410" ry="150" fill="none" stroke="url(#stonetexture)" stroke-width="24"/>
<path d="M300 745h55M460 770h55M690 770h55M820 735h55" stroke="{PALETTE['ink']}" stroke-width="8"/>
{wood_rect(720,480,190,95,10)}{wood_rect(720,470,190,18,8)}
<circle cx="750" cy="500" r="20" fill="{PALETTE['path']}"/><circle cx="795" cy="500" r="20" fill="{PALETTE['rose']}"/><circle cx="840" cy="500" r="20" fill="{PALETTE['teal']}"/>
{dog(480,650,1.0,'#d49a68')}{cat(700,690,.8,'#a9a9a0',-1)}
<path d="M530 630Q610 580 700 610" fill="none" stroke="{PALETTE['teal']}" stroke-width="5" stroke-dasharray="12 8"/><circle cx="700" cy="610" r="18" fill="{PALETTE['rose']}"/>
<text x="300" y="430" font-family="sans-serif" font-size="16" fill="{PALETTE['muted']}">低矮边界不形成围墙，中央保留完整追逐弧</text>'''
    views = f'''<text x="1070" y="190" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">三视图 / 草坪与后勤边界</text>
<ellipse cx="1160" cy="300" rx="95" ry="62" fill="url(#grasstexture)"/><ellipse cx="1160" cy="300" rx="105" ry="72" fill="none" stroke="url(#stonetexture)" stroke-width="12"/>
<path d="M1100 300h120" stroke="{PALETTE['teal']}" stroke-width="4" stroke-dasharray="8 6"/><text x="1160" y="410" text-anchor="middle" font-family="sans-serif" font-size="13" fill="{PALETTE['muted']}">顶视：完整追逐区</text>
{wood_rect(1330,250,150,45,8)}{wood_rect(1330,240,150,14,6)}<circle cx="1360" cy="275" r="12" fill="{PALETTE['path']}"/><circle cx="1395" cy="275" r="12" fill="{PALETTE['rose']}"/><text x="1405" y="410" text-anchor="middle" font-family="sans-serif" font-size="13" fill="{PALETTE['muted']}">侧视：收纳靠近边界</text>
<path d="M1550 240v120M1550 360h90v-120" fill="url(#stonetexture)"/><path d="M1570 330h50" stroke="{PALETTE['ink']}" stroke-width="8"/><text x="1570" y="410" text-anchor="middle" font-family="sans-serif" font-size="13" fill="{PALETTE['muted']}">剖面：排水槽</text>'''
    material = f'''<text x="1065" y="520" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">材质细节</text>
{stone_rect(1080,550,140,60,10)}{wood_rect(1080,640,140,55,10)}
<circle cx="1260" cy="570" r="20" fill="{PALETTE['path']}"/><circle cx="1300" cy="570" r="20" fill="{PALETTE['rose']}"/><circle cx="1340" cy="570" r="20" fill="{PALETTE['teal']}"/>
<text x="1080" y="735" font-family="sans-serif" font-size="13" fill="{PALETTE['muted']}">粗糙石边、木篮、哑光橡胶彩球</text>'''
    structure = f'''<text x="1485" y="520" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">排水与收纳剖面</text>
<path d="M1490 590h300v70h-300Z" fill="url(#grasstexture)"/><path d="M1490 660h300v55h-300Z" fill="url(#stonetexture)"/>
<path d="M1560 660h100v55h-100Z" fill="{PALETTE['water']}" opacity=".65"/>
<path d="M1490 625h300" stroke="{PALETTE['teal']}" stroke-width="3" stroke-dasharray="6 5"/>
<text x="1490" y="745" font-family="sans-serif" font-size="12" fill="{PALETTE['muted']}">草皮 → 碎石排水层 → 外侧集水槽</text>'''
    interaction = f'''<text x="90" y="850" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">宠物互动示意</text>
<path d="M200 960Q450 850 760 940" fill="none" stroke="{PALETTE['teal']}" stroke-width="5" stroke-dasharray="14 8"/>
{dog(430,960,.8,'#d49a68')}<circle cx="760" cy="940" r="18" fill="{PALETTE['rose']}"/>
{cat(700,1000,.65,'#a9a9a0',-1)}
<text x="720" y="895" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">球从收纳区取出；追逐弧不穿过后勤与休息区</text>'''
    notes = f'''<text x="1070" y="850" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">设计约束</text>
<text x="1070" y="885" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">• 低矮石边标识范围，不阻碍跨出和紧急退出。</text>
<text x="1070" y="915" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">• 排水槽放在外侧低处，不在奔跑落点上。</text>
<text x="1070" y="945" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">• 彩球有固定收纳，不滚入饮水区。</text>
<text x="1070" y="975" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">• 爪印只做方向提示，不缩小中央草坪。</text>'''
    facility_sheet('06-play-lawn-closeup.svg', '06 / CLOSE-UP', '互动草坪：有边界，也有自由', '追逐空间、排水与收纳同时成立，可爱装饰不占跑道', main, views, material, structure, interaction, notes)


def make_quiet_retreat_closeup():
    main = f'''<text x="90" y="190" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">安静休息区近景 / 遮阴、饮水与溢水处理</text>
<path d="M170 720Q520 510 900 700V760H170Z" fill="url(#grasstexture)"/>
{wood_rect(340,460,250,30,10)}{wood_rect(360,490,28,150,8)}{wood_rect(540,490,28,150,8)}
<path d="M300 460Q465 260 630 460L600 500Q465 390 330 500Z" fill="{PALETTE['cream']}" stroke="{PALETTE['rose']}" stroke-width="4"/>
<path d="M350 460Q465 330 580 460" fill="none" stroke="{PALETTE['rose']}" stroke-width="4" opacity=".6"/>
{wood_rect(700,500,180,30,9)}{wood_rect(720,530,24,100,8)}{wood_rect(840,530,24,100,8)}
<ellipse cx="745" cy="580" rx="34" ry="12" fill="url(#water)"/><ellipse cx="815" cy="580" rx="34" ry="12" fill="url(#water)"/>
<path d="M710 600h170l-20 35H730Z" fill="{PALETTE['water']}" opacity=".45"/>
{cat(520,650,.9,'#a9a9a0')}{dog(770,700,.75,'#6f756f',-1)}
<text x="460" y="610" text-anchor="middle" font-family="sans-serif" font-size="15" fill="{PALETTE['muted']}">花苞顶棚下保持安静视野，不设奔跑穿越线</text>'''
    views = f'''<text x="1070" y="190" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">三视图 / 花苞顶棚与碗架</text>
<path d="M1100 340Q1170 230 1240 340L1215 360Q1170 310 1125 360Z" fill="{PALETTE['cream']}" stroke="{PALETTE['rose']}" stroke-width="3"/>
<text x="1170" y="410" text-anchor="middle" font-family="sans-serif" font-size="13" fill="{PALETTE['muted']}">正视：遮阴覆盖座席</text>
{wood_rect(1320,250,170,26,8)}{wood_rect(1340,276,22,90,6)}{wood_rect(1450,276,22,90,6)}<ellipse cx="1390" cy="330" rx="32" ry="11" fill="url(#water)"/>
<text x="1390" y="410" text-anchor="middle" font-family="sans-serif" font-size="13" fill="{PALETTE['muted']}">侧视：碗架抬高</text>
<ellipse cx="1570" cy="300" rx="90" ry="55" fill="url(#pathgrain)"/><ellipse cx="1570" cy="300" rx="30" ry="12" fill="url(#water)"/><path d="M1530 340h80l-15 25h-50Z" fill="{PALETTE['water']}" opacity=".45"/>
<text x="1570" y="410" text-anchor="middle" font-family="sans-serif" font-size="13" fill="{PALETTE['muted']}">顶视：溢水托盘</text>'''
    material = f'''<text x="1065" y="520" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">材质细节</text>
<path d="M1080 610Q1150 520 1220 610L1200 640Q1150 580 1100 640Z" fill="{PALETTE['cream']}" stroke="{PALETTE['rose']}" stroke-width="3"/>
<ellipse cx="1120" cy="690" rx="40" ry="14" fill="url(#water)"/>
<text x="1190" y="700" font-family="sans-serif" font-size="13" fill="{PALETTE['muted']}">哑光顶棚、可清洗碗架、浅水色</text>'''
    structure = f'''<text x="1485" y="520" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">溢水与支撑连接</text>
{wood_rect(1530,560,200,26,8)}{wood_rect(1550,586,24,90,8)}{wood_rect(1710,586,24,90,8)}
<path d="M1510 620h220l-25 45h-170Z" fill="{PALETTE['water']}" opacity=".45"/>
<path d="M1550 665h-45M1730 665h45" stroke="{PALETTE['teal']}" stroke-width="2"/>
<text x="1490" y="690" font-family="sans-serif" font-size="12" fill="{PALETTE['muted']}">碗架固定于托盘，溢水向外侧导流</text>'''
    interaction = f'''<text x="90" y="850" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">宠物互动示意</text>
<path d="M240 950Q470 850 760 930" fill="none" stroke="url(#pathgrain)" stroke-width="60"/>
{cat(520,970,.8,'#a9a9a0')}{dog(720,970,.7,'#6f756f',-1)}
<ellipse cx="590" cy="960" rx="26" ry="9" fill="url(#water)"/>
<text x="700" y="900" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">可饮水、可独处，也可并肩休息；不必穿越草坪</text>'''
    notes = f'''<text x="1070" y="850" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">设计约束</text>
<text x="1070" y="885" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">• 花苞顶棚提供真实遮阴，不遮挡邻近视线。</text>
<text x="1070" y="915" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">• 水碗有抬高支架、托盘与外侧溢水路径。</text>
<text x="1070" y="945" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">• 座椅和碗架离开追逐弧与设施出口。</text>
<text x="1070" y="975" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">• 安静区可从入口直接看到，方便退出。</text>'''
    facility_sheet('07-quiet-retreat-closeup.svg', '07 / CLOSE-UP', '安静休息区：遮阴与可撤退的安静', '花苞顶棚、饮水与溢水都围绕宠物习惯布置', main, views, material, structure, interaction, notes)


def make_ball_facility():
    main = f'''<text x="90" y="190" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">设施 01 / 玩球草坪</text>
<path d="M150 650Q520 360 960 630V760H150Z" fill="url(#grasstexture)"/>
<ellipse cx="570" cy="630" rx="380" ry="150" fill="none" stroke="url(#stonetexture)" stroke-width="22"/>
<path d="M260 730h60M460 770h60M690 770h60M820 730h60" stroke="{PALETTE['ink']}" stroke-width="8"/>
{wood_rect(730,470,190,90,10)}{wood_rect(730,460,190,18,8)}
<circle cx="760" cy="495" r="20" fill="{PALETTE['path']}"/><circle cx="805" cy="495" r="20" fill="{PALETTE['rose']}"/><circle cx="850" cy="495" r="20" fill="{PALETTE['teal']}"/>
{dog(490,650,.9,'#d49a68')}<circle cx="640" cy="610" r="19" fill="{PALETTE['rose']}"/>
<path d="M520 630Q580 590 630 610" fill="none" stroke="{PALETTE['teal']}" stroke-width="4" stroke-dasharray="10 7"/>'''
    views = f'''<text x="1070" y="190" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">三视图</text>
<ellipse cx="1160" cy="300" rx="100" ry="65" fill="url(#grasstexture)"/><ellipse cx="1160" cy="300" rx="110" ry="75" fill="none" stroke="url(#stonetexture)" stroke-width="12"/>
<path d="M1100 300h120" stroke="{PALETTE['teal']}" stroke-width="4" stroke-dasharray="8 6"/><text x="1160" y="410" text-anchor="middle" font-family="sans-serif" font-size="13" fill="{PALETTE['muted']}">顶视：追逐弧</text>
{wood_rect(1320,250,170,50,8)}{wood_rect(1320,240,170,14,6)}<path d="M1320 320h170" stroke="url(#stonetexture)" stroke-width="14"/>
<text x="1405" y="410" text-anchor="middle" font-family="sans-serif" font-size="13" fill="{PALETTE['muted']}">侧视：低边与收纳</text>
<path d="M1550 240v130M1550 370h90v-130" fill="url(#stonetexture)"/><path d="M1570 335h50" stroke="{PALETTE['ink']}" stroke-width="8"/><text x="1570" y="410" text-anchor="middle" font-family="sans-serif" font-size="13" fill="{PALETTE['muted']}">剖面：外侧排水</text>'''
    material = f'''<text x="1065" y="520" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">材质细节</text>
{stone_rect(1080,550,140,60,10)}{wood_rect(1080,640,140,55,10)}
<circle cx="1260" cy="570" r="20" fill="{PALETTE['path']}"/><circle cx="1300" cy="570" r="20" fill="{PALETTE['rose']}"/><circle cx="1340" cy="570" r="20" fill="{PALETTE['teal']}"/>
<text x="1080" y="735" font-family="sans-serif" font-size="13" fill="{PALETTE['muted']}">柔色低饱和，不靠高光塑料感</text>'''
    structure = f'''<text x="1485" y="520" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">结构连接图</text>
<path d="M1490 590h300v70h-300Z" fill="url(#grasstexture)"/><path d="M1490 660h300v55h-300Z" fill="url(#stonetexture)"/>
<path d="M1560 660h100v55h-100Z" fill="{PALETTE['water']}" opacity=".65"/>
<path d="M1490 625h300" stroke="{PALETTE['teal']}" stroke-width="3" stroke-dasharray="6 5"/>
<text x="1490" y="745" font-family="sans-serif" font-size="12" fill="{PALETTE['muted']}">边界落地、排水向外、收纳独立于草坪</text>'''
    interaction = f'''<text x="90" y="850" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">宠物互动示意</text>
<path d="M200 960Q450 850 760 940" fill="none" stroke="{PALETTE['teal']}" stroke-width="5" stroke-dasharray="14 8"/>
{dog(430,960,.8,'#d49a68')}<circle cx="760" cy="940" r="18" fill="{PALETTE['rose']}"/>
{cat(700,1000,.65,'#a9a9a0',-1)}'''
    notes = f'''<text x="1070" y="850" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">真实感与可爱细节</text>
<text x="1070" y="885" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">• 有边界、排水与固定收纳位置。</text>
<text x="1070" y="915" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">• 中央只保留可穿行的追逐空间。</text>
<text x="1070" y="945" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">• 爪印指路，彩球用柔色哑光材质。</text>
<text x="1070" y="975" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">• 装饰不进入落球点与宠物急停区。</text>'''
    facility_sheet('08-facility-ball-lawn.svg', '08 / FACILITY 01', '玩球草坪：边界、排水与追逐空间', '不是一块纯色圆毯，而是可玩、可收纳、可退出的活动场', main, views, material, structure, interaction, notes)


def make_tunnel_facility():
    main = f'''<text x="90" y="190" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">设施 02 / 钻行隧道</text>
<path d="M150 700Q500 470 950 680V760H150Z" fill="url(#grasstexture)"/>
{wood_rect(330,400,110,260,20)}{wood_rect(690,400,110,260,20)}
<path d="M330 400Q550 200 800 400L800 520Q550 360 330 520Z" fill="{PALETTE['teal']}" stroke="{PALETTE['ink']}" stroke-width="3"/>
<path d="M380 410Q550 280 750 410L750 500Q550 390 380 500Z" fill="#dfe9e5" stroke="{PALETTE['cream']}" stroke-width="9"/>
<path d="M380 500Q550 390 750 500V560H380Z" fill="url(#pathgrain)"/>
<path d="M380 500Q550 390 750 500" fill="none" stroke="{PALETTE['rose']}" stroke-width="7"/>
{wood_rect(320,650,130,45,10)}{wood_rect(680,650,130,45,10)}
<path d="M340 450h60M340 490h60M340 530h60M340 570h60M700 450h60M700 490h60M700 530h60M700 570h60" stroke="{PALETTE['ink']}" stroke-width="6"/>
{cat(560,610,.85,'#a9a9a0')}{dog(760,650,.7,'#d49a68',-1)}
<text x="550" y="340" text-anchor="middle" font-family="sans-serif" font-size="16" fill="{PALETTE['cream']}">少量耳形轮廓，不改变结构厚度</text>'''
    views = f'''<text x="1070" y="190" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">三视图</text>
<path d="M1100 330Q1170 230 1240 330V370H1100Z" fill="{PALETTE['teal']}"/><path d="M1130 335Q1170 280 1210 335V370H1130Z" fill="#dfe9e5"/>
<text x="1170" y="410" text-anchor="middle" font-family="sans-serif" font-size="13" fill="{PALETTE['muted']}">正视：洞口与壁厚</text>
{wood_rect(1320,240,170,45,12)}{wood_rect(1320,285,170,45,12)}<path d="M1320 330h170" stroke="url(#pathgrain)" stroke-width="22"/>
<text x="1405" y="410" text-anchor="middle" font-family="sans-serif" font-size="13" fill="{PALETTE['muted']}">侧视：支撑与防滑</text>
<path d="M1550 250h90v120h-90Z" fill="url(#stonetexture)"/><path d="M1550 300h90" stroke="{PALETTE['cream']}" stroke-width="8"/>
<text x="1570" y="410" text-anchor="middle" font-family="sans-serif" font-size="13" fill="{PALETTE['muted']}">剖面：可见另一端</text>'''
    material = f'''<text x="1065" y="520" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">材质细节</text>
<path d="M1090 610Q1150 520 1210 610L1200 650Q1150 580 1100 650Z" fill="{PALETTE['teal']}"/>
<path d="M1110 620Q1150 570 1190 620" fill="none" stroke="{PALETTE['cream']}" stroke-width="7"/>
<path d="M1080 690h140" stroke="url(#pathgrain)" stroke-width="22"/>
<text x="1080" y="735" font-family="sans-serif" font-size="13" fill="{PALETTE['muted']}">灰青外壳、奶油内壁、低光防滑地面</text>'''
    structure = f'''<text x="1485" y="520" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">结构连接图</text>
<path d="M1510 610Q1600 500 1690 610L1690 660Q1600 570 1510 660Z" fill="{PALETTE['teal']}"/>
{wood_rect(1500,660,70,35,8)}{wood_rect(1660,660,70,35,8)}
<path d="M1530 680h120" stroke="url(#pathgrain)" stroke-width="20"/>
<text x="1490" y="745" font-family="sans-serif" font-size="12" fill="{PALETTE['muted']}">壳体与独立支撑共同落地，出口无遮挡</text>'''
    interaction = f'''<text x="90" y="850" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">宠物互动示意</text>
<path d="M180 980H850" stroke="url(#pathgrain)" stroke-width="55"/>
{cat(450,970,.75,'#a9a9a0')}{dog(720,970,.65,'#d49a68',-1)}
<path d="M500 960h170" stroke="{PALETTE['teal']}" stroke-width="4" stroke-dasharray="10 7"/><path d="M670 960l-18-10v20z" fill="{PALETTE['teal']}"/>
<text x="600" y="900" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">进入前能看到另一端，退出不被后宠堵住</text>'''
    notes = f'''<text x="1070" y="850" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">真实感与可爱细节</text>
<text x="1070" y="885" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">• 外壳厚度、独立支撑与防滑地面明确。</text>
<text x="1070" y="915" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">• 出入口不被耳形装饰或植被遮挡。</text>
<text x="1070" y="945" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">• 圆润洞口只在上沿做少量耳形轮廓。</text>
<text x="1070" y="975" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">• 两端均可退出，后宠能看见前宠位置。</text>'''
    facility_sheet('09-facility-tunnel.svg', '09 / FACILITY 02', '钻行隧道：厚度、支撑与可见出口', '既能钻进，也能随时看清并退出；装饰不取代结构', main, views, material, structure, interaction, notes)


make_entry_closeup()
make_play_lawn_closeup()
make_quiet_retreat_closeup()
make_ball_facility()
make_tunnel_facility()


def make_hoops_facility():
    main = f'''<text x="90" y="190" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">设施 03 / 低矮跳圈与跨杆</text>
<path d="M140 700Q500 470 950 680V760H140Z" fill="url(#grasstexture)"/>
{wood_rect(300,430,34,220,9)}{wood_rect(520,430,34,220,9)}{wood_rect(740,430,34,220,9)}
<path d="M300 430Q410 270 520 430" fill="none" stroke="{PALETTE['rose']}" stroke-width="14"/>
<path d="M520 430Q630 310 740 430" fill="none" stroke="{PALETTE['cream']}" stroke-width="14"/>
{wood_rect(270,650,90,35,10)}{wood_rect(490,650,90,35,10)}{wood_rect(710,650,90,35,10)}
<path d="M340 500h150M560 540h150" stroke="{PALETTE['teal']}" stroke-width="14" stroke-linecap="round"/>
<path d="M335 430Q410 350 485 430M555 430Q630 370 705 430" fill="none" stroke="{PALETTE['path']}" stroke-width="4" stroke-dasharray="8 6"/>
{dog(560,670,.9,'#d49a68')}{cat(760,700,.7,'#a9a9a0',-1)}
<path d="M500 630Q540 560 600 600" fill="none" stroke="{PALETTE['teal']}" stroke-width="4" stroke-dasharray="10 7"/>
<text x="640" y="360" text-anchor="middle" font-family="sans-serif" font-size="16" fill="{PALETTE['muted']}">花瓣与云朵只作边框，不侵占跳跃净空</text>'''
    views = f'''<text x="1070" y="190" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">三视图</text>
{wood_rect(1100,250,22,120,7)}{wood_rect(1240,250,22,120,7)}<path d="M1100 250Q1170 160 1240 250" fill="none" stroke="{PALETTE['rose']}" stroke-width="10"/>
<text x="1170" y="410" text-anchor="middle" font-family="sans-serif" font-size="13" fill="{PALETTE['muted']}">正视：跳跃净空</text>
{wood_rect(1320,250,22,120,7)}{wood_rect(1320,650-350,22,35,7)}<path d="M1320 300h150" stroke="{PALETTE['teal']}" stroke-width="10"/>
<text x="1395" y="410" text-anchor="middle" font-family="sans-serif" font-size="13" fill="{PALETTE['muted']}">侧视：稳定底座</text>
<path d="M1530 300h150" stroke="{PALETTE['teal']}" stroke-width="12"/><circle cx="1560" cy="300" r="30" fill="none" stroke="{PALETTE['rose']}" stroke-width="8"/>
<text x="1605" y="410" text-anchor="middle" font-family="sans-serif" font-size="13" fill="{PALETTE['muted']}">顶视：前后不串线</text>'''
    material = f'''<text x="1065" y="520" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">材质细节</text>
{wood_rect(1080,550,140,55,10)}<path d="M1080 650Q1150 560 1220 650" fill="none" stroke="{PALETTE['rose']}" stroke-width="11"/>
<path d="M1080 690h160" stroke="{PALETTE['teal']}" stroke-width="12"/>
<text x="1080" y="735" font-family="sans-serif" font-size="13" fill="{PALETTE['muted']}">木支架、柔色包边、可触横梁</text>'''
    structure = f'''<text x="1485" y="520" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">结构连接图</text>
{wood_rect(1530,560,30,120,8)}{wood_rect(1500,680,90,30,8)}
<path d="M1545 560h150" stroke="{PALETTE['teal']}" stroke-width="12"/><circle cx="1545" cy="560" r="16" fill="{PALETTE['cream']}" stroke="{PALETTE['teal']}" stroke-width="3"/>
<path d="M1545 590v60" stroke="{PALETTE['teal']}" stroke-width="3" stroke-dasharray="5 4"/>
<text x="1490" y="745" font-family="sans-serif" font-size="12" fill="{PALETTE['muted']}">宽底座＋圆角插接横梁，避免倒伏</text>'''
    interaction = f'''<text x="90" y="850" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">宠物互动示意</text>
<path d="M200 970H850" stroke="url(#pathgrain)" stroke-width="55"/>
{wood_rect(480,860,22,100,7)}{wood_rect(620,860,22,100,7)}<path d="M480 860Q550 790 620 860" fill="none" stroke="{PALETTE['rose']}" stroke-width="10"/>
{dog(560,990,.8,'#d49a68')}{cat(760,990,.6,'#a9a9a0',-1)}
<text x="690" y="900" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">低杆练习与大杆绕行并存，猫狗不必走同一路线</text>'''
    notes = f'''<text x="1070" y="850" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">真实感与可爱细节</text>
<text x="1070" y="885" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">• 支架有宽底座和圆角插接，跳落时不倒伏。</text>
<text x="1070" y="915" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">• 高低两种尺度，幼宠与大狗都有绕行选择。</text>
<text x="1070" y="945" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">• 花瓣与云朵仅作边框，不缩小跳跃净空。</text>
<text x="1070" y="975" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">• 入口、落点和后宠等待区互不重叠。</text>'''
    facility_sheet('10-facility-hoops-hurdles.svg', '10 / FACILITY 03', '低矮跳圈与跨杆：稳定与尺度', '用支架和净空建立可爱，不用夸张造型挤占跳跃路线', main, views, material, structure, interaction, notes)


def make_balance_facility():
    main = f'''<text x="90" y="190" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">设施 04 / 平衡木与小坡桥</text>
<path d="M150 700Q500 470 950 680V760H150Z" fill="url(#grasstexture)"/>
<path d="M320 650L740 420L790 460L370 690Z" fill="url(#woodgrain)" stroke="{PALETTE['darkwood']}" stroke-width="3"/>
<path d="M320 650L370 690V730L320 690Z" fill="#6f5138"/>
<path d="M740 420L790 460V500L740 460Z" fill="#6f5138"/>
{wood_rect(340,690,45,65,8)}{wood_rect(720,480,45,65,8)}
<path d="M400 630l50-35M480 580l50-35M560 530l50-35M640 480l50-35" stroke="{PALETTE['cream']}" stroke-width="7" stroke-linecap="round"/>
{paw(440,630,.45,PALETTE['cream'])}{paw(580,540,.45,PALETTE['cream'])}
{dog(560,580,.85,'#d49a68')}
<path d="M390 670L760 435" stroke="{PALETTE['teal']}" stroke-width="3" stroke-dasharray="8 6"/>
<text x="580" y="430" text-anchor="middle" font-family="sans-serif" font-size="16" fill="{PALETTE['muted']}">板厚、坡度与连接件同时可读</text>'''
    views = f'''<text x="1070" y="190" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">三视图</text>
<path d="M1100 340L1230 260L1260 285L1130 365Z" fill="url(#woodgrain)" stroke="{PALETTE['darkwood']}" stroke-width="2"/>
<path d="M1100 340L1130 365V390L1100 365Z" fill="#6f5138"/>
<text x="1180" y="410" text-anchor="middle" font-family="sans-serif" font-size="13" fill="{PALETTE['muted']}">侧视：坡度与板厚</text>
{wood_rect(1330,250,180,40,8)}{wood_rect(1350,290,28,85,8)}{wood_rect(1470,290,28,85,8)}
<path d="M1350 270h120" stroke="{PALETTE['cream']}" stroke-width="6"/>
<text x="1410" y="410" text-anchor="middle" font-family="sans-serif" font-size="13" fill="{PALETTE['muted']}">正视：支撑与踏面</text>
<path d="M1540 250h100v100h-100Z" fill="url(#woodgrain)"/><path d="M1550 270h80M1550 300h80" stroke="{PALETTE['cream']}" stroke-width="5"/>
<text x="1590" y="410" text-anchor="middle" font-family="sans-serif" font-size="13" fill="{PALETTE['muted']}">顶视：连续踏点</text>'''
    material = f'''<text x="1065" y="520" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">材质细节</text>
{wood_rect(1080,550,160,55,8)}<path d="M1080 620h160v35h-160Z" fill="#6f5138"/>
{paw(1160,680,.55,PALETTE['cream'])}
<text x="1080" y="735" font-family="sans-serif" font-size="13" fill="{PALETTE['muted']}">顶面木纹与端面差异，爪印踏点浅嵌</text>'''
    structure = f'''<text x="1485" y="520" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">结构连接图</text>
<path d="M1510 610L1690 520L1710 545L1530 635Z" fill="url(#woodgrain)" stroke="{PALETTE['darkwood']}" stroke-width="2"/>
{wood_rect(1520,640,36,55,8)}{wood_rect(1670,560,36,55,8)}
<path d="M1530 650h120" stroke="{PALETTE['teal']}" stroke-width="3" stroke-dasharray="5 4"/>
<text x="1490" y="745" font-family="sans-serif" font-size="12" fill="{PALETTE['muted']}">板端插入支撑件，不用悬浮单板</text>'''
    interaction = f'''<text x="90" y="850" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">宠物互动示意</text>
<path d="M230 980L760 850L790 885L260 1015Z" fill="url(#woodgrain)" stroke="{PALETTE['darkwood']}" stroke-width="2"/>
{dog(510,940,.8,'#d49a68')}{paw(420,970,.45,PALETTE['cream'])}{paw(600,920,.45,PALETTE['cream'])}
<text x="690" y="900" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">前掌连续落点，侧向留出让行和下来空间</text>'''
    notes = f'''<text x="1070" y="850" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">真实感与可爱细节</text>
<text x="1070" y="885" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">• 坡度适中，木板厚度和端面明确。</text>
<text x="1070" y="915" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">• 板端与支撑件连接，不做悬浮装饰板。</text>
<text x="1070" y="945" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">• 爪印踏点浅嵌，木构件边缘圆角。</text>
<text x="1070" y="975" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">• 两侧留有下来与让行空间，不形成独木死路。</text>'''
    facility_sheet('11-facility-balance-bridge.svg', '11 / FACILITY 04', '平衡木与小坡桥：坡度、板厚与连接', '每一步都落在真实构件上，爪印只提示节奏', main, views, material, structure, interaction, notes)


def make_cat_climb_facility():
    main = f'''<text x="90" y="190" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">设施 05 / 猫咪攀爬与躲藏区</text>
<path d="M150 700Q500 470 950 680V760H150Z" fill="url(#grasstexture)"/>
{wood_rect(420,300,65,390,18)}{wood_rect(660,360,65,330,18)}
<path d="M420 470Q450 430 485 470V570Q450 610 420 570Z" fill="{PALETTE['darkwood']}"/>
<path d="M435 490Q450 465 470 490V555Q450 580 435 555Z" fill="#3e5147"/>
{wood_rect(330,380,230,34,12)}{wood_rect(610,450,230,34,12)}{wood_rect(390,570,280,34,12)}
<path d="M330 380Q445 310 560 380Q445 420 330 380Z" fill="{PALETTE['forest']}" opacity=".8"/>
<path d="M610 450Q725 380 840 450Q725 490 610 450Z" fill="{PALETTE['forest']}" opacity=".8"/>
<path d="M390 570Q530 500 670 570Q530 610 390 570Z" fill="{PALETTE['forest']}" opacity=".8"/>
<path d="M560 400L620 430M710 484L640 540" stroke="{PALETTE['teal']}" stroke-width="8" stroke-dasharray="10 8"/>
{cat(520,540,.8,'#a9a9a0')}{cat(455,520,.55,'#b4a091',-1)}
<path d="M700 650Q760 560 840 520" fill="none" stroke="{PALETTE['teal']}" stroke-width="4" stroke-dasharray="10 7"/>
<text x="700" y="330" text-anchor="middle" font-family="sans-serif" font-size="16" fill="{PALETTE['muted']}">叶片平台、抓挠柱与树洞，多条上下路线</text>'''
    views = f'''<text x="1070" y="190" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">三视图</text>
{wood_rect(1100,240,40,140,10)}{wood_rect(1070,280,160,24,9)}{wood_rect(1130,350,150,24,9)}
<path d="M1110 300Q1140 260 1170 300V350Q1140 380 1110 350Z" fill="{PALETTE['darkwood']}"/>
<text x="1170" y="410" text-anchor="middle" font-family="sans-serif" font-size="13" fill="{PALETTE['muted']}">正视：平台与树洞</text>
{wood_rect(1330,240,40,140,10)}{wood_rect(1300,300,170,24,9)}{wood_rect(1360,360,140,24,9)}
<path d="M1370 260L1430 340" stroke="{PALETTE['teal']}" stroke-width="6" stroke-dasharray="8 6"/>
<text x="1405" y="410" text-anchor="middle" font-family="sans-serif" font-size="13" fill="{PALETTE['muted']}">侧视：连续上行</text>
<ellipse cx="1570" cy="300" rx="105" ry="65" fill="{PALETTE['forest']}" opacity=".75"/><ellipse cx="1570" cy="300" rx="50" ry="28" fill="#a9ba83"/>
<path d="M1520 300h100" stroke="{PALETTE['teal']}" stroke-width="4" stroke-dasharray="8 6"/>
<text x="1570" y="410" text-anchor="middle" font-family="sans-serif" font-size="13" fill="{PALETTE['muted']}">顶视：多向出入</text>'''
    material = f'''<text x="1065" y="520" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">材质细节</text>
{wood_rect(1080,550,140,55,10)}<path d="M1090 570h120M1090 585h120M1090 600h120" stroke="{PALETTE['darkwood']}" stroke-width="3"/>
<path d="M1080 650Q1150 590 1220 650Q1150 680 1080 650Z" fill="{PALETTE['forest']}" opacity=".8"/>
<text x="1080" y="735" font-family="sans-serif" font-size="13" fill="{PALETTE['muted']}">抓挠木纹、叶片平台、非镜面树洞内壁</text>'''
    structure = f'''<text x="1485" y="520" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">结构连接图</text>
{wood_rect(1530,540,45,150,10)}{wood_rect(1500,590,150,28,10)}{wood_rect(1560,650,160,28,10)}
<path d="M1575 560L1650 630" stroke="{PALETTE['teal']}" stroke-width="5" stroke-dasharray="8 6"/>
<path d="M1550 600h-50M1610 660h50" stroke="{PALETTE['teal']}" stroke-width="2"/>
<text x="1490" y="745" font-family="sans-serif" font-size="12" fill="{PALETTE['muted']}">平台穿柱固定，路径不依赖单一跳点</text>'''
    interaction = f'''<text x="90" y="850" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">宠物互动示意</text>
{wood_rect(350,850,45,150,10)}{wood_rect(300,900,180,25,10)}{wood_rect(460,960,200,25,10)}
{cat(470,940,.7,'#a9a9a0')}{cat(390,920,.5,'#b4a091',-1)}
<path d="M500 920L580 880" stroke="{PALETTE['teal']}" stroke-width="4" stroke-dasharray="8 6"/>
<text x="620" y="890" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">可爬、可躲、可从另一侧下来；不会被看见即困住</text>'''
    notes = f'''<text x="1070" y="850" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">真实感与可爱细节</text>
<text x="1070" y="885" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">• 分层平台、抓挠柱与树洞都有真实厚度。</text>
<text x="1070" y="915" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">• 上下与进出路线至少两条，避免单点拥堵。</text>
<text x="1070" y="945" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">• 叶片只做平台轮廓，树洞不做夸张猫脸。</text>
<text x="1070" y="975" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">• 跳点和藏身处不遮挡主通道与其他宠物。</text>'''
    facility_sheet('12-facility-cat-climb.svg', '12 / FACILITY 05', '猫咪攀爬与躲藏区：分层与多路线', '叶片平台、树洞与抓挠柱共同服务猫的行为，而不是装饰布景', main, views, material, structure, interaction, notes)


def make_rest_water_facility():
    main = f'''<text x="90" y="190" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">设施 06 / 遮阴休息与饮水区</text>
<path d="M150 700Q500 470 950 680V760H150Z" fill="url(#grasstexture)"/>
{wood_rect(340,460,240,30,10)}{wood_rect(360,490,28,150,8)}{wood_rect(540,490,28,150,8)}
<path d="M300 460Q460 270 620 460L590 500Q460 390 330 500Z" fill="{PALETTE['cream']}" stroke="{PALETTE['rose']}" stroke-width="4"/>
{wood_rect(700,500,180,30,9)}{wood_rect(720,530,24,100,8)}{wood_rect(840,530,24,100,8)}
<ellipse cx="745" cy="580" rx="34" ry="12" fill="url(#water)"/><ellipse cx="815" cy="580" rx="34" ry="12" fill="url(#water)"/>
<path d="M710 600h170l-20 35H730Z" fill="{PALETTE['water']}" opacity=".45"/>
{cat(510,650,.85,'#a9a9a0')}{dog(760,690,.75,'#6f756f',-1)}
<text x="470" y="620" text-anchor="middle" font-family="sans-serif" font-size="15" fill="{PALETTE['muted']}">遮阴、碗架与溢水托盘组成完整休息点</text>'''
    views = f'''<text x="1070" y="190" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">三视图</text>
<path d="M1100 340Q1170 230 1240 340L1215 360Q1170 310 1125 360Z" fill="{PALETTE['cream']}" stroke="{PALETTE['rose']}" stroke-width="3"/>
<text x="1170" y="410" text-anchor="middle" font-family="sans-serif" font-size="13" fill="{PALETTE['muted']}">正视：花苞遮阴</text>
{wood_rect(1320,250,170,26,8)}{wood_rect(1340,276,22,90,6)}{wood_rect(1450,276,22,90,6)}<ellipse cx="1390" cy="330" rx="32" ry="11" fill="url(#water)"/>
<text x="1390" y="410" text-anchor="middle" font-family="sans-serif" font-size="13" fill="{PALETTE['muted']}">侧视：碗架与座席</text>
<ellipse cx="1570" cy="300" rx="90" ry="55" fill="url(#pathgrain)"/><ellipse cx="1570" cy="300" rx="30" ry="12" fill="url(#water)"/><path d="M1530 340h80l-15 25h-50Z" fill="{PALETTE['water']}" opacity=".45"/>
<text x="1570" y="410" text-anchor="middle" font-family="sans-serif" font-size="13" fill="{PALETTE['muted']}">顶视：溢水外导</text>'''
    material = f'''<text x="1065" y="520" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">材质细节</text>
<path d="M1080 610Q1150 520 1220 610L1200 640Q1150 580 1100 640Z" fill="{PALETTE['cream']}" stroke="{PALETTE['rose']}" stroke-width="3"/>
<ellipse cx="1120" cy="690" rx="40" ry="14" fill="url(#water)"/>
<text x="1190" y="700" font-family="sans-serif" font-size="13" fill="{PALETTE['muted']}">哑光顶棚、可清洗碗架、浅水色与托盘</text>'''
    structure = f'''<text x="1485" y="520" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">结构连接图</text>
{wood_rect(1530,560,200,26,8)}{wood_rect(1550,586,24,90,8)}{wood_rect(1710,586,24,90,8)}
<path d="M1510 620h220l-25 45h-170Z" fill="{PALETTE['water']}" opacity=".45"/>
<path d="M1550 665h-45M1730 665h45" stroke="{PALETTE['teal']}" stroke-width="2"/>
<text x="1490" y="690" font-family="sans-serif" font-size="12" fill="{PALETTE['muted']}">碗架固定于托盘，溢水向外侧导流</text>'''
    interaction = f'''<text x="90" y="850" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">宠物互动示意</text>
<path d="M240 950Q470 850 760 930" fill="none" stroke="url(#pathgrain)" stroke-width="60"/>
{cat(520,970,.8,'#a9a9a0')}{dog(720,970,.7,'#6f756f',-1)}
<ellipse cx="590" cy="960" rx="26" ry="9" fill="url(#water)"/>
<text x="700" y="900" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">可饮水、可独处，也可并肩休息；不必穿越草坪</text>'''
    notes = f'''<text x="1070" y="850" font-family="sans-serif" font-size="18" font-weight="700" fill="{PALETTE['teal']}">真实感与可爱细节</text>
<text x="1070" y="885" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">• 花苞顶棚提供真实遮阴，不遮挡邻近视线。</text>
<text x="1070" y="915" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">• 水碗有抬高支架、托盘与外侧溢水路径。</text>
<text x="1070" y="945" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">• 座椅和碗架离开追逐弧与设施出口。</text>
<text x="1070" y="975" font-family="sans-serif" font-size="14" fill="{PALETTE['muted']}">• 安静区可从入口直接看到，方便退出。</text>'''
    facility_sheet('13-facility-rest-water.svg', '13 / FACILITY 06', '遮阴休息与饮水区：安静、清洁与退出', '把遮阴、饮水和溢水处理做成完整设施，而不是角落摆两个碗', main, views, material, structure, interaction, notes)


make_hoops_facility()
make_balance_facility()
make_cat_climb_facility()
make_rest_water_facility()
