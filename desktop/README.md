# 现实传送门与 Windows 桌宠

服务端、网页和桌面客户端需要一起更新。桌面传送使用协议 2；旧服务端会提示升级，新服务端上未完成准备确认的旧桌面客户端会超时返程。

## 使用

1. 在 `desktop` 目录运行一次 `npm ci`，随后用项目根目录的 `Start-Desktop.cmd` 启动。
2. 在小窝选择“动作 → 双传送门 → 现实传送门”。宠物到门口后点击“确认出发”。
3. 将网页根地址和一次性配对码填入客户端。地址必须连接同一个服务端；本机可用 `http://127.0.0.1:端口`，远程连接使用 HTTPS。
4. 保持小窝页面可见，等待模型与已穿饰品准备完成。宠物走入岛上的门，再从桌面光门走出、站稳，随后自由活动。
5. 点击宠物可摸摸，右键可召回。软件感知默认关闭，只在自由活动阶段允许开启。

启动器默认地址仍为本机 5002，请按实际服务地址修改。网页的登录账号决定传送哪只宠物；客户端只持有本次行程凭证，不保存账号密码或长期凭证。

## 阶段与故障恢复

数据库继续用 `pairing / active / returned` 管理行程互斥，在 active 行程上增加 `phase` 和 `phase_started`：

| 阶段 | 完成条件 |
| --- | --- |
| preparing | 主进程下载模型及已装备饰品，渲染器解析并确认挂点完整 |
| entering | 桌面 `ready` 确认后，网页完成入门裁切动画并提交 `depart-complete` |
| emerging | 桌面完成出门、站稳，提交 `arrived` |
| roaming | 开启桌面移动、互动和轨迹记录 |

确认接口可重试，阶段不能倒退或越级。准备超时为 90 秒，入门和出门各 20 秒，心跳中断 45 秒后返程；截止时间在请求触发的清理中检查。准备失败、关闭客户端或取消会结束行程，异步资源返回不能激活旧行程。准备和穿门期间不产生探索奖励。

网页用门平面裁切宠物及饰品，退出阶段恢复原材质；外出时禁用旧的“隐藏宠物自动恢复”兜底。鸿蒙混合渲染在穿门阶段使用 Web 画面，避免原生宠物绕过裁切。

桌面移动使用 DIP 坐标、加减速和有限转向速度，按镜头投影与模型缩放换算步频。当前支持主显示器工作区，不包含跨屏迁移、桌面窗口碰撞或逐足 IK。出门光门是运行时几何效果。

## 验证

- `python -m unittest discover -s test -p test_portals.py`：阶段、授权、幂等、超时、行程互斥和私有模型。
- `node test/desktop_motion.cjs`：转向、加速度、限速、到达和负原点工作区。
- `node test/portal_approach.cjs`、`node test/portal_confirm.cjs`：真实网页回调的到门与确认逻辑。
- 先启动 `python test/desktop_transfer_server.py`，再运行 `node test/desktop_transfer.cjs`：隔离数据库，实际 Chromium + Electron 主进程、GLB 和饰品，慢加载、出入门、召回、饰品失败及加载中取消。需要 Playwright；可用 `PET_TEST_ELECTRON` 和 `PET_TEST_CHROME` 指定程序路径。
- `desktop/node_modules/electron/dist/electron.exe test/desktop-render.cjs`：透明窗口渲染和门户 DOM 回归；可用 `PET_DESKTOP_TEST_GLB` 提供本地定制模型。

测试账号、截图和数据库均为临时产物，不读取用户运行数据库、不消费模型账户额度。
