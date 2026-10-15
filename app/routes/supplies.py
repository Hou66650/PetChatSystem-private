from urllib.parse import urlsplit
from flask import Blueprint,request,jsonify,render_template
from ..services import supply_service as supplies,companion_service as companion
bp=Blueprint('supplies',__name__)
@bp.after_request
def no_cache(r):r.headers['Cache-Control']='no-store';return r
@bp.errorhandler(supplies.Error)
def error(e):return jsonify(error=str(e)),e.status
@bp.get('/supplies')
def page():return render_template('supplies.html',scope=companion.browser_scope())
@bp.get('/api/supplies')
def state():return jsonify(**supplies.state(companion.owner_key()),scope=companion.browser_scope())
@bp.post('/api/supplies/<op>')
def operate(op):
 origin=request.headers.get('Origin')
 if (origin and urlsplit(origin).netloc!=request.host) or request.headers.get('Sec-Fetch-Site')=='cross-site':raise supplies.Error('请从本站操作',403)
 if request.headers.get('X-Profile-Scope')!=companion.browser_scope():raise supplies.Error('账号已变化，请刷新',409)
 if not request.is_json or (request.content_length or 0)>2048:raise supplies.Error('请求格式错误')
 data=request.get_json(silent=True)
 if not isinstance(data,dict):raise supplies.Error('请求格式错误')
 if op in ('claim','complete'):
  if op=='complete' and (not isinstance(data.get('delivery'),str) or not data['delivery']):raise supplies.Error('缺少补给编号')
  return jsonify(delivery=supplies.delivery(companion.owner_key(),data.get('pet'),data.get('client'),data.get('delivery') if op=='complete' else None),scope=companion.browser_scope())
 return jsonify(**supplies.operate(companion.owner_key(),op,data),scope=companion.browser_scope())
