"""Cosmetic ownership and a non-purchasable, account-scoped coin ledger."""
from datetime import datetime, timezone, timedelta
import time
from ..db import get_db

BASE='/static/models/petchat-cat-coats-v1/'
CATALOG=[
 dict(id='tabby',name='雾林狸花',price=0,model='/static/models/petchat-cat-v3/cat.glb',description='原有狸花伙伴，细密虎纹与温柔的眼睛。',color='#958875'),
 dict(id='ginger',name='暖阳橘猫',price=120,model=BASE+'ginger.glb',description='暖橘虎纹、奶油色口鼻，像一小团阳光。',color='#d79b54'),
 dict(id='tuxedo',name='云朵奶牛',price=180,model=BASE+'tuxedo.glb',description='黑白花斑、白胸口和白袜，短毛清爽。',color='#637374'),
 dict(id='calico',name='秋日三花',price=220,model=BASE+'calico.glb',description='奶白底色上散落橘与墨色的不规则花斑。',color='#b5845f'),
 dict(id='ragdoll',name='月光布偶',price=300,model=BASE+'ragdoll.glb',description='布偶风格：奶油长毛、深色重点色面罩与丰盈颊毛。',color='#a6baca')]
ITEMS={x['id']:x for x in CATALOG}
class MarketError(ValueError):
 def __init__(self,message,status=400):super().__init__(message);self.status=status

def init_schema():
 get_db().executescript("""
 CREATE TABLE IF NOT EXISTS cat_wallets(owner TEXT PRIMARY KEY,balance INTEGER NOT NULL CHECK(balance>=0),active TEXT NOT NULL DEFAULT 'tabby');
 CREATE TABLE IF NOT EXISTS cat_owned(owner TEXT NOT NULL,coat TEXT NOT NULL,created REAL NOT NULL,PRIMARY KEY(owner,coat));
 CREATE TABLE IF NOT EXISTS cat_coin_ledger(owner TEXT NOT NULL,event TEXT NOT NULL,kind TEXT NOT NULL,amount INTEGER NOT NULL,day TEXT NOT NULL,created REAL NOT NULL,PRIMARY KEY(owner,event));
 """)
def day():return datetime.now(timezone(timedelta(hours=8))).date().isoformat()
def ensure(owner):
 db=get_db()
 if not owner.startswith('user:'):return
 if db.execute("INSERT OR IGNORE INTO cat_wallets(owner,balance) VALUES (?,160)",(owner,)).rowcount:
  db.execute('INSERT INTO cat_coin_ledger VALUES (?,?,?,?,?,?)',(owner,'welcome','welcome',160,day(),time.time()))
  db.execute('INSERT INTO cat_owned VALUES (?,?,?)',(owner,'tabby',time.time()))
def reward(owner,kind,event):
 # Called inside the existing successful action's transaction; never commits it.
 if not owner.startswith('user:'):return
 limits={'explore':(5,5),'journey':(10,3),'daily':(30,1)}
 if kind not in limits:return
 db=get_db();ensure(owner);amount,cap=limits[kind];today=day()
 if db.execute('SELECT count(*) FROM cat_coin_ledger WHERE owner=? AND kind=? AND day=?',(owner,kind,today)).fetchone()[0]>=cap:return
 if db.execute('INSERT OR IGNORE INTO cat_coin_ledger VALUES (?,?,?,?,?,?)',(owner,kind+':'+event,kind,amount,today,time.time())).rowcount:
  db.execute('UPDATE cat_wallets SET balance=balance+? WHERE owner=?',(amount,owner))
def appearance(owner):
 r=get_db().execute('SELECT active FROM cat_wallets WHERE owner=?',(owner,)).fetchone()
 return dict(ITEMS.get(r['active'] if r else 'tabby',ITEMS['tabby']))
def state(owner):
 db=get_db()
 with db:ensure(owner)
 wallet=db.execute('SELECT balance,active FROM cat_wallets WHERE owner=?',(owner,)).fetchone()
 owned=[r['coat'] for r in db.execute('SELECT coat FROM cat_owned WHERE owner=?',(owner,))] if wallet else ['tabby']
 return dict(catalog=CATALOG,balance=wallet['balance'] if wallet else 0,active=wallet['active'] if wallet else 'tabby',owned=owned,guest=not owner.startswith('user:'),dailyClaimed=bool(db.execute("SELECT 1 FROM cat_coin_ledger WHERE owner=? AND event=?",(owner,'daily:'+day())).fetchone()),ledger=[dict(r) for r in db.execute('SELECT kind,amount,created FROM cat_coin_ledger WHERE owner=? ORDER BY created DESC LIMIT 20',(owner,))])
def operate(owner,op,data):
 if not owner.startswith('user:'):raise MarketError('请登录后领取代币、购买和启用外观',403)
 db=get_db();db.execute('BEGIN IMMEDIATE')
 try:
  ensure(owner)
  if op=='daily':reward(owner,'daily',day())
  elif op in ('buy','equip'):
   coat=data.get('coat')
   if not isinstance(coat,str) or coat not in ITEMS:raise MarketError('外观不存在',404)
   owned=db.execute('SELECT 1 FROM cat_owned WHERE owner=? AND coat=?',(owner,coat)).fetchone()
   if op=='buy' and not owned:
    price=ITEMS[coat]['price']
    if not db.execute('UPDATE cat_wallets SET balance=balance-? WHERE owner=? AND balance>=?',(price,owner,price)).rowcount:raise MarketError('代币不足，探索和串门可以获得奖励')
    db.execute('INSERT INTO cat_owned VALUES (?,?,?)',(owner,coat,time.time()))
    db.execute('INSERT INTO cat_coin_ledger VALUES (?,?,?,?,?,?)',(owner,'purchase:'+coat,'purchase',-price,day(),time.time()))
   elif op=='equip':
    if not owned:raise MarketError('请先解锁这个外观',403)
    from .wardrobe_service import check_available
    check_available(owner,3)
    db.execute('UPDATE cat_wallets SET active=? WHERE owner=?',(coat,owner))
    db.execute('DELETE FROM pet_studio_equipped WHERE owner=?',(owner,))
  else:raise MarketError('操作不存在',404)
  db.commit()
 except Exception:db.rollback();raise
 return state(owner)
