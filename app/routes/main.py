# -*- coding: utf-8 -*-
"""主页与静态资源代理。

/images /js /css 三个代理路由保留自旧版：聊天页等模板以相对路径引用
templates/ 下的资产（templates/images、templates/css、templates/js），
Flask 默认静态目录是 static/，所以需要显式代理。
"""
from flask import Blueprint, redirect, render_template, send_from_directory, session, url_for

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
    books_p = [{
        'book_name': pet.get('name', pet['role']),
        'image_name': pet.get('avatar', 'c.png'),
        'rating': pet_display_rating(pet),
    } for pet in pets]
    top_pet = max(books_p, key=lambda p: p['rating']) if books_p else None
    return render_template('index1.html', books_p=books_p, top_pet=top_pet)


@bp.route('/about')
def about():
    return render_template('about_us.html')


@bp.route('/logout')
def logout():
    session.pop('user_id', None)
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
