# -*- coding: utf-8 -*-
"""登录校验装饰器，替代旧版 manager_judge()/reader_judge()。

旧版 reader_judge 直接取 session['user_id']，未登录时抛 KeyError 变成 500；
这里统一改为"未登录 → 渲染对应登录页"，与旧版 manager_judge 行为一致。
校验粒度沿用旧版：只检查是否登录，不区分读者/管理员角色。
"""
from functools import wraps

from flask import render_template, session


def _login_required(login_template, error):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if 'user_id' not in session:
                return render_template(login_template, error=error)
            return view(*args, **kwargs)
        return wrapped
    return decorator


reader_required = _login_required('reader_login.html', '请先登录')
manager_required = _login_required('manager_login.html', '请先以管理员身份登录')
