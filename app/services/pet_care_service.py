"""Time-aware care. Confirmed events, not similarity matches, drive reminders.

Emotion cues are a conservative local text policy, not a psychological diagnosis.
"""
import re
import time
import uuid
from datetime import datetime, timedelta, timezone

from ..db import get_db
from . import companion_service as memory

TZ = timezone(timedelta(hours=8))
EVENTS = ('面试', '考试', '答辩', '演讲', '比赛', '开会', '复诊', '生日', '出差')


def clock():
    return time.time()


class CareError(ValueError):
    pass


def init_schema():
    get_db().executescript('''
    CREATE TABLE IF NOT EXISTS pet_care_settings(
      owner TEXT NOT NULL,pet_id INTEGER NOT NULL,enabled INTEGER NOT NULL DEFAULT 1,
      emotion INTEGER NOT NULL DEFAULT 1,quiet_start INTEGER NOT NULL DEFAULT 22,
      quiet_end INTEGER NOT NULL DEFAULT 8,PRIMARY KEY(owner,pet_id));
    CREATE TABLE IF NOT EXISTS pet_care_events(
      id TEXT PRIMARY KEY,owner TEXT NOT NULL,pet_id INTEGER NOT NULL,title TEXT NOT NULL,
      source TEXT NOT NULL,source_id INTEGER,event_at REAL NOT NULL,remind_at REAL NOT NULL,
      state TEXT NOT NULL DEFAULT 'draft',created REAL NOT NULL,updated REAL NOT NULL);
    CREATE INDEX IF NOT EXISTS pet_care_due ON pet_care_events(owner,pet_id,state,remind_at);
    CREATE TABLE IF NOT EXISTS pet_care_deliveries(
      owner TEXT NOT NULL,day TEXT NOT NULL,event_id TEXT NOT NULL,created REAL NOT NULL,
      PRIMARY KEY(owner,day),UNIQUE(event_id));
    ''')


def settings(owner, pet_id):
    row = get_db().execute('SELECT * FROM pet_care_settings WHERE owner=? AND pet_id=?', (owner, pet_id)).fetchone()
    return dict(row) if row else dict(enabled=1, emotion=1, quiet_start=22, quiet_end=8)


def public(row):
    return {k: row[k] for k in ('id', 'title', 'source', 'event_at', 'remind_at', 'state')}


def state(owner, pet_id):
    prefs = settings(owner, pet_id)
    enabled = bool(memory.settings(owner)['enabled'])
    rows = get_db().execute('SELECT * FROM pet_care_events WHERE owner=? AND pet_id=? ORDER BY updated DESC LIMIT 30', (owner, pet_id)).fetchall() if enabled else []
    return dict(scope=memory.browser_scope(), petId=pet_id, memoryEnabled=enabled, signedIn=owner.startswith('user:'),
                settings={k: prefs[k] for k in ('enabled', 'emotion', 'quiet_start', 'quiet_end')},
                events=[public(r) for r in rows], timezone='Asia/Shanghai')


def number(text):
    if text.isdigit(): return int(text)
    digits = dict(zip('零一二三四五六七八九', range(10))); digits['两'] = 2
    if '十' in text:
        left, right = text.split('十', 1)
        return (digits.get(left, 1) * 10) + digits.get(right, 0)
    return digits.get(text, -1)


def proposed_time(message, now):
    today = datetime.fromtimestamp(now, TZ)
    day = None
    iso = re.search(r'(20\d{2})[-年/](\d{1,2})[-月/](\d{1,2})日?', message)
    if iso:
        try: day = today.replace(year=int(iso[1]), month=int(iso[2]), day=int(iso[3]))
        except ValueError: return None
    else:
        relative = re.search('后天|明天|今天', message)
        week = re.search(r'(下周|这周|本周|周|星期)([一二三四五六日天])', message)
        if relative:
            day = today + timedelta(days={'今天': 0, '明天': 1, '后天': 2}[relative[0]])
        elif week:
            target = '一二三四五六日天'.index(week[2]); target = min(target, 6)
            offset = target - today.weekday()
            if week[1] == '下周': offset += 7
            elif week[1] in ('周', '星期') and offset < 0: offset += 7
            day = today + timedelta(days=offset)
    if day is None: return None
    hour, minute = 9, 0
    clock = re.search(r'(上午|早上|下午|晚上|中午)?\s*([零一二三四五六七八九十两\d]{1,3})(?:点|时|:|：)(半|[零一二三四五六七八九十\d]{1,3})?', message)
    if clock:
        hour = number(clock[2]); minute = 30 if clock[3] == '半' else number(clock[3]) if clock[3] else 0
        if clock[1] in ('下午', '晚上', '中午') and hour < 12: hour += 12
        if not 0 <= hour < 24 or not 0 <= minute < 60: return None
    result = day.replace(hour=hour, minute=minute, second=0, microsecond=0).timestamp()
    return result if now < result < now + 366 * 86400 else None


def emotion_cue(message):
    # Require an explicit personal cue. Quoted, negated, hypothetical and third-party
    # statements must not turn into autonomous physical interaction.
    if re.search(r'别过来|不要过来|让我静静|让我静一静|不想被打扰|不要安慰|不用安慰', message):
        return dict(kind='space', action='space', basis='用户明确希望保留空间')
    if re.search(r'[“”「」"“]|如果|假如|假设|比如|他说|她说|朋友|电影|小说|故事|你难过|你累|不难过|没难过|不焦虑|不紧张|不累|开玩笑|没有|并不|不是|不觉得|没觉得|不再|一点也不', message):
        return None
    for pattern, kind in ((r'(?:我|今天|现在|真的|好|有点|太).{0,8}(?:难过|低落|沮丧|伤心|失落)|面试.{0,4}(?:没过|失败)|考试.{0,4}(?:没过|考砸)', 'low'),
                          (r'(?:我|今天|现在|真的|好|有点|太).{0,8}(?:焦虑|紧张|压力大|压力好大)', 'tense'),
                          (r'(?:我|今天|现在|真的|好|有点|太).{0,8}(?:好累|很累|疲惫|累了)', 'tired')):
        if re.search(pattern, message): return dict(kind=kind, action='company', basis='本轮明确的文字表达')
    return None


def on_turn(db, owner, pet_id, message, source_id, remember=True, now=None):
    now = clock() if now is None else now
    prefs = settings(owner, pet_id)
    result = dict(emotion=emotion_cue(message) if prefs['emotion'] else None, event=None)
    if not owner.startswith('user:') or not remember or not prefs['enabled'] or memory.SENSITIVE.search(message): return result
    titles = [name for name in EVENTS if name in message]
    if len(titles) != 1: return result
    title = titles[0]
    if re.search(r'取消|不去了|不参加|不用提醒|不要提醒|忘记|忘掉', message):
        db.execute("UPDATE pet_care_events SET state='cancelled',updated=? WHERE owner=? AND pet_id=? AND title=? AND state IN ('draft','scheduled')", (now, owner, pet_id, title))
        return result
    if re.search(r'如果|假如|可能|也许|他说|她说|朋友|电影|小说|[“”"]|没有|不需要', message): return result
    at = proposed_time(message, now)
    if at is None: return result
    existing = db.execute("SELECT id FROM pet_care_events WHERE owner=? AND pet_id=? AND title=? AND event_at=? AND state IN ('draft','scheduled')", (owner, pet_id, title, at)).fetchone()
    if existing: return result
    # Changes invalidate the previous scheduled reminder immediately, then ask for
    # confirmation of the new date; never silently keep reminding the old plan.
    db.execute("UPDATE pet_care_events SET state='superseded',updated=? WHERE owner=? AND pet_id=? AND title=? AND state IN ('draft','scheduled')", (now, owner, pet_id, title))
    if db.execute("SELECT count(*) FROM pet_care_events WHERE owner=? AND state IN ('draft','scheduled')",(owner,)).fetchone()[0] >= 30: return result
    event_id = uuid.uuid4().hex
    db.execute('INSERT INTO pet_care_events(id,owner,pet_id,title,source,source_id,event_at,remind_at,created,updated) VALUES (?,?,?,?,?,?,?,?,?,?)',
               (event_id, owner, pet_id, title, message[:200], source_id, at, min(at, max(now + 60, at - 3600)), now, now))
    result['event'] = public(db.execute('SELECT * FROM pet_care_events WHERE id=?', (event_id,)).fetchone())
    # Keep the account store bounded without dropping active plans.
    db.execute("DELETE FROM pet_care_events WHERE owner=? AND state IN ('cancelled','superseded','expired','delivered') AND updated<?", (owner, now - 90 * 86400))
    return result


def save_settings(owner, pet_id, data):
    if not isinstance(data, dict): raise CareError('设置格式不正确')
    old = settings(owner, pet_id)
    for key in ('enabled', 'emotion'):
        if key in data:
            if type(data[key]) is not bool: raise CareError('开关格式不正确')
            old[key] = int(data[key])
    for key in ('quiet_start', 'quiet_end'):
        if key in data:
            if type(data[key]) is not int or not 0 <= data[key] <= 23: raise CareError('免打扰时间应为 0–23 点')
            old[key] = data[key]
    db = get_db()
    with db:
        db.execute('INSERT OR REPLACE INTO pet_care_settings VALUES (?,?,?,?,?,?)', (owner, pet_id, old['enabled'], old['emotion'], old['quiet_start'], old['quiet_end']))


def save_event(owner, pet_id, data, event_id=None):
    if not memory.settings(owner)['enabled']: raise CareError('请先在陪伴档案中开启记忆')
    if not isinstance(data, dict): raise CareError('计划格式不正确')
    db = get_db(); now = clock()
    with db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT * FROM pet_care_events WHERE owner=? AND pet_id=? AND id=?', (owner, pet_id, event_id)).fetchone() if event_id else None
        if event_id and not row: raise CareError('没有找到这件事')
        title = data.get('title', row['title'] if row else '')
        if not isinstance(title, str) or not 1 <= len(title.strip()) <= 60 or memory.SENSITIVE.search(title): raise CareError('请填写 1–60 字的事件名称，不含密码等敏感信息')
        try:
            at, remind = float(data['event_at']), float(data['remind_at'])
            if not (now < at <= now + 366 * 86400 and now - 60 <= remind <= at): raise ValueError()
        except (KeyError, TypeError, ValueError, OverflowError): raise CareError('请确认未来的事件时间；提醒时间不能晚于事件')
        if row and row['state'] not in ('draft', 'scheduled'): raise CareError('此计划已结束，请重新添加')
        if not row and db.execute("SELECT count(*) FROM pet_care_events WHERE owner=? AND state IN ('draft','scheduled')", (owner,)).fetchone()[0] >= 30: raise CareError('请先整理已有计划，最多保留 30 件待办')
        event_id = event_id or uuid.uuid4().hex
        if row:
            db.execute("UPDATE pet_care_events SET title=?,event_at=?,remind_at=?,state='scheduled',updated=? WHERE id=?", (title.strip(), at, remind, now, event_id))
        else:
            db.execute("INSERT INTO pet_care_events(id,owner,pet_id,title,source,event_at,remind_at,state,created,updated) VALUES (?,?,?,?,?,?,?,'scheduled',?,?)", (event_id, owner, pet_id, title.strip(), '用户手动确认', at, remind, now, now))
    return event_id


def claim(owner, pet_id, now=None):
    now = clock() if now is None else now
    db = get_db()
    with db:
        db.execute('BEGIN IMMEDIATE')
        prefs = settings(owner, pet_id)
        if not prefs['enabled'] or not memory.settings(owner)['enabled']: return None
        local = datetime.fromtimestamp(now, TZ)
        start, end = prefs['quiet_start'], prefs['quiet_end']
        quiet = start <= local.hour < end if start < end else local.hour >= start or local.hour < end if start > end else False
        db.execute("UPDATE pet_care_events SET state='expired',updated=? WHERE owner=? AND state IN ('draft','scheduled') AND event_at<?", (now, owner, now))
        if quiet or db.execute('SELECT 1 FROM pet_care_deliveries WHERE owner=? AND day=?', (owner, local.date().isoformat())).fetchone(): return None
        row = db.execute("SELECT * FROM pet_care_events WHERE owner=? AND pet_id=? AND state='scheduled' AND remind_at<=? AND event_at>=? ORDER BY remind_at LIMIT 1", (owner, pet_id, now, now)).fetchone()
        if not row: return None
        db.execute('INSERT INTO pet_care_deliveries VALUES (?,?,?,?)', (owner, local.date().isoformat(), row['id'], now))
        db.execute("UPDATE pet_care_events SET state='delivered',updated=? WHERE id=?", (now, row['id']))
        return dict(id=row['id'], title=row['title'], message='你提过的“'+row['title']+'”快到了。慢慢来，我在岛上给你打气。')
