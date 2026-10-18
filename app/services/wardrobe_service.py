"""Account-owned cosmetics, pet-specific slots, and the existing island wallet."""
import time
from ..db import get_db
from . import cat_market_service as wallet

CATALOG = [
    dict(id='moss-bow', name='苔绿领结', slot='neck', price=60, design='bow', color='#718c75', description='柔软双层领结，配一枚暖金色扣。'),
    dict(id='coral-bow', name='珊瑚领结', slot='neck', price=60, design='bow', color='#c67c70', description='低饱和珊瑚红，为日常添一点温暖。'),
    dict(id='daisy', name='雏菊发饰', slot='head', price=80, design='flower', color='#f4e9cc', description='奶油花瓣与蜂蜜花心，小小一朵落在头顶。'),
    dict(id='blue-beret', name='雾蓝贝雷帽', slot='head', price=100, design='beret', color='#778e9b', description='圆润的羊毛帽型，轻轻斜戴，保留耳朵轮廓。'),
]
ITEMS = {item['id']: item for item in CATALOG}
Error = wallet.MarketError


def init_schema():
    get_db().executescript('''
        CREATE TABLE IF NOT EXISTS pet_wardrobe_owned(
            owner TEXT NOT NULL, item TEXT NOT NULL, created REAL NOT NULL,
            PRIMARY KEY(owner,item));
        CREATE TABLE IF NOT EXISTS pet_wardrobe_equipped(
            owner TEXT NOT NULL, pet INTEGER NOT NULL CHECK(pet BETWEEN 1 AND 4),
            slot TEXT NOT NULL CHECK(slot IN ('head','neck')), item TEXT NOT NULL,
            PRIMARY KEY(owner,pet,slot),
            FOREIGN KEY(owner,item) REFERENCES pet_wardrobe_owned(owner,item));
    ''')


def pet_id(value):
    if type(value) is not int or value not in (1, 2, 3, 4):
        raise Error('请选择有效宠物')
    return value


def equipped(owner, pet):
    return [dict(ITEMS[r['item']]) for r in get_db().execute(
        'SELECT item FROM pet_wardrobe_equipped WHERE owner=? AND pet=? ORDER BY slot',
        (owner, pet)) if r['item'] in ITEMS]


def state(owner, pet):
    from . import portal_service, growth_asset_service
    pet_id(pet)
    coins = wallet.state(owner)
    spec = portal_service.pet_spec(owner, str(pet))
    catalog = [dict(x) for x in CATALOG]
    if pet == 3:
        for coat in wallet.CATALOG:
            preview = growth_asset_service.apply_stage(owner, '3', dict(model=coat['model'], coat=coat['id'], height=.85))
            catalog.append({**coat, 'id': 'coat:'+coat['id'], 'slot': 'coat', 'model': preview['model'], 'height': preview['height']})
    return dict(catalog=catalog, pet=spec, balance=coins['balance'], guest=coins['guest'],
                dailyClaimed=coins['dailyClaimed'], ledger=coins['ledger'],
                owned=[r['item'] for r in get_db().execute('SELECT item FROM pet_wardrobe_owned WHERE owner=?', (owner,))]
                    + ['coat:'+x for x in coins['owned']],
                equipped={x['slot']: x['id'] for x in equipped(owner, pet)},
                activeCoat=None if spec.get('custom') else 'coat:'+coins['active'],
                compatible=not spec.get('custom'),
                compatibilityNote='定制模型尚未完成装扮挂点适配，请先选择其他标准伙伴。' if spec.get('custom') else '')


def check_available(owner, pet):
    db = get_db()
    if db.execute("""SELECT 1 FROM portal_trips t LEFT JOIN portal_islands i ON i.id=t.destination
        WHERE t.status IN ('active','pairing') AND ((t.owner=? AND t.pet=?) OR (i.owner=? AND i.pet=?))""",
        (owner, str(pet), owner, str(pet))).fetchone():
        raise Error('伙伴正在旅行或接待好友，请结束行程后换装', 409)
    if db.execute('SELECT 1 FROM park_presence WHERE owner=? AND updated>?', (owner, time.time()-12)).fetchone():
        raise Error('请先离开公共乐园，再更换装扮', 409)


def operate(owner, operation, data):
    pet = pet_id(data.get('petId'))
    if not owner.startswith('user:'):
        raise Error('请登录后购买和穿戴装扮', 403)
    item_id = data.get('item')
    if operation == 'daily':
        wallet.operate(owner, 'daily', {})
        return state(owner, pet)
    if isinstance(item_id, str) and item_id.startswith('coat:'):
        if pet != 3 or operation not in ('buy', 'equip'):
            raise Error('猫咪毛色只能用于猫咪')
        wallet.operate(owner, operation, {'coat': item_id[5:]})
        return state(owner, pet)
    db = get_db()
    db.execute('BEGIN IMMEDIATE')
    try:
        wallet.ensure(owner)
        if operation in ('buy', 'equip'):
            if not isinstance(item_id, str) or item_id not in ITEMS:
                raise Error('装扮不存在', 404)
            owned = db.execute('SELECT 1 FROM pet_wardrobe_owned WHERE owner=? AND item=?', (owner, item_id)).fetchone()
            if operation == 'buy' and not owned:
                price = ITEMS[item_id]['price']
                if not db.execute('UPDATE cat_wallets SET balance=balance-? WHERE owner=? AND balance>=?', (price, owner, price)).rowcount:
                    raise Error('岛屿代币不足，可以领取每日奖励或完成探索')
                db.execute('INSERT INTO pet_wardrobe_owned VALUES (?,?,?)', (owner, item_id, time.time()))
                db.execute('INSERT INTO cat_coin_ledger VALUES (?,?,?,?,?,?)',
                           (owner, 'wardrobe:'+item_id, 'wardrobe_purchase', -price, wallet.day(), time.time()))
            elif operation == 'equip':
                if not owned:
                    raise Error('请先购买这件装扮', 403)
                check_available(owner, pet)
                from . import pet_generation_service
                if pet == 3 and pet_generation_service.appearance(owner):
                    raise Error('定制模型尚未完成装扮挂点适配', 409)
                db.execute('INSERT INTO pet_wardrobe_equipped VALUES (?,?,?,?) ON CONFLICT(owner,pet,slot) DO UPDATE SET item=excluded.item',
                           (owner, pet, ITEMS[item_id]['slot'], item_id))
        elif operation == 'unequip':
            slot = data.get('slot')
            if slot not in ('head', 'neck', 'all'):
                raise Error('装扮部位不存在')
            check_available(owner, pet)
            if slot == 'all':
                db.execute('DELETE FROM pet_wardrobe_equipped WHERE owner=? AND pet=?', (owner, pet))
            else:
                db.execute('DELETE FROM pet_wardrobe_equipped WHERE owner=? AND pet=? AND slot=?', (owner, pet, slot))
        else:
            raise Error('操作不存在', 404)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return state(owner, pet)
