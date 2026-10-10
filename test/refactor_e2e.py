# -*- coding: utf-8 -*-
"""重构后端到端测试脚本（可重复执行）：
页面路由 / 登录注册 / GLM 对话 / 头像管线 / 日记 / 评价。
"""
import sys

import requests

BASE = 'http://127.0.0.1:5000'
s = requests.Session()
# 本机回环 + 长耗时 LLM 请求下 keep-alive 复用会被中间层干扰，改为每请求独立连接
s.headers.update({'Connection': 'close'})
ok = fail = 0


def check(name, cond, detail=''):
    global ok, fail
    if cond:
        ok += 1
        print(f'  PASS  {name} {detail}')
    else:
        fail += 1
        print(f'  FAIL  {name} {detail}')


print('== 1. 页面路由 ==')
for path in ['/', '/gpt', '/reader_login', '/register', '/manager_login',
             '/register_admin', '/diary', '/remark_pet', '/about',
             '/remark?book_name=%E6%9F%AF%E5%9F%BA']:
    r = s.get(BASE + path)
    check(f'GET {path}', r.status_code == 200, f'[{r.status_code}]')

print('== 2. 静态代理 ==')
for path in ['/images/f.png', '/css/b.jpg', '/js/script.js',
             '/static/js/vendor/three.min.js']:
    r = s.get(BASE + path)
    check(f'GET {path}', r.status_code == 200, f'[{r.status_code}]')

r = s.get(BASE + '/den')
check('3D 宠物小窝页面', r.status_code == 200 and 'den-canvas' in r.text, f'[{r.status_code}]')
check('视觉互动按钮', r.status_code == 200 and 'btn-vision' in r.text and 'den_vision.js' in r.text)

print('== 2b. 视觉互动资产（MediaPipe 本地化）==')
r = s.get(BASE + '/static/js/den_vision.js')
check('GET /static/js/den_vision.js', r.status_code == 200 and 'DenVision' in r.text, f'[{r.status_code}]')
for path in ['/static/js/vendor/mediapipe/vision_bundle.mjs',
             '/static/js/vendor/mediapipe/vision_wasm_internal.wasm',
             '/static/js/vendor/mediapipe/face_landmarker.task',
             '/static/js/vendor/mediapipe/hand_landmarker.task']:
    r = s.get(BASE + path)
    big_ok = r.status_code == 200 and len(r.content) > 100000
    check(f'GET {path}', big_ok, f'[{r.status_code} {len(r.content)}B]')

print('== 3. 注册/登录/读者页 ==')
s.post(BASE + '/register', data={
    'username': 'e2e_test', 'password': '123456', 'password2': '123456',
    'college': 't', 'number': '1', 'email': 't@t.com'}, allow_redirects=False)
r = s.post(BASE + '/reader_login', data={'username': 'e2e_test', 'password': '123456'},
           allow_redirects=False)
check('登录跳转 /reader', r.status_code == 302 and '/reader' in r.headers.get('Location', ''))
for path in ['/reader', '/reader/info', '/reader/modify', '/reader/histroy']:
    r = s.get(BASE + path)
    check(f'GET {path}', r.status_code == 200, f'[{r.status_code}]')
r = s.post(BASE + '/reader/query', data={'item': 'name', 'query': '活着'})
check('图书搜索有结果', r.status_code == 200 and '活着' in r.text)

print('== 4. GLM 对话 ==')
r = s.post(BASE + '/get_gpt_response', json={
    'message': '用五个字打个招呼', 'chatHistory': [], 'model': 'glm-4.5-flash', 'petId': 1},
    timeout=120)
d = r.json()
check('柯基对话', r.status_code == 200 and d.get('reply'), d.get('reply', '')[:30])
check('返回宠物信息', d.get('pet', {}).get('name') == '柯基' and d.get('pet', {}).get('avatar') == 'f.png')
r = s.post(BASE + '/get_gpt_response', json={
    'message': '你是猫还是狗？', 'chatHistory': [], 'model': 'glm-4.5-flash', 'petId': 3},
    timeout=120)
d = r.json()
check('切换猫咪', d.get('pet', {}).get('name') == '猫咪' and '喵' in d.get('reply', ''), d.get('reply', '')[:30])
r = s.post(BASE + '/get_gpt_response', json={'message': 'hi', 'model': 'gpt-4o'}, timeout=30)
check('非法模型被拒', r.status_code == 503 and 'error' in r.json())

print('== 5. 头像管线 ==')
with open('templates/images/dog1.png', 'rb') as f:
    r = s.post(BASE + '/upload-avatar',
               files={'image': ('my-dog.png', f, 'image/png')}, timeout=300)
d = r.json()
if d.get('success'):
    img = s.get(BASE + d['image_url'])
    check('头像生成并可访问', img.status_code == 200 and img.headers.get('Content-Type', '').startswith('image'),
          f'{len(img.content)} bytes {d["image_url"]}')
    with open('output_images/refactored_avatar_test.png', 'wb') as f:
        f.write(img.content)
else:
    check('头像生成', False, str(d)[:120])
r = s.post(BASE + '/upload-avatar', files={'image': ('bad.exe', b'MZ', 'application/x-msdownload')})
check('非法格式被拒', r.status_code == 400)

print('== 6. 日记 ==')
r = s.post(BASE + '/get-diary', json={'chatHistory': [
    {'sender': '小明', 'message': '你好', 'role': 'user'},
    {'sender': '柯基', 'message': '汪汪！', 'role': 'assistant'}]})
check('日记文本', r.status_code == 200 and '汪汪' in r.json().get('text', ''))

print('== 7. 宠物评分 ==')
r = s.post(BASE + '/remark', data={'book_name': '柯基', 'name': 'e2e_test',
                                   'rating': '5', 'review': '很可爱'})
check('宠物评分提交', r.status_code == 200 and '柯基' in r.text)
r = s.post(BASE + '/remark', data={'book_name': '不存在的', 'name': 'x', 'rating': '5', 'review': 'y'})
check('未知名称 404', r.status_code == 404)

print(f'\n结果: {ok} 通过, {fail} 失败')
sys.exit(1 if fail else 0)
