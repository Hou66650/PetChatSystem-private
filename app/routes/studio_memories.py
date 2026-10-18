"""Memory endpoints share studio authentication, scope checks and upload limits."""
import io
from flask import jsonify, request, send_file
from .pet_studio import bp
from ..db import get_db
from ..services import studio_memory_service as service
from ..services import pet_habit_service as habits


@bp.errorhandler(service.Error)
def memory_invalid(error):
    return jsonify(error=str(error)), error.status


@bp.route('/api/pet-studio/<task>/memories', methods=['GET','POST'])
def memory_library(task):
    return jsonify(service.state(task) if request.method=='GET' else service.upload(task,request.files.get('file')))


@bp.get('/api/pet-studio/<task>/memories/<media>/<view>')
def memory_asset(task,media,view):
    row=service.media_row(task,media)
    if view not in ('preview','source'): raise service.Error('素材不存在',404)
    return send_file(io.BytesIO(row['preview'] if view=='preview' else row['data']),
                     mimetype='image/jpeg' if view=='preview' else row['mime'],conditional=True)


@bp.post('/api/pet-studio/<task>/memories/<media>/analyze')
def memory_analyze(task,media):
    data=request.get_json(silent=True)
    if not isinstance(data,dict): raise service.Error('请求格式错误')
    return jsonify(service.analyze(task,media,data))


@bp.post('/api/pet-studio/<task>/memories/<media>/delete')
def memory_delete(task,media):
    db=get_db()
    with db:
        db.execute('BEGIN IMMEDIATE'); service.media_row(task,media)
        service.clear(task,media)
    return jsonify(service.state(task))


@bp.post('/api/pet-studio/<task>/memory-cards/<card>/<operation>')
def memory_change(task,card,operation):
    data=request.get_json(silent=True)
    if not isinstance(data,dict): raise service.Error('请求格式错误')
    return jsonify(service.card_change(task,card,data,operation))


def habit_data():
    data=request.get_json(silent=True)
    if not isinstance(data,dict) or (request.content_length or 0)>16000:
        raise service.Error('请提交不超过16KB的JSON')
    return data


@bp.post('/api/pet-studio/<task>/habits/<media>/analyze')
def habit_analyze(task,media):
    return jsonify(habits.analyze(task,media,habit_data()))


@bp.post('/api/pet-studio/<task>/habit-events/<event>/review')
def habit_review(task,event):
    return jsonify(habits.review(task,event,habit_data()))


@bp.post('/api/pet-studio/<task>/habit-rules')
def habit_apply(task):
    return jsonify(habits.apply(task,habit_data()))
