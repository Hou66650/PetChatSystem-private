# -*- coding: utf-8 -*-
"""管理员侧功能：图书/宠物卡片管理、用户管理（沿用旧图书系统逻辑）。

注意：manger_user_modify / manger_user_delete 两个函数名沿用了旧版的拼写
（少了个 a），因为 manager_user_modify.html 模板里 url_for 按这个名字引用，
改名会直接导致模板渲染报错。
"""
import time

from flask import (Blueprint, redirect, render_template, request, url_for)
from werkzeug.security import generate_password_hash

from ..db import execute_db, query_db
from ..decorators import manager_required

bp = Blueprint('manager', __name__)


@bp.route('/manager')
@manager_required
def manager():
    return render_template('manager.html')


@bp.route('/manager/books')
@manager_required
def manager_books():
    return render_template('manager_books.html',
                           books=query_db('SELECT * FROM books'))


@bp.route('/manager/books/add', methods=['GET', 'POST'])
@manager_required
def manager_books_add():
    error = None
    if request.method == 'POST':
        if not request.form.get('id'):
            error = 'You have to input the book ISBN'
        elif not request.form.get('name'):
            error = 'You have to input the book name'
        elif not request.form.get('author'):
            error = 'You have to input the book author'
        elif not request.form.get('company'):
            error = 'You have to input the publish company'
        elif not request.form.get('date'):
            error = 'You have to input the publish date'
        else:
            execute_db(
                'INSERT INTO books (book_id, book_name, author, publish_com, publish_date) '
                'VALUES (?, ?, ?, ?, ?)',
                [request.form['id'], request.form['name'], request.form['author'],
                 request.form['company'], request.form['date']])
            return redirect(url_for('manager.manager_books'))
    return render_template('manager_books_add.html', error=error)


@bp.route('/manager/books/delete', methods=['GET', 'POST'])
@manager_required
def manager_books_delete():
    error = None
    if request.method == 'POST':
        if not request.form.get('id'):
            error = 'You have to input the book name'
        else:
            book = query_db('SELECT * FROM books WHERE book_id = ?',
                            [request.form['id']], one=True)
            if book is None:
                error = 'Invalid book id'
            else:
                execute_db('DELETE FROM books WHERE book_id = ?', [request.form['id']])
                return redirect(url_for('manager.manager_books'))
    return render_template('manager_books_delete.html', error=error)


@bp.route('/manager/book/<id>', methods=['GET', 'POST'])
@manager_required
def manager_book(id):
    book = query_db('SELECT * FROM books WHERE book_id = ?', [id], one=True)
    reader = query_db('SELECT * FROM borrows WHERE book_id = ?', [id], one=True)
    name = query_db('SELECT user_name FROM borrows WHERE book_id = ?', [id], one=True)

    if request.method == 'POST':
        current_time = time.strftime('%Y-%m-%d', time.localtime())
        if name:
            execute_db(
                "UPDATE histroys SET status = ?, date_return = ? "
                "WHERE book_id = ? AND user_name = ? AND status = ?",
                ['returned', current_time, id, name[0], 'not return'])
        execute_db('DELETE FROM borrows WHERE book_id = ?', [id])
        return redirect(url_for('manager.manager_book', id=id))

    return render_template('manager_book.html', book=book, reader=reader)


@bp.route('/manager/modify/<id>', methods=['GET', 'POST'])
@manager_required
def manager_modify(id):
    error = None
    book = query_db('SELECT * FROM books WHERE book_id = ?', [id], one=True)
    if request.method == 'POST':
        if not request.form.get('name'):
            error = 'You have to input the book name'
        elif not request.form.get('author'):
            error = 'You have to input the book author'
        elif not request.form.get('company'):
            error = 'You have to input the publish company'
        elif not request.form.get('date'):
            error = 'You have to input the publish date'
        else:
            execute_db(
                'UPDATE books SET book_name=?, author=?, publish_com=?, publish_date=? '
                'WHERE book_id=?',
                [request.form['name'], request.form['author'],
                 request.form['company'], request.form['date'], id])
            return redirect(url_for('manager.manager_book', id=id))
    return render_template('manager_modify.html', book=book, error=error)


@bp.route('/manager/users')
@manager_required
def manager_users():
    return render_template('manager_users.html', users=query_db('SELECT * FROM users'))


@bp.route('/manager/user/<id>', methods=['GET', 'POST'])
@manager_required
def manager_user(id):
    user = query_db('SELECT * FROM users WHERE user_id = ?', [id], one=True)
    return render_template('manager_userinfo.html', user=user, books=None)


@bp.route('/manager/user/modify/<id>', methods=['GET', 'POST'])
@manager_required
def manger_user_modify(id):
    """函数名拼写沿用旧版（模板 url_for 引用了这个名字）。"""
    error = None
    user = query_db('SELECT * FROM users WHERE user_id = ?', [id], one=True)
    if request.method == 'POST':
        if not request.form.get('username'):
            error = 'You have to input your name'
        elif not request.form.get('password'):
            execute_db(
                'UPDATE users SET user_name=?, college=?, num=?, email=? WHERE user_id=?',
                [request.form['username'], request.form.get('college'),
                 request.form.get('number'), request.form.get('email'), id])
        else:
            execute_db(
                'UPDATE users SET user_name=?, pwd=?, college=?, num=?, email=? WHERE user_id=?',
                [request.form['username'], generate_password_hash(request.form['password']),
                 request.form.get('college'), request.form.get('number'),
                 request.form.get('email'), id])
        if not error:
            return redirect(url_for('manager.manager_user', id=id))
    return render_template('manager_user_modify.html', user=user, error=error)


@bp.route('/manager/user/deleter/<id>', methods=['GET', 'POST'])
@manager_required
def manger_user_delete(id):
    """函数名拼写沿用旧版（模板 url_for 引用了这个名字）。"""
    execute_db('DELETE FROM users WHERE user_id = ?', [id])
    return redirect(url_for('manager.manager_users'))
