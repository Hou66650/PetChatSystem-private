# -*- coding: utf-8 -*-
"""启动入口。

用法：
    python run.py                # 启动开发服务器（127.0.0.1:5000）
    python run.py --init-db      # 按 app/schema.sql 初始化数据库（幂等，不动存量数据）
"""
import os
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
    # threaded：局域网多人同时访问（含大模型文件下载）不互相顶断连接
    # PORT 环境变量可覆盖端口（如 WSL 部署用 5002 避开 Windows 实例）
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', '5001')),
            debug=app.config['DEBUG'], threaded=True)
