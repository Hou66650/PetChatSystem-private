from urllib.parse import urlsplit
from flask import Blueprint,request,jsonify,render_template
from ..services import cat_market_service as market,companion_service as companion,pet_generation_service as studio
bp=Blueprint('cat_market',__name__)
@bp.after_request
def no_cache(r):r.headers['Cache-Control']='no-store';return r
@bp.errorhandler(market.MarketError)
def error(e):return jsonify(error=str(e)),e.status
@bp.get('/cat-market')
def page():return render_template('cat-market.html',scope=companion.browser_scope())
@bp.get('/api/cat-market')
def state():return jsonify(**market.state(companion.owner_key()),scope=companion.browser_scope(),effectiveAppearance=studio.appearance(companion.owner_key()) or market.appearance(companion.owner_key()))
@bp.post('/api/cat-market/<operation>')
def operate(operation):
 origin=request.headers.get('Origin')
 if (origin and urlsplit(origin).netloc!=request.host) or request.headers.get('Sec-Fetch-Site')=='cross-site':raise market.MarketError('请从本站操作',403)
 if request.headers.get('X-Profile-Scope')!=companion.browser_scope():raise market.MarketError('账号已变化，请刷新',409)
 if not request.is_json or (request.content_length or 0)>2048:raise market.MarketError('请求格式错误')
 data=request.get_json(silent=True)
 if not isinstance(data,dict):raise market.MarketError('请求格式错误')
 return jsonify(**market.operate(companion.owner_key(),operation,data),scope=companion.browser_scope())
