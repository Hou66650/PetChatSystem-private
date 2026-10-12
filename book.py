# -*- coding: utf-8 -*-
"""旧版单文件入口已退役。

旧代码在 legacy/book.py（仅作历史参考，依赖 Flask 2.x 的 _app_ctx_stack，
在 Flask 3 下无法启动；其配套模板也已随重构更新，不再兼容）。

现在请运行：

    python run.py          # 启动服务 http://127.0.0.1:5000
    python run.py --init-db  # 首次部署时初始化数据库
"""
import sys

print(__doc__)
sys.exit(1)
