"""Owner-scoped growth profiles and virtual-scene memories."""
import base64
import html
import io
import json
import time
from urllib.parse import urlsplit
from flask import Blueprint, Response, jsonify, render_template, request
from PIL import Image, UnidentifiedImageError
from ..db import get_db
from ..services import companion_service as memory, growth_service as growth

bp=Blueprint('growth',__name__)

@bp.before_request
def guard():
    if request.method in ('POST','PATCH'):
        if request.content_length and request.content_length>500000:return jsonify(error='图片或请求过大'),413
        origin=request.headers.get('Origin')
        if (origin and urlsplit(origin).netloc!=request.host) or request.headers.get('Sec-Fetch-Site')=='cross-site':return jsonify(error='请在本站操作'),403
        if not request.is_json:return jsonify(error='请使用 JSON 请求'),415
        if request.headers.get('X-Profile-Scope')!=memory.browser_scope():return jsonify(error='账号已变化，请刷新'),409

@bp.errorhandler(ValueError)
def bad(error):return jsonify(error=str(error)),400

def identity(pet):
    if pet not in (1,2,3,4):raise ValueError('请选择有效宠物')
    return memory.owner_key()

@bp.get('/growth')
def page():return render_template('growth.html')

@bp.route('/api/growth/<int:pet>',methods=['GET','POST','PATCH'])
def profile(pet):
    owner=identity(pet)
    d=growth.state(owner,pet,20 if request.args.get('runtime')=='1' else 300) if request.method=='GET' else growth.save(owner,pet,request.get_json(silent=True),request.method=='PATCH')
    return jsonify(**d,scope=memory.browser_scope()),200,{'Cache-Control':'private, no-store'}

@bp.patch('/api/growth/<int:pet>/preferences')
def preferences(pet):
    prefs=growth.update_prefs(identity(pet),pet,request.get_json(silent=True))
    return jsonify(prefs=prefs,scope=memory.browser_scope())

@bp.post('/api/growth/<int:pet>/memories/<int:event>/photo')
def photo(pet,event):
    owner=identity(pet);db=get_db();p=growth.get(db,owner,pet)
    row=db.execute('SELECT created,photo FROM pet_growth_memories WHERE owner=? AND pet=? AND id=?',(owner,pet,event)).fetchone()
    if not row:return jsonify(error='回忆不存在'),404
    if not p or not growth.enabled(db,owner) or not json.loads(p['prefs'])['autoPhoto']:return jsonify(error='已关闭自动相册'),409
    if row['photo'] is not None:return jsonify(ok=True)
    if not 0<=time.time()-row['created']<180:return jsonify(error='不以当前画面补拍过去的回忆'),409
    data=request.get_json(silent=True)
    if not isinstance(data,dict) or not isinstance(data.get('image'),str):raise ValueError('图片格式不正确')
    try:
        raw=base64.b64decode(data['image'],validate=True)
        if len(raw)>300000:raise ValueError('图片过大')
        with Image.open(io.BytesIO(raw)) as im:
            if im.width>1280 or im.height>1280 or im.width*im.height>1000000:raise ValueError('图片尺寸过大')
            im.load();im=im.convert('RGB');im.thumbnail((600,400));out=io.BytesIO();im.save(out,'JPEG',quality=80)
    except (UnidentifiedImageError,OSError,Image.DecompressionBombError):raise ValueError('无法读取场景照片')
    with db:
        db.execute('BEGIN IMMEDIATE');p=growth.get(db,owner,pet)
        if not p or not growth.enabled(db,owner) or not json.loads(p['prefs'])['autoPhoto']:return jsonify(error='设置已变化'),409
        db.execute('UPDATE pet_growth_memories SET photo=? WHERE owner=? AND pet=? AND id=? AND photo IS NULL',(out.getvalue(),owner,pet,event))
    return jsonify(ok=True)

@bp.get('/api/growth/<int:pet>/memories/<int:event>/image')
def image(pet,event):
    owner=identity(pet)
    row=get_db().execute('SELECT * FROM pet_growth_memories WHERE owner=? AND pet=? AND id=?',(owner,pet,event)).fetchone()
    if not row:return jsonify(error='回忆不存在'),404
    headers={'Cache-Control':'private, no-store','X-Profile-Scope':memory.browser_scope(),'X-Content-Type-Options':'nosniff'}
    if row['photo']:return Response(row['photo'],mimetype='image/jpeg',headers=headers)
    title=html.escape(row['title']);day=html.escape(row['day'])
    svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400" viewBox="0 0 600 400"><rect width="600" height="400" rx="24" fill="#f3eee2"/><circle cx="300" cy="140" r="62" fill="#adc4b6"/><text x="300" y="158" text-anchor="middle" font-size="48" fill="#31584c">{('犬' if pet!=3 else '猫')}</text><text x="300" y="255" text-anchor="middle" font-family="sans-serif" font-size="24" fill="#32483e">{title}</text><text x="300" y="300" text-anchor="middle" font-family="sans-serif" font-size="18" fill="#647569">{day} · 成长纪念卡</text></svg>'''
    return Response(svg,mimetype='image/svg+xml',headers=headers)
