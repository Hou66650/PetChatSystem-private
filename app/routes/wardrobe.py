from urllib.parse import urlsplit
from flask import Blueprint, jsonify, render_template, request
from ..services import wardrobe_service as wardrobe, companion_service as companion

bp = Blueprint('wardrobe', __name__)

@bp.after_request
def no_cache(response):
    response.headers['Cache-Control'] = 'private, no-store'
    return response

@bp.errorhandler(wardrobe.Error)
def error(exc):
    return jsonify(error=str(exc)), exc.status

@bp.get('/pet-shop')
def page():
    return render_template('pet-shop.html', scope=companion.browser_scope())

@bp.get('/api/wardrobe')
def state():
    pet = request.args.get('petId', '1')
    if pet not in ('1', '2', '3', '4'):
        raise wardrobe.Error('请选择有效宠物')
    return jsonify(**wardrobe.state(companion.owner_key(), int(pet)), scope=companion.browser_scope())

@bp.post('/api/wardrobe/<operation>')
def operate(operation):
    origin = request.headers.get('Origin')
    if (origin and urlsplit(origin).netloc != request.host) or request.headers.get('Sec-Fetch-Site') == 'cross-site':
        raise wardrobe.Error('请从本站操作', 403)
    if request.headers.get('X-Profile-Scope') != companion.browser_scope():
        raise wardrobe.Error('账号已变化，请刷新', 409)
    if not request.is_json or (request.content_length or 0) > 2048:
        raise wardrobe.Error('请求格式错误')
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise wardrobe.Error('请求格式错误')
    return jsonify(**wardrobe.operate(companion.owner_key(), operation, data), scope=companion.browser_scope())
