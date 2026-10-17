# -*- coding: utf-8 -*-
"""主页与静态资源代理。

/images /js /css 三个代理路由保留自旧版：聊天页等模板以相对路径引用
templates/ 下的资产（templates/images、templates/css、templates/js），
Flask 默认静态目录是 static/，所以需要显式代理。
"""
from flask import Blueprint, abort, current_app, redirect, render_template, request, send_from_directory, session, url_for
from pathlib import Path

from ..config import Config
from ..db import query_db
from ..llm import pets as pet_registry

bp = Blueprint('main', __name__)


def pet_display_rating(pet):
    """宠物展示评分：优先取 reviews 表里的真实平均分，没有则用配置默认值。"""
    row = query_db(
        'SELECT AVG(rating) AS avg_rating, COUNT(*) AS cnt FROM reviews WHERE book_id = ?',
        [f"pet{pet['id']}"], one=True)
    if row and row['cnt']:
        return round(row['avg_rating'], 1)
    return pet.get('rating', 5.0)


@bp.route('/')
def index():
    pets = pet_registry.list_pets()
    cards = [{
        'id': pet['id'],
        'name': pet.get('name', pet['role']),
        'avatar': pet.get('avatar', 'c.png'),
        'rating': pet_display_rating(pet),
    } for pet in pets]
    top_pet = max(cards, key=lambda c: c['rating']) if cards else None
    from ..services import cat_market_service, companion_service, pet_generation_service
    owner = companion_service.owner_key()
    return render_template('index1.html', pets=cards, top_pet=top_pet, cat_model=(pet_generation_service.appearance(owner) or cat_market_service.appearance(owner))['model'])


@bp.route('/about')
def about():
    return render_template('about_us.html')


@bp.route('/static/models/home-islands/<theme>.glb')
def home_island_model(theme):
    """Lossless transfer compression keeps island geometry intact."""
    if theme not in ('sakura', 'snow', 'camp', 'room'):
        abort(404)
    directory = Path(current_app.static_folder) / 'models' / 'home-islands'
    compressed = request.accept_encodings['gzip'] > 0 and (directory / (theme + '.glb.gz')).is_file()
    filename = theme + ('.glb.gz' if compressed else '.glb')
    response = send_from_directory(directory, filename, mimetype='model/gltf-binary', max_age=3600)
    response.vary.add('Accept-Encoding')
    if compressed:
        response.headers['Content-Encoding'] = 'gzip'
    return response


@bp.route('/static/models/paw-commons-v2/preview.glb', defaults={'tier': 'preview'})
@bp.route('/static/models/paw-commons-v2/play.glb', defaults={'tier': 'play'})
def public_park_model(tier):
    if tier not in ('preview', 'play'):
        abort(404)
    directory = Path(current_app.static_folder) / 'models' / 'paw-commons-v2'
    compressed = request.accept_encodings['gzip'] > 0 and (directory / (tier + '.glb.gz')).is_file()
    response = send_from_directory(directory, tier + ('.glb.gz' if compressed else '.glb'), mimetype='model/gltf-binary', max_age=3600)
    response.vary.add('Accept-Encoding')
    if compressed:
        response.headers['Content-Encoding'] = 'gzip'
    return response


@bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('main.index'))


# ---------------------------------------------------------------------
# 静态资产代理（旧版兼容）
# ---------------------------------------------------------------------
@bp.route('/images/<path:filename>')
def serve_images(filename):
    return send_from_directory(f'{Config.TEMPLATES_DIR}/images', filename)


@bp.route('/js/<path:filename>')
def serve_js(filename):
    return send_from_directory(f'{Config.TEMPLATES_DIR}/js', filename)


@bp.route('/css/<path:filename>')
def serve_css(filename):
    return send_from_directory(f'{Config.TEMPLATES_DIR}/css', filename)


@bp.route('/media/avatars/<path:filename>')
def serve_avatars(filename):
    return send_from_directory(Config.AVATAR_DIR, filename)
