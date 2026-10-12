# -*- coding: utf-8 -*-
"""宠物聊天相关路由：聊天页、AI 对话、头像动漫化、日记本、评价。"""
from flask import (Blueprint, current_app, jsonify, render_template,
                   request, session)

from ..db import execute_db, query_db
from ..llm import pets as pet_registry
from ..services import avatar_service, chat_service

bp = Blueprint('chat', __name__)


@bp.route('/gpt')
def gpt():
    pets = [pet_registry.public_info(p) for p in pet_registry.list_pets()]
    # ?pet=N 预选宠物（首页宠物卡直达；非法值回落到第一只）
    try:
        initial = int(request.args.get('pet', pets[0]['id']))
    except (TypeError, ValueError):
        initial = pets[0]['id']
    if not any(p['id'] == initial for p in pets):
        initial = pets[0]['id']
    return render_template('gpt_me.html', pets=pets,
                           models=current_app.config['GLM_MODELS'],
                           initial_pet=initial)


@bp.route('/get_gpt_response', methods=['POST'])
def get_gpt_response():
    payload, status = chat_service.handle_chat(request.get_json(silent=True))
    return jsonify(payload), status


@bp.route('/upload-avatar', methods=['POST'])
def upload_avatar():
    payload, status = avatar_service.process_avatar(request.files.get('image'))
    return jsonify(payload), status


@bp.route('/diary')
def diary():
    return render_template('diary.html')


@bp.route('/den')
def den():
    """3D 宠物小窝：本地 Three.js 程序化宠物 + 抚摸/喂食/亲密度/场景内聊天。"""
    pets = [pet_registry.public_info(p) for p in pet_registry.list_pets()]
    return render_template('den.html', pets=pets,
                           models=current_app.config['GLM_MODELS'])


@bp.route('/get-diary', methods=['POST'])
def get_diary():
    """把浏览器 localStorage 里的聊天记录整理成日记文本。"""
    try:
        chat_history = (request.get_json(silent=True) or {}).get('chatHistory', [])
        lines = []
        for entry in chat_history:
            if not isinstance(entry, dict):
                continue
            sender = entry.get('sender') or ('我' if entry.get('role') == 'user' else '宠物')
            message = str(entry.get('message') or '').strip()
            if message:
                lines.append(f'{sender}: {message}')
        return jsonify({'success': True, 'text': '\n\n'.join(lines)})
    except Exception as e:  # noqa: BLE001 —— 与旧版一致，向前端返回明确错误
        return jsonify({'success': False, 'error': str(e)}), 400


@bp.route('/remark_pet')
def remark_pet():
    """宠物反馈页：真实宠物注册表 + 各宠实时评分（v2 前端用）。"""
    pets = []
    for p in pet_registry.list_pets():
        info = pet_registry.public_info(p)
        row = query_db('SELECT AVG(rating) AS r, COUNT(*) AS c FROM reviews WHERE book_id = ?',
                       [f"pet{p['id']}"], one=True)
        info['avg_rating'] = round(row['r'], 1) if row and row['c'] else None
        info['review_count'] = row['c'] or 0
        pets.append(info)
    return render_template('remark_pet.html', pets=pets,
                           user_name=session.get('user_id') or '')


# ---------------------------------------------------------------------
# 评价页：图书评价 + 宠物评分共用一张 reviews 表，宠物用 book_id='petN' 关联
# ---------------------------------------------------------------------
def _resolve_target(name):
    """按名称找到被评价对象：先查图书，再查宠物注册表。返回 (id, 名称) 或 (None, None)。"""
    if not name:
        return None, None
    book = query_db('SELECT book_id, book_name FROM books WHERE book_name = ?',
                    [name], one=True)
    if book:
        return book['book_id'], book['book_name']
    for pet in pet_registry.list_pets():
        if name in (pet.get('name'), pet.get('role'), *(pet.get('aliases') or [])):
            return f"pet{pet['id']}", pet.get('name', pet['role'])
    return None, None


def _remark_view(target_id, target_name, submitted=False):
    """组装评价页上下文：宠物显示头像与简介，图书显示出版信息；评论列表两种都显示。"""
    pet = None
    if target_id.startswith('pet'):
        p = pet_registry.get_pet(int(target_id[3:]))
        pet = {'name': p.get('name', p['role']),
               'avatar': p.get('avatar', 'c.png'),
               'description': p['description']}
    book_row = query_db('SELECT * FROM books WHERE book_id = ?', [target_id], one=True)
    book = dict(book_row) if book_row else {
        'book_id': target_id, 'book_name': target_name, 'author': '',
        'publish_com': '', 'publish_date': '', 'summary': '', 'author_jj': ''}
    reviews = query_db('SELECT * FROM reviews WHERE book_id = ?', [target_id])
    rated = [r['rating'] for r in reviews if r['rating']]
    avg_rating = round(sum(rated) / len(rated), 1) if rated else None
    # 相关推荐：宠物页推荐其他宠物，图书页推荐宠物们
    recommends = [p.get('name', p['role']) for p in pet_registry.list_pets()]
    if pet:
        recommends = [n for n in recommends if n != target_name]
    return render_template('remark.html', book=book, pet=pet,
                           book_name=target_name, reviews=reviews,
                           avg_rating=avg_rating, review_count=len(reviews),
                           pets_in_recommend=recommends, submitted=submitted)


@bp.route('/remark', methods=['GET', 'POST'])
def remark():
    if request.method == 'POST':
        target_id, target_name = _resolve_target(request.form.get('book_name'))
        if not target_id:
            return '未找到该图书或宠物', 404
        name = request.form.get('name')
        rating = request.form.get('rating')
        review_text = request.form.get('review')
        if not all([name, rating, review_text]):
            return '所有字段都是必填的', 400
        try:
            execute_db('INSERT INTO reviews (name, rating, review_text, book_id) VALUES (?, ?, ?, ?)',
                       [name, int(rating), review_text, target_id])
        except (ValueError, TypeError):
            return '评分必须是数字', 400
        return _remark_view(target_id, target_name, submitted=True)

    target_id, target_name = _resolve_target(request.args.get('book_name'))
    if not target_id:
        return '未提供或未找到名称', 404
    return _remark_view(target_id, target_name)


# 叫声类别白名单（与 static/audio/pets/<species>/<kind>_N.wav 对应）
PET_SOUND_KINDS = ('bark', 'whine', 'meow', 'purr')


@bp.route('/api/pet-sound', methods=['GET'])
def pet_sound():
    """真实宠物叫声（v1.0.0）：GET ?petId=&kind= → 随机返回一条 wav 变体。

    - 物种由服务端 PET_SPECIES 决定，kind 白名单校验，杜绝路径拼接；
    - 每类多条变体随机挑一条，配合前端 ±1.5 半音微变调避免机械重复；
    - 库缺失返回 404，前端降级为人声 TTS。
    """
    try:
        pet_id = int(request.args.get('petId', 1))
    except (TypeError, ValueError):
        return jsonify({'error': 'invalid petId'}), 400
    kind = request.args.get('kind', 'bark')
    if kind not in PET_SOUND_KINDS:
        return jsonify({'error': 'invalid kind'}), 400
    species = (current_app.config.get('PET_SPECIES') or {}).get(pet_id)
    if not species:
        return jsonify({'error': 'unknown pet'}), 400
    import os as _os
    import random as _random
    from flask import send_file as _send_file
    d = _os.path.join(current_app.static_folder, 'audio', 'pets', species)
    try:
        variants = sorted(f for f in _os.listdir(d)
                          if f.startswith(kind + '_') and f.endswith('.wav'))
    except OSError:
        variants = []
    if not variants:
        return jsonify({'error': 'no sound asset'}), 404
    resp = _send_file(_os.path.join(d, _random.choice(variants)),
                      mimetype='audio/wav', conditional=True)
    resp.headers['Cache-Control'] = 'public, max-age=86400'
    return resp


@bp.route('/api/tts', methods=['POST'])
def tts():
    """GLM-TTS 语音合成：POST {text, petId} → audio/wav 二进制。

    音色由服务端按 petId 从配置白名单选择（S1-04）；
    客户端传入的 voice 字段被忽略，避免无效值打到上游。
    """
    data = request.get_json(silent=True) or {}
    text = str(data.get('text') or '').strip()[:500]
    if not text:
        return jsonify({'error': 'empty text'}), 400
    try:
        pet_id = int(data.get('petId', 1))
    except (TypeError, ValueError):
        pet_id = 1
    voice = (current_app.config.get('PET_TTS_VOICES') or {}).get(pet_id) \
        or current_app.config.get('PET_TTS_DEFAULT_VOICE', 'tongtong')
    try:
        import requests as _req
        session = _req.Session()
        session.trust_env = False   # bigmodel.cn 直连不走系统代理
        resp = session.post(
            f"{current_app.config['GLM_BASE_URL']}/audio/speech",
            headers={
                'Authorization': f"Bearer {current_app.config['GLM_API_KEY']}",
                'Content-Type': 'application/json',
            },
            json={
                'model': 'glm-tts',
                'input': text,
                'voice': voice,
                'response_format': 'wav',
                'speed': 0.9,
                'volume': 1.0,
            },
            timeout=20,
        )
        if resp.status_code != 200:
            current_app.logger.warning('GLM TTS failed [%s]: %s', resp.status_code, resp.text[:200])
            return jsonify({'error': f'tts failed: {resp.status_code}'}), 502
        return current_app.response_class(resp.content, mimetype='audio/wav',
                                          headers={'Cache-Control': 'public, max-age=3600'})
    except Exception as e:
        current_app.logger.warning('GLM TTS error: %s', e)
        return jsonify({'error': str(e)}), 502
