# -*- coding: utf-8 -*-
"""登录与注册（读者 + 管理员），逻辑沿用旧版，仅做整理。"""
from flask import (Blueprint, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from ..db import execute_db, query_db

bp = Blueprint('auth', __name__)


def _get_user_id(username):
    row = query_db('SELECT user_id FROM users WHERE user_name = ?', [username], one=True)
    return row[0] if row else None


# ---------------------------------------------------------------------
# 读者
# ---------------------------------------------------------------------
@bp.route('/reader_login', methods=['GET', 'POST'])
def reader_login():
    error = None
    if request.method == 'POST':
        user = query_db('SELECT * FROM users WHERE user_name = ?',
                        [request.form['username']], one=True)
        if user is None:
            error = 'Invalid username'
        elif not check_password_hash(user['pwd'], request.form['password']):
            error = 'Invalid password'
        else:
            session['user_id'] = user['user_name']
            return redirect(url_for('reader.reader'))
    return render_template('reader_login.html', error=error)


@bp.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        if not request.form.get('username'):
            error = 'You have to enter a username'
        elif not request.form.get('password'):
            error = 'You have to enter a password'
        elif request.form['password'] != request.form['password2']:
            error = 'The two passwords do not match'
        elif _get_user_id(request.form['username']) is not None:
            error = 'The username is already taken'
        else:
            execute_db(
                'INSERT INTO users (user_name, pwd, college, num, email) VALUES (?, ?, ?, ?, ?)',
                [request.form['username'], generate_password_hash(request.form['password']),
                 request.form.get('college'), request.form.get('number'),
                 request.form.get('email')])
            return redirect(url_for('auth.reader_login'))
    return render_template('register.html', error=error)


# ---------------------------------------------------------------------
# 管理员
# ---------------------------------------------------------------------
@bp.route('/manager_login', methods=['GET', 'POST'])
def manager_login():
    error = None
    if request.method == 'POST':
        manager = query_db('SELECT * FROM manager_info WHERE manager_id = ?',
                           [request.form['user_id']], one=True)
        if manager is None:
            error = 'Invalid username'
        elif not check_password_hash(manager['password'], request.form['password']):
            error = 'Invalid password'
        else:
            session['user_id'] = request.form['user_id']
            return redirect(url_for('manager.manager'))
    return render_template('manager_login.html', error=error)


@bp.route('/register_admin', methods=['GET', 'POST'])
def register_admin():
    error = None
    if request.method == 'POST':
        if not request.form.get('password'):
            error = 'You have to input your password'
        elif not request.form.get('manager_id'):
            error = 'You have to input your manager_id'
        else:
            execute_db('INSERT INTO manager_info (manager_id, password) VALUES (?, ?)',
                       [request.form['manager_id'],
                        generate_password_hash(request.form['password'])])
            return redirect(url_for('auth.manager_login'))
    return render_template('register_admin.html', error=error)
