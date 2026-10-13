# -*- coding: utf-8 -*-
"""SQLite 访问层：连接生命周期、查询/执行封装、schema 初始化。

旧版 book.py 的问题：
- 每次启动都执行 book.sql，其中 drop table 会清空 borrows/histroys；
- teardown 函数定义了两次，后者覆盖前者。
这里收敛为单一定义；init_db 只在显式执行 `python run.py --init-db` 时运行，
建表语句全部 create table if not exists，不会动存量数据。
"""
import sqlite3

from flask import g, current_app

from .config import Config


def get_db():
    """当前应用上下文复用同一个连接，请求结束自动关闭。"""
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE_PATH'], timeout=15)
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(_exc=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def query_db(query, args=(), one=False):
    """执行 SELECT，返回 Row 列表（one=True 时返回单条或 None）。"""
    cur = get_db().execute(query, args)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv


def execute_db(query, args=()):
    """执行 INSERT/UPDATE/DELETE 并提交，失败时回滚并抛出原始异常。"""
    db = get_db()
    try:
        db.execute(query, args)
        db.commit()
    except sqlite3.Error:
        db.rollback()
        raise


def init_db():
    """按 schema.sql 建表（幂等，不删数据）。"""
    db = get_db()
    with open(Config.SCHEMA_PATH, encoding='utf-8') as f:
        db.executescript(f.read())
    db.commit()
