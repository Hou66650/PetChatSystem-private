# -*- coding: utf-8 -*-
"""应用工厂：宠物聊天系统（重构版）。

目录结构：
    app/config.py        配置（.env 注入，密钥不进代码）
    app/db.py            SQLite 访问层
    app/decorators.py    登录校验装饰器
    app/llm/             GLM 客户端 + 宠物角色注册表
    app/services/        聊天编排、头像动漫化管线
    app/routes/          蓝图：main / auth / chat / reader / manager
"""
import os

from flask import Flask, g, session

from .config import BASE_DIR, Config
from .db import close_db
from .llm.client import GLMClient


def create_app(config_object=Config):
    app = Flask(__name__,
                template_folder=os.path.join(BASE_DIR, 'templates'),
                static_folder=os.path.join(BASE_DIR, 'static'))
    app.config.from_object(config_object)

    os.makedirs(Config.AVATAR_DIR, exist_ok=True)

    # GLM 客户端全局单例：并发上限 + 重试策略见 config.py
    app.extensions['llm'] = GLMClient(
        api_key=Config.GLM_API_KEY,
        base_url=Config.GLM_BASE_URL,
        models=Config.GLM_MODELS,
        vision_model=Config.GLM_VISION_MODEL,
        image_model=Config.GLM_IMAGE_MODEL,
        timeout=Config.LLM_TIMEOUT,
        image_timeout=Config.LLM_IMAGE_TIMEOUT,
        max_retries=Config.LLM_MAX_RETRIES,
        retry_delay=Config.LLM_RETRY_DELAY,
        max_concurrency=Config.LLM_MAX_CONCURRENCY,
        trust_env=Config.LLM_TRUST_ENV,
    )

    app.teardown_appcontext(close_db)
    from .services import companion_service
    with app.app_context():
        companion_service.init_schema()

    @app.context_processor
    def _companion_scope():
        return {'companion_scope': companion_service.browser_scope()}


    @app.before_request
    def load_logged_in_user():
        g.user = session.get('user_id')

    from .routes import ALL_BLUEPRINTS

    @app.context_processor
    def _inject_app_version():
        """所有模板可直接用 {{ app_version }} 显示版本徽标。"""
        from .config import Config as _Cfg
        return {'app_version': _Cfg.APP_VERSION}
    for blueprint in ALL_BLUEPRINTS:
        app.register_blueprint(blueprint)

    return app
