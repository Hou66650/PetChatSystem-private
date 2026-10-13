# -*- coding: utf-8 -*-
"""版本号管理工具：每次改动必须升版本 + 记 CHANGELOG（v1.0.1 起强制）。

用法（项目根目录）：
    python3 scripts/bump_version.py patch   # 修复/小调整：1.0.1 → 1.0.2
    python3 scripts/bump_version.py minor   # 新功能：    1.0.1 → 1.1.0
    python3 scripts/bump_version.py major   # 破坏性变更：1.0.1 → 2.0.0

行为：
1. 改写 app/config.py 的 APP_VERSION（页面徽标随之更新）；
2. 校验 CHANGELOG.md 已包含 "## v新版本" 条目——没有就拒绝执行，
   防止只升号不记账。请先把本次改动的 CHANGELOG 小节写好再运行本工具。
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = os.path.join(ROOT, 'app', 'config.py')
LOG = os.path.join(ROOT, 'CHANGELOG.md')


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ('patch', 'minor', 'major'):
        print(__doc__)
        return 1
    part = sys.argv[1]
    s = io.open(CFG, encoding='utf-8').read()
    m = re.search(r"APP_VERSION = os\.environ\.get\('APP_VERSION', '(\d+)\.(\d+)\.(\d+)'\)", s)
    if not m:
        print('错误：app/config.py 里找不到 APP_VERSION 定义')
        return 1
    major, minor, patch = (int(x) for x in m.groups())
    if part == 'patch':
        patch += 1
    elif part == 'minor':
        minor, patch = minor + 1, 0
    else:
        major, minor, patch = major + 1, 0, 0
    new = '%d.%d.%d' % (major, minor, patch)

    log = io.open(LOG, encoding='utf-8').read()
    if ('## v' + new) not in log:
        print('拒绝升号：CHANGELOG.md 里还没有 "## v%s" 条目。' % new)
        print('请先在 CHANGELOG.md 写好本次改动的 v%s 小节，再运行本工具。' % new)
        return 1

    s = s.replace(m.group(0),
                  "APP_VERSION = os.environ.get('APP_VERSION', '%s')" % new, 1)
    io.open(CFG, 'w', encoding='utf-8', newline='').write(s)
    print('APP_VERSION → v%s（记得 git commit + tag v%s 并推送）' % (new, new))
    return 0


if __name__ == '__main__':
    sys.exit(main())
