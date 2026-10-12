# -*- coding: utf-8 -*-
"""实时语音 P0 自动化单测：JWT 签发 + session 接口行为（不触网、不打印密钥）。

运行：cd ~/petchat && python3 test/test_realtime_jwt.py
"""
import base64
import hashlib
import hmac
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402

PASS = 0
FAIL = 0


def check(name, cond, detail=''):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f'  PASS  {name}')
    else:
        FAIL += 1
        print(f'  FAIL  {name} {detail}')


def b64d(seg):
    return base64.urlsafe_b64decode(seg + '=' * (-len(seg) % 4))


def main():
    app = create_app()
    api_key = app.config['GLM_API_KEY']
    with app.test_request_context():
        from app.services.realtime_service import RealtimeError, build_realtime_session
        print('== 1. JWT 签发 ==')
        body = build_realtime_session(1, 'male')
        tok = body['token']
        segs = tok.split('.')
        check('JWT 三段式', len(segs) == 3)
        hdr = json.loads(b64d(segs[0]))
        check('header alg=HS256', hdr.get('alg') == 'HS256')
        check('header sign_type=SIGN', hdr.get('sign_type') == 'SIGN')
        payload = json.loads(b64d(segs[1]))
        check('payload 含 api_key/exp/timestamp',
              sorted(payload.keys()) == ['api_key', 'exp', 'timestamp'])
        ttl = app.config['GLM_REALTIME_TOKEN_TTL']
        check(f'exp ≈ now+{ttl}s', 0 <= payload['exp'] - time.time() <= ttl + 5)
        check('expiresAt 与 exp 一致', body['expiresAt'] == payload['exp'])
        # 用 secret 重算 HMAC 验签（不打印任何密钥内容）
        secret = api_key.split('.', 1)[1]
        signing_input = f'{segs[0]}.{segs[1]}'.encode()
        expect = base64.urlsafe_b64encode(
            hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
        ).rstrip(b'=').decode()
        check('HMAC-SHA256 签名可验证', expect == segs[2])
        check('响应不含长期 API Key', api_key not in json.dumps(body))
        cfg = body['config']
        check('voice 走白名单', cfg['voice'] in ('tongtong', 'jam', 'xiaochen', 'chuichui'))
        check('server_vad', cfg['turn_detection'] == {'type': 'server_vad'})
        check('输入 pcm16 / 输出 pcm',
              cfg['input_audio_format'] == 'pcm16' and cfg['output_audio_format'] == 'pcm')
        check('人设含语音约束', '语音通话' in cfg['instructions'] and '打断' in cfg['instructions'])

        print('== 2. 非法入参 ==')
        try:
            build_realtime_session(99, None)
            check('非法 petId 抛错', False)
        except RealtimeError as e:
            check('非法 petId 抛错 404', e.status == 404)

    print('== 3. 接口行为（test client） ==')
    c = app.test_client()
    r = c.post('/api/realtime/session', json={'petId': 2, 'petGender': 'hacker'})
    check('POST 200', r.status_code == 200)
    check('Cache-Control no-store', r.headers.get('Cache-Control') == 'no-store')
    r2 = c.post('/api/realtime/session', json={'petId': 'abc'})
    check('非法 petId 400', r2.status_code == 400)

    print(f'\n结果: {PASS} 通过, {FAIL} 失败')
    return 1 if FAIL else 0


if __name__ == '__main__':
    sys.exit(main())
