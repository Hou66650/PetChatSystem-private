# -*- coding: utf-8 -*-
"""路由蓝图注册。"""
from .main import bp as main_bp
from .auth import bp as auth_bp
from .chat import bp as chat_bp
from .reader import bp as reader_bp
from .manager import bp as manager_bp

ALL_BLUEPRINTS = (main_bp, auth_bp, chat_bp, reader_bp, manager_bp)
