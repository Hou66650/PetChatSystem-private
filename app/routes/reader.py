# -*- coding: utf-8 -*-
"""读者侧功能：个人中心、资料修改、检索、借阅（沿用旧图书系统逻辑）。"""
import time

from flask import (Blueprint, flash, g, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import generate_password_hash

from ..db import execute_db, query_db
from ..decorators import reader_required

bp = Blueprint('reader', __name__)


@bp.route('/reader')
@reader_required
def reader():
    return render_template('reader.html')


@bp.route('/reader/info', methods=['GET', 'POST'])
@reader_required
def reader_info():
    user = query_db('SELECT * FROM users WHERE user_name = ?', [g.user], one=True)
    if request.method == 'POST':
        user_tag = request.form.get('user_tag')
        if user_tag:
            execute_db('UPDATE users SET college = ? WHERE user_name = ?', [user_tag, g.user])
            flash('个性签名已更新！', 'success')
        else:
            flash('请输入个性签名！', 'error')
    return render_template('reader_info.html', user=user)


@bp.route('/reader/modify', methods=['GET', 'POST'])
@reader_required
def reader_modify():
    error = None
    user = query_db('SELECT * FROM users WHERE user_name = ?', [g.user], one=True)
    if user is None:
        return render_template('reader_login.html', error='请重新登录')
    user_id = user['user_id']

    def _apply_update(new_username, new_pwd_hash=None):
        execute_db(
            'UPDATE users SET user_name=?, pwd=?, college=?, num=?, email=? WHERE user_id=?',
            [new_username, new_pwd_hash or user['pwd'],
             request.form.get('college'), request.form.get('number'),
             request.form.get('email'), user_id])
        # 用户名改了要同步 session，否则下个请求就"查无此人"
        session['user_id'] = new_username
        return redirect(url_for('reader.reader_info'))

    if request.method == 'POST':
        if not request.form.get('username'):
            error = 'You have to input your name'
        elif not request.form.get('password'):
            return _apply_update(request.form['username'])
        else:
            return _apply_update(request.form['username'],
                                 generate_password_hash(request.form['password']))
    return render_template('reader_modify.html', user=user, error=error)


@bp.route('/reader/query', methods=['GET', 'POST'])
@reader_required
def reader_query():
    error = None
    books = None
    if request.method == 'POST':
        keyword = request.form.get('query', '').strip()
        if not keyword:
            error = '请输入搜索内容'
        elif request.form.get('item') == 'name':
            books = query_db('SELECT * FROM books WHERE book_name = ?', [keyword])
            error = '未找到该书' if not books else None
        else:
            books = query_db('SELECT * FROM books WHERE author = ?', [keyword])
            error = '未找到该作者' if not books else None
    return render_template('reader_query.html', books=books, error=error)


@bp.route('/reader/book/<id>', methods=['GET', 'POST'])
@reader_required
def reader_book(id):
    error = None
    book = query_db('SELECT * FROM books WHERE book_id = ?', [id], one=True)
    reader = query_db('SELECT * FROM borrows WHERE book_id = ?', [id], one=True)
    count = query_db('SELECT COUNT(book_id) FROM borrows WHERE user_name = ?',
                     [g.user], one=True)

    current_time = time.strftime('%Y-%m-%d', time.localtime())
    return_time = time.strftime('%Y-%m-%d', time.localtime(time.time() + 2600000))
    if request.method == 'POST':
        if reader:
            error = 'The book has already borrowed.'
        elif count[0] == 3:
            error = "You can't borrow more than three books."
        else:
            execute_db(
                'INSERT INTO borrows (user_name, book_id, date_borrow, date_return) VALUES (?, ?, ?, ?)',
                [g.user, id, current_time, return_time])
            execute_db(
                'INSERT INTO histroys (user_name, book_id, date_borrow, status) VALUES (?, ?, ?, ?)',
                [g.user, id, current_time, 'not return'])
            return redirect(url_for('reader.reader_book', id=id))
    return render_template('reader_book.html', book=book, reader=reader, error=error)


@bp.route('/reader/histroy', methods=['GET', 'POST'])
@reader_required
def reader_histroy():
    histroys = query_db(
        'SELECT * FROM histroys, books WHERE histroys.book_id = books.book_id '
        'AND histroys.user_name = ?', [g.user])
    return render_template('reader_histroy.html', histroys=histroys)
