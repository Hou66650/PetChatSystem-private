"""Durable, account-scoped garden. Growth uses server time and never withers offline."""
import json, re, time, uuid, secrets
from pathlib import Path
from ..db import get_db
from . import cat_market_service as wallet, supply_service as supplies
from . import farm_placement_service as placement

Error = wallet.MarketError
LAYOUT = json.loads((Path(__file__).resolve().parents[2]/'static/data/farm-layout.json').read_text())
BEDS = {p['id']:p for p in LAYOUT['beds']}
SLOTS = {p['id']:p for p in LAYOUT['placements']}
CATALOG = [
    dict(id='cosmos', name='波斯菊', kind='flower', price=8, hours=18,
         stages=['子叶展开','初生细裂叶','第二对真叶','叶丛展开','主茎拔节','侧枝舒展','花苞初生','花苞饱满','初花绽放','盛花可装盆']),
    dict(id='pumpkin', name='小南瓜', kind='food', price=10, hours=24,
         stages=['子叶展开','第一片真叶','幼叶舒展','叶柄伸长','蔓茎生长','分蔓展叶','花蕾形成','黄花绽放','青果膨大','橙果成熟']),
    dict(id='birch', name='白桦', kind='tree', price=12, hours=36,
         stages=['子叶展开','锯齿真叶','幼苗舒展','茎节伸长','顶芽生长','初始分枝','木质化','侧枝展叶','树冠形成','可移栽幼树'])]
FLOWERS=json.loads((Path(__file__).resolve().parents[2]/'static/data/farm-flowers.json').read_text(encoding='utf-8'))
for flower in FLOWERS:
    base=dict(id=flower['id'],name=flower['name'],kind='flower',price=flower['price'],hours=flower['hours'],stages=flower['stages'],mutationChance=flower['mutationChance'])
    CATALOG.append(base)
    CATALOG.append(dict(**{**base,'id':base['id']+'-dream','name':flower['variantName']},variantOf=base['id'],mutationChanceLabel='成熟时 10% 概率出现，结果永久保留'))
SPECIES = {p['id']:p for p in CATALOG}
SHOP = [dict(id='seed:'+p['id'],name=p['name']+'种子',price=p['price']) for p in CATALOG if not p.get('variantOf')]+[dict(id='pot',name='手作陶土花盆',price=15)]
SHOP.append(dict(id='fertilizer',name='缓释园艺肥',price=3))

def bed_name(key):
    return ('育苗床' if BEDS[key].get('nursery') else '种植床')+key.split('-')[1]


def init_schema():
    get_db().executescript('''
    CREATE TABLE IF NOT EXISTS farm_accounts(owner TEXT PRIMARY KEY,created REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS farm_stock(owner TEXT NOT NULL,item TEXT NOT NULL,quantity INTEGER NOT NULL CHECK(quantity>=0),PRIMARY KEY(owner,item));
    CREATE TABLE IF NOT EXISTS farm_plants(owner TEXT NOT NULL,bed TEXT NOT NULL,id TEXT NOT NULL,species TEXT NOT NULL,planted REAL NOT NULL,bonus REAL NOT NULL DEFAULT 0,water_day TEXT NOT NULL DEFAULT '',PRIMARY KEY(owner,bed));
    CREATE TABLE IF NOT EXISTS farm_decor(owner TEXT NOT NULL,slot TEXT NOT NULL,species TEXT NOT NULL,created REAL NOT NULL,PRIMARY KEY(owner,slot));
    CREATE TABLE IF NOT EXISTS farm_requests(owner TEXT NOT NULL,token TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(owner,token));
    CREATE TABLE IF NOT EXISTS farm_events(id INTEGER PRIMARY KEY AUTOINCREMENT,owner TEXT NOT NULL,created REAL NOT NULL,kind TEXT NOT NULL,summary TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS farm_events_owner ON farm_events(owner,id);
    CREATE TABLE IF NOT EXISTS farm_arrangements(owner TEXT NOT NULL,id TEXT NOT NULL,species TEXT NOT NULL,container TEXT NOT NULL,x REAL NOT NULL,z REAL NOT NULL,yaw REAL NOT NULL,revision INTEGER NOT NULL DEFAULT 1,created REAL NOT NULL,PRIMARY KEY(owner,id));
    ''')
    db=get_db()
    if 'fertilizer_day' not in [r['name'] for r in db.execute('PRAGMA table_info(farm_plants)')]:
        db.execute("ALTER TABLE farm_plants ADD COLUMN fertilizer_day TEXT NOT NULL DEFAULT ''")
    if 'bloom_resolved' not in [r['name'] for r in db.execute('PRAGMA table_info(farm_plants)')]:
        db.execute("ALTER TABLE farm_plants ADD COLUMN bloom_resolved INTEGER NOT NULL DEFAULT 0")
    # NULL planted marks existing mature decorations; never regress legacy plants.
    columns={r['name'] for r in db.execute('PRAGMA table_info(farm_arrangements)')}
    for name,definition in [('planted','REAL'),('bonus','REAL NOT NULL DEFAULT 0'),('water_day',"TEXT NOT NULL DEFAULT ''"),('fertilizer_day',"TEXT NOT NULL DEFAULT ''"),('bloom_resolved','INTEGER NOT NULL DEFAULT 1')]:
        if name not in columns:db.execute('ALTER TABLE farm_arrangements ADD COLUMN '+name+' '+definition)
    db.commit()

def stock(db,owner,item,n):
    if n<0:
        if not db.execute('UPDATE farm_stock SET quantity=quantity+? WHERE owner=? AND item=? AND quantity>=?',(n,owner,item,-n)).rowcount:
            raise Error('库存不足，请先收获或购买',409)
    else:
        db.execute('INSERT INTO farm_stock VALUES (?,?,?) ON CONFLICT(owner,item) DO UPDATE SET quantity=quantity+excluded.quantity',(owner,item,n))

def growth(row,now):
    duration=SPECIES[row['species']]['hours']*3600
    rate=.25 if 'container' in row.keys() else 1
    age=duration if row['planted'] is None else max(0,now-row['planted'])*rate+row['bonus'];progress=max(0,min(1,age/duration))
    # Stage 10 always means harvestable; no confusing near-mature harvest button.
    stage=10 if progress>=1 else 1+min(8,int(progress*9))
    return dict(stage=stage,progress=progress,remaining=max(0,duration-age)/rate,ready=progress>=1,growthRate=rate)

def resolve_blooms(db,owner):
    # One atomic maturity roll per plant. All consumers use the persisted cultivar.
    own=not db.in_transaction
    if own:db.execute('BEGIN IMMEDIATE')
    try:
        for table in ('farm_plants','farm_arrangements'):
            for row in db.execute('SELECT * FROM '+table+' WHERE owner=? AND bloom_resolved=0',(owner,)).fetchall():
                spec=SPECIES[row['species']]
                if not growth(row,time.time())['ready']:continue
                variant=row['species']+'-dream' if spec.get('mutationChance') and not spec.get('variantOf') and secrets.randbelow(10)==0 else row['species']
                db.execute('UPDATE '+table+' SET species=?,bloom_resolved=1 WHERE owner=? AND id=?',(variant,owner,row['id']))
                if variant!=row['species']:
                    location=bed_name(row['bed']) if table=='farm_plants' else '岛上移栽'
                    db.execute('INSERT INTO farm_events(owner,created,kind,summary) VALUES (?,?,?,?)',(owner,time.time(),'mutation',location+'的'+spec['name']+'成熟时变异为'+SPECIES[variant]['name']))
        if own:db.commit()
    except Exception:
        if own:db.rollback()
        raise


def state(owner):
    db=get_db();base=wallet.state(owner);resolve_blooms(db,owner);now=time.time()
    rows={r['bed']:r for r in db.execute('SELECT * FROM farm_plants WHERE owner=?',(owner,))}
    beds=[]
    for key,bed in BEDS.items():
        r=rows.get(key);beds.append(dict(**bed,plant=dict(id=r['id'],species=r['species'],watered=r['water_day']==wallet.day(),fertilized=r['fertilizer_day']==wallet.day(),**growth(r,now)) if r else None))
    return dict(guest=base['guest'],started=bool(db.execute('SELECT 1 FROM farm_accounts WHERE owner=?',(owner,)).fetchone()),
                balance=base['balance'],catalog=CATALOG,shop=SHOP,beds=beds,serverTime=now,
                inventory={r['item']:r['quantity'] for r in db.execute('SELECT * FROM farm_stock WHERE owner=?',(owner,))},
                decorations=[dict(r) for r in db.execute('SELECT slot,species,created FROM farm_decor WHERE owner=?',(owner,))],placements=list(SLOTS.values()),
                arrangements=arrangements(db,owner),placementMap=placement.MAP,
                recentRequests=[r['token'] for r in db.execute('SELECT token FROM farm_requests WHERE owner=? ORDER BY rowid DESC LIMIT 20',(owner,))])


def arrangements(db,owner):
    now=time.time()
    return [dict(**{k:r[k] for k in ('id','species','container','x','z','yaw','revision','created')},**growth(r,now),watered=r['water_day']==wallet.day(),fertilized=r['fertilizer_day']==wallet.day()) for r in db.execute('SELECT * FROM farm_arrangements WHERE owner=? ORDER BY created,id',(owner,))]

def operate(owner,op,data):
    if not owner.startswith('user:'):raise Error('请登录后保存你的花园',403)
    token=data.get('token')
    if not isinstance(token,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{8,80}',token):raise Error('缺少有效操作编号')
    payload=json.dumps([op,{k:v for k,v in data.items() if k!='token'}],sort_keys=True,ensure_ascii=False)
    db=get_db();resolve_blooms(db,owner);db.execute('BEGIN IMMEDIATE')
    try:
        wallet.ensure(owner)
        old=db.execute('SELECT payload FROM farm_requests WHERE owner=? AND token=?',(owner,token)).fetchone()
        if old:
            if old['payload']!=payload:raise Error('操作编号已使用，请刷新后重试',409)
            db.commit();return state(owner)
        event_text=None
        if op=='start':
            if db.execute('INSERT OR IGNORE INTO farm_accounts VALUES (?,?)',(owner,time.time())).rowcount:
                for p in CATALOG:
                    if not p.get('variantOf'):stock(db,owner,'seed:'+p['id'],2)
                stock(db,owner,'pot',1)
                stock(db,owner,'fertilizer',3)
        elif not db.execute('SELECT 1 FROM farm_accounts WHERE owner=?',(owner,)).fetchone():raise Error('请先领取园艺入门礼',409)
        elif op=='buy':
            item=next((p for p in SHOP if p['id']==data.get('item')),None);n=data.get('quantity',1)
            if not item or type(n)!=int or not 1<=n<=20:raise Error('请选择商品和 1–20 的数量')
            price=item['price']*n
            if not db.execute('UPDATE cat_wallets SET balance=balance-? WHERE owner=? AND balance>=?',(price,owner,price)).rowcount:raise Error('代币不足',409)
            stock(db,owner,item['id'],n)
            db.execute('INSERT INTO cat_coin_ledger VALUES (?,?,?,?,?,?)',(owner,'farm:'+token,'garden_purchase',-price,wallet.day(),time.time()))
        elif op=='plant':
            bed=BEDS.get(data.get('bed')) if isinstance(data.get('bed'),str) else None
            p=SPECIES.get(data.get('species')) if isinstance(data.get('species'),str) else None
            if not bed or not p or p.get('variantOf'):raise Error('请选择种植床与可播种植物')
            if bool(bed.get('nursery'))!=(p['kind']=='tree'):raise Error('树苗请种在育苗床，花卉与作物种在种植床')
            if db.execute('SELECT 1 FROM farm_plants WHERE owner=? AND bed=?',(owner,bed['id'])).fetchone():raise Error('这块种植床已经有植物了',409)
            stock(db,owner,'seed:'+p['id'],-1)
            db.execute('INSERT INTO farm_plants(owner,bed,id,species,planted) VALUES (?,?,?,?,?)',(owner,bed['id'],uuid.uuid4().hex,p['id'],time.time()))
            event_text='主人在'+bed_name(bed['id'])+'种下了'+p['name']
        elif op in ('water','fertilize') and data.get('id'):
            row=db.execute('SELECT * FROM farm_arrangements WHERE owner=? AND id=?',(owner,str(data['id']))).fetchone()
            if not row or type(data.get('revision'))!=int or data['revision']!=row['revision']:raise Error('植物已变化，请刷新后重试',409)
            if growth(row,time.time())['ready']:raise Error('植物已成熟，不需要继续加速生长',409)
            column='water_day' if op=='water' else 'fertilizer_day'
            if row[column]==wallet.day():raise Error('今天已照料过了，不需要重复添加',409)
            if op=='fertilize':stock(db,owner,'fertilizer',-1)
            bonus=SPECIES[row['species']]['hours']*3600*(.08 if op=='water' else .06)
            db.execute('UPDATE farm_arrangements SET bonus=bonus+?,'+column+'=?,revision=revision+1 WHERE owner=? AND id=?',(bonus,wallet.day(),owner,row['id']))
            event_text='主人给岛上的'+SPECIES[row['species']]['name']+('浇了水' if op=='water' else '施了肥')
        elif op in ('water','fertilize','harvest'):
            if not isinstance(data.get('bed'),str) or not isinstance(data.get('plant'),str):raise Error('缺少植物编号')
            row=db.execute('SELECT * FROM farm_plants WHERE owner=? AND bed=? AND id=?',(owner,data['bed'],data['plant'])).fetchone()
            if not row:raise Error('植物已变化，请刷新花园',409)
            g=growth(row,time.time());p=SPECIES[row['species']]
            if op=='fertilize':
                if row['fertilizer_day']==wallet.day():raise Error('今天已施肥，不需要重复添加',409)
                if g['ready']:raise Error('已经成熟，不需要继续施肥',409)
                stock(db,owner,'fertilizer',-1)
                db.execute('UPDATE farm_plants SET bonus=bonus+?,fertilizer_day=? WHERE owner=? AND bed=?',(p['hours']*3600*.06,wallet.day(),owner,row['bed']))
                event_text='主人给'+bed_name(row['bed'])+'的'+p['name']+'施了肥'
            elif op=='water':
                if row['water_day']==wallet.day():raise Error('今天已浇过水了',409)
                if g['ready']:raise Error('已经成熟，可以收获了',409)
                db.execute('UPDATE farm_plants SET bonus=bonus+?,water_day=? WHERE owner=? AND bed=?',(p['hours']*3600*.08,wallet.day(),owner,row['bed']))
                event_text='主人给'+bed_name(row['bed'])+'的'+p['name']+'浇了水'
            else:
                if not g['ready']:raise Error('还在生长，成熟后再来收获',409)
                stock(db,owner,p['id'],2 if p['kind']=='food' else 1)
                db.execute('DELETE FROM farm_plants WHERE owner=? AND bed=?',(owner,row['bed']))
                event_text='主人收获了'+bed_name(row['bed'])+'的'+p['name']
        elif op=='arrange':
            previous=None;source=None
            if data.get('id'):
                previous=db.execute('SELECT * FROM farm_arrangements WHERE owner=? AND id=?',(owner,str(data['id']))).fetchone()
                if not previous or type(data.get('revision'))!=int or previous['revision']!=data['revision']:raise Error('这株植物已被移动，请刷新后重试',409)
                species=previous['species'];container=previous['container']
            elif data.get('bed'):
                source=db.execute('SELECT * FROM farm_plants WHERE owner=? AND bed=? AND id=?',(owner,str(data['bed']),str(data.get('plant','')))).fetchone()
                if not source:raise Error('植物已变化，请重新选择种植床里的植物',409)
                species=source['species'];container=data.get('container')
            else:species=data.get('species');container=data.get('container')
            point=dict(species=species,container=container,x=data.get('x'),z=data.get('z'),yaw=data.get('yaw',0))
            existing=arrangements(db,owner)
            problem=placement.validate(point,existing,previous['id'] if previous else None)
            if problem:raise Error(problem,409)
            if not previous and len(existing)>=80:raise Error('岛上已有 80 株装饰植物，请先移动或收回一些',409)
            if previous:
                db.execute('UPDATE farm_arrangements SET x=?,z=?,yaw=?,revision=revision+1 WHERE owner=? AND id=?',(point['x'],point['z'],point['yaw']%6.28318530718,owner,previous['id']))
                event_text='主人移动了岛上的'+SPECIES[species]['name']
            else:
                if source:db.execute('DELETE FROM farm_plants WHERE owner=? AND bed=?',(owner,source['bed']))
                else:stock(db,owner,species,-1)
                if container=='pot':stock(db,owner,'pot',-1)
                now=time.time();age=growth(source,now)['progress']*SPECIES[species]['hours']*3600 if source else 0
                db.execute('INSERT INTO farm_arrangements(owner,id,species,container,x,z,yaw,revision,created,planted,bonus,water_day,fertilizer_day,bloom_resolved) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(owner,uuid.uuid4().hex,species,container,point['x'],point['z'],point['yaw']%6.28318530718,1,now,now if source else None,age,source['water_day'] if source else '',source['fertilizer_day'] if source else '',source['bloom_resolved'] if source else 1))
                event_text='主人把'+SPECIES[species]['name']+('连盆摆放在岛上' if container=='pot' else '栽进岛屿土壤')
        elif op=='recover-arrangement':
            row=db.execute('SELECT * FROM farm_arrangements WHERE owner=? AND id=?',(owner,str(data.get('id','')))).fetchone()
            if not row or type(data.get('revision'))!=int or row['revision']!=data['revision']:raise Error('植物已变化，请刷新后重试',409)
            g=growth(row,time.time())
            if not g['ready']:
                occupied={r['bed'] for r in db.execute('SELECT bed FROM farm_plants WHERE owner=?',(owner,))}
                bed=next((b for b in BEDS.values() if b['id'] not in occupied and bool(b.get('nursery'))==(SPECIES[row['species']]['kind']=='tree')),None)
                if not bed:raise Error('请先空出一块对应的种植床，幼苗将保留进度移回种植床',409)
                db.execute('INSERT INTO farm_plants(owner,bed,id,species,planted,bonus,water_day,fertilizer_day,bloom_resolved) VALUES (?,?,?,?,?,?,?,?,?)',(owner,bed['id'],row['id'],row['species'],time.time(),g['progress']*SPECIES[row['species']]['hours']*3600,row['water_day'],row['fertilizer_day'],row['bloom_resolved']))
            else:stock(db,owner,row['species'],1)
            if row['container']=='pot':stock(db,owner,'pot',1)
            db.execute('DELETE FROM farm_arrangements WHERE owner=? AND id=?',(owner,row['id']))
            event_text='主人把岛上的'+SPECIES[row['species']]['name']+('收回仓库' if g['ready'] else '移回'+bed_name(bed['id'])+'继续生长')
        elif op=='place':
            slot=SLOTS.get(data.get('slot')) if isinstance(data.get('slot'),str) else None
            p=SPECIES.get(data.get('species')) if isinstance(data.get('species'),str) else None
            if not slot or not p or slot['kind']!=p['kind']:raise Error('请选择合适的花台或树池')
            if db.execute('SELECT 1 FROM farm_decor WHERE owner=? AND slot=?',(owner,slot['id'])).fetchone():raise Error('这个位置已有植物，请先收回',409)
            stock(db,owner,p['id'],-1)
            if p['kind']=='flower':stock(db,owner,'pot',-1)
            db.execute('INSERT INTO farm_decor VALUES (?,?,?,?)',(owner,slot['id'],p['id'],time.time()))
            event_text='主人把'+p['name']+'安放在'+slot['name']
        elif op=='recover':
            if not isinstance(data.get('slot'),str):raise Error('请选择摆放位置')
            row=db.execute('SELECT * FROM farm_decor WHERE owner=? AND slot=?',(owner,data['slot'])).fetchone()
            if not row:raise Error('这里没有可收回的植物',409)
            stock(db,owner,row['species'],1)
            if SPECIES[row['species']]['kind']=='flower':stock(db,owner,'pot',1)
            db.execute('DELETE FROM farm_decor WHERE owner=? AND slot=?',(owner,row['slot']))
            event_text='主人收回了'+SLOTS[row['slot']]['name']+'的'+SPECIES[row['species']]['name']
        elif op=='cook':
            # A game recipe, never pass raw crops directly to the animal care engine.
            stock(db,owner,'pumpkin',-1);supplies.stock(db,owner,'treat',1)
        else:raise Error('操作不存在',404)
        if event_text:
            db.execute('INSERT INTO farm_events(owner,created,kind,summary) VALUES (?,?,?,?)',(owner,time.time(),op,event_text))
            from . import diary_service
            diary_service.record(db,owner,3,'garden:'+token,'event','我的花园里，'+event_text.rstrip('。'))
            db.execute('DELETE FROM farm_events WHERE owner=? AND id NOT IN (SELECT id FROM farm_events WHERE owner=? ORDER BY id DESC LIMIT 80)',(owner,owner))
        db.execute('INSERT INTO farm_requests VALUES (?,?,?)',(owner,token,payload));db.commit()
    except Exception:db.rollback();raise
    return state(owner)
