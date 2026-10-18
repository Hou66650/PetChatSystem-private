from urllib.parse import urlsplit
from flask import Blueprint, jsonify, render_template, request, Response, redirect, url_for
from ..services import companion_service as memory, pet_imprint_service as imprint

bp = Blueprint('pet_imprint', __name__)


@bp.before_request
def guard():
    if request.method != 'GET':
        origin = request.headers.get('Origin')
        if (origin and urlsplit(origin).netloc != request.host) or request.headers.get('Sec-Fetch-Site') == 'cross-site':
            return jsonify(error='请在本站操作'), 403
        if not request.is_json or (request.content_length or 0) > 10000:
            return jsonify(error='请提交不超过 10KB 的 JSON'), 400
        if not memory.owner_key().startswith('user:'):
            return jsonify(error='请登录后保存宠物的真实回忆'), 403
        if request.headers.get('X-Profile-Scope') != memory.browser_scope():
            return jsonify(error='账号已变化，请刷新页面'), 409


@bp.after_request
def private(response):
    response.headers['Cache-Control'] = 'private, no-store'
    response.headers['X-Profile-Scope'] = memory.browser_scope()
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


@bp.errorhandler(imprint.ImprintError)
def invalid(error):
    return jsonify(error=str(error)), error.status


def owner(pet):
    if pet not in (1, 2, 3, 4):
        raise imprint.ImprintError('请选择有效宠物')
    return memory.owner_key()


@bp.get('/pet-imprint')
def page():
    if request.args.get('embedded') != '1':
        pet=request.args.get('petId',default=1,type=int)
        return redirect(url_for('pet_studio.page',section='memories',petId=pet if pet in (1,2,3,4) else 1))
    return render_template('pet-imprint.html', embedded=True)


@bp.route('/api/pet-imprint/<int:pet>', methods=['GET', 'POST'])
def cards(pet):
    who = owner(pet)
    return jsonify(imprint.state(who, pet) if request.method == 'GET' else imprint.mutate(who, pet, request.get_json(silent=True)))


@bp.route('/api/pet-imprint/<int:pet>/<card_id>', methods=['PATCH', 'DELETE'])
def card(pet, card_id):
    return jsonify(imprint.mutate(owner(pet), pet, request.get_json(silent=True), card_id,
                                 'delete' if request.method == 'DELETE' else 'edit'))


@bp.post('/api/pet-imprint/<int:pet>/<card_id>/<operation>')
def change(pet, card_id, operation):
    if operation not in ('confirm', 'withdraw'):
        raise imprint.ImprintError('操作不支持')
    return jsonify(imprint.mutate(owner(pet), pet, request.get_json(silent=True), card_id, operation))


@bp.get('/api/pet-imprint/<int:pet>/call/<kind>')
def audio(pet, kind):
    who = owner(pet)
    return Response(imprint.call_audio(who, pet, kind, request.args.get('revision', type=int)), mimetype='audio/wav')
