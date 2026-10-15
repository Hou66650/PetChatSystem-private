"""Account inventory and durable deliveries, sharing the cosmetic-market wallet."""
import json,re,time,uuid
from ..db import get_db
from . import cat_market_service as wallet
Error=wallet.MarketError
CATALOG=[
 dict(id='kibble',name='日常口粮',price=10,kind='food',icon='meal',description='猫狗各自的日常口粮，一份温暖的饱足。',effect='eat'),
 dict(id='dinner',name='精致餐盒',price=25,kind='food',icon='dinner',description='给今天的陪伴加一顿丰盛晚餐。',effect='eat'),
 dict(id='treat',name='宠物小零食',price=8,kind='food',icon='treat',description='一小份奖励，适合亲手喂给它。',effect='snack'),
 dict(id='water',name='清水补给',price=0,kind='water',icon='water',description='清水随时免费补充，不消耗代币。',effect='drink'),
 dict(id='star_ball',name='星光弹力球',price=60,kind='toy',icon='ball',description='薄荷与奶油色的新款球，沿用抛接、追逐和捡回。',effect='ball'),
 dict(id='cloud_bone',name='云朵毛绒骨头',price=80,kind='toy',icon='bone',description='柔软的丁香色玩具，猫狗都能嗅闻和寻回。',effect='bone')]
ITEMS={i['id']:i for i in CATALOG}
def init_schema():
 get_db().executescript('''
 CREATE TABLE IF NOT EXISTS supply_bowls(owner TEXT NOT NULL,pet TEXT NOT NULL,food INTEGER NOT NULL DEFAULT 100 CHECK(food BETWEEN 0 AND 100),water INTEGER NOT NULL DEFAULT 100 CHECK(water BETWEEN 0 AND 100),PRIMARY KEY(owner,pet));
 CREATE TABLE IF NOT EXISTS supply_inventory(owner TEXT NOT NULL,item TEXT NOT NULL,quantity INTEGER NOT NULL CHECK(quantity>=0),PRIMARY KEY(owner,item));
 CREATE TABLE IF NOT EXISTS supply_requests(owner TEXT NOT NULL,token TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(owner,token));
 CREATE TABLE IF NOT EXISTS supply_daily(owner TEXT NOT NULL,day TEXT NOT NULL,PRIMARY KEY(owner,day));
 CREATE TABLE IF NOT EXISTS supply_deliveries(id TEXT PRIMARY KEY,owner TEXT NOT NULL,pet TEXT NOT NULL,item TEXT NOT NULL,status TEXT NOT NULL,lease TEXT,expires REAL,created REAL NOT NULL,completed REAL);
 CREATE UNIQUE INDEX IF NOT EXISTS supply_one_pending ON supply_deliveries(owner,pet) WHERE status='pending';
 ''')
def state(owner):
 base=wallet.state(owner);db=get_db()
 return dict(balance=base['balance'],guest=base['guest'],catalog=CATALOG,
  bowls={r['pet']:dict(food=r['food'],water=r['water']) for r in db.execute('SELECT * FROM supply_bowls WHERE owner=?',(owner,))},
  inventory={r['item']:r['quantity'] for r in db.execute('SELECT * FROM supply_inventory WHERE owner=?',(owner,))},
  dailyClaimed=bool(db.execute('SELECT 1 FROM supply_daily WHERE owner=? AND day=?',(owner,wallet.day())).fetchone()),
  deliveries=[dict(r) for r in db.execute('SELECT id,pet,item,status,created,completed FROM supply_deliveries WHERE owner=? ORDER BY created DESC LIMIT 20',(owner,))])
def stock(db,owner,item,n):
 db.execute('INSERT INTO supply_inventory VALUES (?,?,?) ON CONFLICT(owner,item) DO UPDATE SET quantity=quantity+excluded.quantity',(owner,item,n))
def operate(owner,op,data):
 if not owner.startswith('user:'):raise Error('请登录后领取补给和使用库存',403)
 token=data.get('token')
 if not isinstance(token,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{8,80}',token):raise Error('缺少有效操作编号')
 payload=json.dumps([op,{k:v for k,v in data.items() if k!='token'}],sort_keys=True,ensure_ascii=False)
 db=get_db();db.execute('BEGIN IMMEDIATE')
 try:
  wallet.ensure(owner)
  old=db.execute('SELECT payload FROM supply_requests WHERE owner=? AND token=?',(owner,token)).fetchone()
  if old:
   if old['payload']!=payload:raise Error('操作编号已使用，请重新操作',409)
   db.commit();return state(owner)
  if op=='daily':
   if db.execute('INSERT OR IGNORE INTO supply_daily VALUES (?,?)',(owner,wallet.day())).rowcount:stock(db,owner,'kibble',3)
  elif op=='buy':
   item=ITEMS.get(data.get('item')) if isinstance(data.get('item'),str) else None
   n=data.get('quantity',1)
   if not item or item['kind']=='water':raise Error('请选择可购买的商品')
   if type(n)!=int or not 1<=n<=20:raise Error('购买数量应为 1–20')
   owned=db.execute('SELECT quantity FROM supply_inventory WHERE owner=? AND item=?',(owner,item['id'])).fetchone()
   if item['kind']=='toy':
    n=1
    if owned and owned[0]>0:raise Error('已经拥有这件永久玩具',409)
   price=item['price']*n
   if not db.execute('UPDATE cat_wallets SET balance=balance-? WHERE owner=? AND balance>=?',(price,owner,price)).rowcount:raise Error('代币不足，可以领取每日代币或参与探索')
   stock(db,owner,item['id'],n)
   db.execute('INSERT INTO cat_coin_ledger VALUES (?,?,?,?,?,?)',(owner,'supply:'+token,'supply_purchase',-price,wallet.day(),time.time()))
  elif op=='use':
   item=ITEMS.get(data.get('item')) if isinstance(data.get('item'),str) else None;pet=str(data.get('pet',''))
   if not item or pet not in ('1','2','3','4'):raise Error('请选择商品和宠物')
   if db.execute("SELECT 1 FROM portal_trips WHERE owner=? AND pet=? AND status IN ('pairing','active')",(owner,pet)).fetchone():raise Error('请先召回这只宠物，再送补给',409)
   if db.execute("SELECT 1 FROM supply_deliveries WHERE owner=? AND pet=? AND status='pending'",(owner,pet)).fetchone():raise Error('这只宠物还有一份待使用补给，请先回小岛使用或取消',409)
   if item['kind']!='water':
    if item['kind']=='food':
     if not db.execute('UPDATE supply_inventory SET quantity=quantity-1 WHERE owner=? AND item=? AND quantity>0',(owner,item['id'])).rowcount:raise Error('库存不足',409)
    elif not db.execute('SELECT 1 FROM supply_inventory WHERE owner=? AND item=? AND quantity>0',(owner,item['id'])).fetchone():raise Error('请先购买这件玩具',403)
   db.execute('INSERT INTO supply_deliveries(id,owner,pet,item,status,created) VALUES (?,?,?,?,?,?)',(uuid.uuid4().hex,owner,pet,item['id'],'pending',time.time()))
  elif op in ('bowl-refill','bowl-consume'):
   pet=str(data.get('pet',''));kind=data.get('kind')
   if pet!='3' or kind not in ('food','water'):raise Error('请选择猫咪岛上的食盆或水盆')
   db.execute('INSERT OR IGNORE INTO supply_bowls(owner,pet) VALUES (?,?)',(owner,pet))
   row=db.execute('SELECT * FROM supply_bowls WHERE owner=? AND pet=?',(owner,pet)).fetchone()
   if op=='bowl-refill':
    if row[kind]>=100:raise Error('盆已经满了，不需要补充',409)
    if kind=='food':
     if not db.execute("UPDATE supply_inventory SET quantity=quantity-1 WHERE owner=? AND item='kibble' AND quantity>0",(owner,)).rowcount:raise Error('口粮库存不足，请到补给站领取或购买',409)
    value=100 if kind=='water' else min(100,row[kind]+25)
   else:
    value=max(0,row[kind]-25)
   db.execute('UPDATE supply_bowls SET '+kind+'=? WHERE owner=? AND pet=?',(value,owner,pet))
  elif op=='cancel':
   row=db.execute("SELECT * FROM supply_deliveries WHERE owner=? AND id=? AND status='pending'",(owner,str(data.get('delivery','')))).fetchone()
   if not row:raise Error('补给不存在或已使用',404)
   if (row['expires'] or 0)>time.time():raise Error('宠物正在使用，请稍后再试',409)
   if ITEMS[row['item']]['kind']=='food':stock(db,owner,row['item'],1)
   db.execute("UPDATE supply_deliveries SET status='cancelled' WHERE id=?",(row['id'],))
  else:raise Error('操作不存在',404)
  db.execute('INSERT INTO supply_requests VALUES (?,?,?)',(owner,token,payload));db.commit()
 except Exception:db.rollback();raise
 return state(owner)
def delivery(owner,pet,client,complete=None):
 if not owner.startswith('user:'):raise Error('请登录',403)
 if str(pet) not in ('1','2','3','4') or not isinstance(client,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{8,80}',client):raise Error('请求格式错误')
 db=get_db();db.execute('BEGIN IMMEDIATE')
 try:
  if not complete and db.execute("SELECT 1 FROM portal_trips WHERE owner=? AND pet=? AND status IN ('active','pairing')",(owner,str(pet))).fetchone():
   db.commit();return None
  row=db.execute("SELECT * FROM supply_deliveries WHERE owner=? AND pet=? AND status='pending'",(owner,str(pet))).fetchone();result=None
  if row and complete:
   if row['id']!=complete or row['lease']!=client or (row['expires'] or 0)<time.time():raise Error('补给领取状态已改变',409)
   db.execute("UPDATE supply_deliveries SET status='completed',completed=? WHERE id=?",(time.time(),row['id']))
  elif row and ((row['expires'] or 0)<=time.time() or row['lease']==client):
   db.execute('UPDATE supply_deliveries SET lease=?,expires=? WHERE id=?',(client,time.time()+90,row['id']))
   result=dict(id=row['id'],pet=row['pet'],item=ITEMS[row['item']])
  db.commit();return result
 except Exception:db.rollback();raise
