"""Operator-only copy of explicitly authorized cases; no public cross-owner API.

Dry run by default. --apply requires --backup outside the project. Existing
target profiles, account memories, equipped models and original cases are kept.
Cloud jobs are never resumed/copied. Completed adaptation IDs stay unchanged
because quality fingerprints refer to the immutable adaptation provenance.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import time
import uuid


def copy_cases(db, source, target, ids):
    if source==target or not ids or len(ids)!=len(set(ids)):
        raise ValueError('请选择不同账号和不重复的档案 ID')
    db.execute('''CREATE TABLE IF NOT EXISTS pet_studio_case_copies(
        source TEXT NOT NULL, target_owner TEXT NOT NULL, copied TEXT NOT NULL,
        created REAL NOT NULL, PRIMARY KEY(source,target_owner))''')
    report=[]
    for key in ids:
        original=db.execute('SELECT * FROM pet_studio_tasks WHERE id=? AND owner=?',(key,source)).fetchone()
        if not original: raise ValueError('来源账号没有指定档案：'+key)
        previous=db.execute('SELECT copied FROM pet_studio_case_copies WHERE source=? AND target_owner=?',(key,target)).fetchone()
        if previous and db.execute('SELECT 1 FROM pet_studio_tasks WHERE id=? AND owner=?',(previous[0],target)).fetchone():
            report.append(dict(source=key,copied=previous[0],existing=True));continue
        if db.execute('SELECT count(*) FROM pet_studio_tasks WHERE owner=?',(target,)).fetchone()[0]>=20:
            raise ValueError('目标账号已达到 20 份档案上限')
        adaptation=db.execute('SELECT * FROM pet_studio_adaptations WHERE task=?',(key,)).fetchone()
        if adaptation and adaptation['status']=='running': raise ValueError('请等待动作适配结束后复制')
        new=uuid.uuid4().hex; row=dict(original);row.update(id=new,owner=target,created=time.time(),updated=time.time())
        if row['status']=='awaiting_generation': row['status']='draft'
        cols=list(row);db.execute('INSERT INTO pet_studio_tasks ('+','.join(cols)+') VALUES ('+','.join('?' for _ in cols)+')',tuple(row.values()))
        hashes={}
        for asset in db.execute('SELECT * FROM pet_studio_assets WHERE task=?',(key,)).fetchall():
            db.execute('INSERT INTO pet_studio_assets VALUES (?,?,?,?)',(new,asset['slot'],asset['mime'],asset['data']))
            hashes[asset['slot']]=hashlib.sha256(asset['data']).hexdigest()
        for table in ('pet_studio_adaptations','pet_studio_quality'):
            for record in db.execute('SELECT * FROM '+table+' WHERE task=?',(key,)).fetchall():
                row=dict(record);row['task']=new
                db.execute('INSERT INTO '+table+' ('+','.join(row)+') VALUES ('+','.join('?' for _ in row)+')',tuple(row.values()))
        for asset in db.execute('SELECT slot,data FROM pet_studio_assets WHERE task=?',(new,)):
            if hashlib.sha256(asset['data']).hexdigest()!=hashes[asset['slot']]:raise ValueError('复制校验失败')
        db.execute('INSERT OR REPLACE INTO pet_studio_case_copies VALUES (?,?,?,?)',(key,target,new,time.time()))
        report.append(dict(source=key,copied=new,name=original['name'],assets=hashes,existing=False))
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',required=True);parser.add_argument('--source-user',required=True)
    parser.add_argument('--target-user',required=True);parser.add_argument('--task',action='append',required=True)
    parser.add_argument('--apply',action='store_true');parser.add_argument('--backup')
    args=parser.parse_args();path=Path(args.database).resolve()
    if not path.is_file():raise ValueError('数据库不存在')
    with sqlite3.connect(path) as db:
        db.row_factory=sqlite3.Row
        def owner(name):
            rows=db.execute('SELECT user_id FROM users WHERE user_name=?',(name,)).fetchall()
            if len(rows)!=1:raise ValueError('用户名不存在或不唯一')
            return 'user:'+str(rows[0][0])
        source,target=owner(args.source_user),owner(args.target_user)
        if args.apply:
            if not args.backup:raise ValueError('--apply 必须指定 --backup')
            backup=Path(args.backup).resolve()
            if backup.exists() or backup==path:raise ValueError('备份路径已存在')
            backup.parent.mkdir(parents=True,exist_ok=True)
            with sqlite3.connect(backup) as dest:db.backup(dest)
        db.execute('BEGIN IMMEDIATE')
        try:
            report=copy_cases(db,source,target,args.task)
            if args.apply:db.commit()
            else:db.rollback()
        except Exception:
            db.rollback();raise
        print(json.dumps(dict(applied=args.apply,cases=report),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
