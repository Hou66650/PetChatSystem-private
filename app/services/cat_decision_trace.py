"""Bounded, public decision evidence. Never store arbitrary telemetry dictionaries."""
import math


def clean_trace(raw):
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError('决策记录格式错误')

    def text(obj, key, limit=220):
        value = obj.get(key, '')
        if not isinstance(value, str) or len(value) > limit:
            raise ValueError('决策文字过长或格式错误')
        return value

    def number(obj, key, low=0, high=10000):
        value = obj.get(key, 0)
        if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
            raise ValueError('决策数值错误')
        return value

    def obj(value):
        if not isinstance(value, dict):
            raise ValueError('决策结构错误')
        return value

    def rows(key, limit):
        value = raw.get(key, [])
        if not isinstance(value, list) or len(value) > limit:
            raise ValueError('决策列表过长')
        return value

    needs = obj(raw.get('needs', {}))
    clean = dict(id=text(raw, 'id', 80), created=number(raw, 'created', high=1e15),
                 worldRevision=text(raw, 'worldRevision', 20),
                 needs={k: number(needs, k, high=1) for k in ('energy', 'hunger', 'thirst')},
                 candidateCount=number(raw, 'candidateCount'), excludedCount=number(raw, 'excludedCount'),
                 model=text(raw, 'model'), outcome=text(raw, 'outcome', 24), ranked=[], excluded=[])
    if not clean['id'] or clean['outcome'] not in ('pending', 'completed', 'blocked', 'interrupted', 'unavailable'):
        raise ValueError('决策结果错误')
    clean['attention'] = [text({'value': s}, 'value', 160) for s in rows('attention', 6)]
    for item in rows('ranked', 8):
        item = obj(item); parts = obj(item.get('parts', {}))
        clean['ranked'].append(dict(target=text(item, 'target', 40), name=text(item, 'name', 120),
                                    score=number(item, 'score', -1000, 1000),
                                    parts={k: number(parts, k, -1000, 1000) for k in ('recency', 'novelty', 'preference', 'repeat', 'distance')}))
    for item in rows('excluded', 8):
        item = obj(item)
        clean['excluded'].append(dict(target=text(item, 'target', 40), name=text(item, 'name', 120), reason=text(item, 'reason')))
    selection = raw.get('selection')
    clean['selection'] = None if selection is None else {k: text(obj(selection), k, limit) for k, limit in
                            [('target', 40), ('name', 120), ('action', 24), ('source', 16), ('trigger', 80), ('reason', 220)]}
    if clean['selection'] and clean['selection']['source'] not in ('user', 'model', 'local'):
        raise ValueError('决策来源错误')
    memory = raw.get('memory')
    clean['memory'] = None if memory is None else dict(before=number(obj(memory), 'before', high=1e9),
                            after=number(memory, 'after', high=1e9), synced=memory.get('synced') is True, note=text(memory, 'note'))
    return clean
