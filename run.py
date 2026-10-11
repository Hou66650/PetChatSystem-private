# -*- coding: utf-8 -*-
"""启动入口。

用法：
    python run.py                # 启动开发服务器（127.0.0.1:5000）
    python run.py --init-db      # 按 app/schema.sql 初始化数据库（幂等，不动存量数据）
"""
import sys

from app import create_app
from app.db import init_db

app = create_app()

if __name__ == '__main__':
    if '--init-db' in sys.argv:
        with app.app_context():
            init_db()
        print(f'数据库初始化完成: {app.config["DATABASE_PATH"]}')
        sys.exit(0)
    app.run(host='0.0.0.0', port=5001, debug=app.config['DEBUG'])
