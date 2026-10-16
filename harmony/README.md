# 派特岛 · 鸿蒙平板原生客户端

目标真机：HUAWEI MatePad Air LRT-W20，HarmonyOS 6.1.0.135（SP9C00E125R2P4patch09）。

这是第一阶段的工程源码：ArkTS / ArkUI 原生登录、宠物选择、文本聊天、账号历史与横屏双栏/窄窗口布局。没有嵌入网页。3D 小岛、实时语音、种植园、好友串门和私人模型尚未迁移。

**验证状态：服务端隔离测试和客户端传输逻辑测试已通过；当前开发机没有 DevEco Studio / HarmonyOS SDK，尚未编译 HAP、签名安装或进行真机验收。不要把源码交付视为可发布应用。**

## 工程与工具

- 在 DevEco Studio 中打开本目录 `harmony/`，而不是仓库根目录。
- 工程开发态版本 `modelVersion: 6.1.0`，目标 SDK `6.1.0(23)`，最低兼容 `6.0.0(20)`。最低兼容配置尚未经过 6.0 真机验证。
- 使用支持上述 SDK 的 DevEco Studio；通过 IDE 下载/选择 SDK 并同步 Hvigor。当前仓库不包含 SDK、Hvigor 可执行文件或伪造的依赖锁文件。
- Bundle 名称暂用 `com.hou66650.pait.tablet`，对外发布前确认账号中的应用标识。
- 在 IDE 的签名配置中登录华为开发者账号，配置自己的调试签名；平板开启开发者模式和 USB 调试，连接并在平板授权。账号登录和设备授权需要设备所有者操作。
- `build-profile.json5` 不含签名信息。IDE 若将本机签名写进该文件，提交前去除；证书、私钥、密码、本机 SDK 路径和构建产物不入库。

官方参考：[HarmonyOS 6.1.0](https://developer.huawei.com/consumer/cn/doc/harmonyos-releases/overview-610)、[DevEco Studio](https://developer.huawei.com/consumer/cn/deveco-studio/)、[Network Kit HTTP](https://developer.huawei.com/consumer/en/doc/harmonyos-references/js-apis-http)。

## 电脑服务端

本机已在仓库 `venv/` 中准备 Python 依赖。新环境需要 Python 3.10 及以上，创建虚拟环境后安装根目录 `requirements.txt`。

在仓库根目录运行：

```powershell
# 不使用模型服务，先验证连接、账号登录、宠物列表和历史。
# 创建你自己的开发账号，密码在终端隐藏输入，不写入命令行。
.\venv\Scripts\python.exe -X utf8 scripts/run_harmony_dev.py --offline --create-user tablet-dev
.\venv\Scripts\python.exe -X utf8 scripts/run_harmony_dev.py --offline
```

离线模式不会生成模拟 AI 回复，发送消息返回 503。真实聊天需要在根目录 `.env` 配置自己的 `GLM_API_KEY`，然后去掉 `--offline` 重启。密钥仅保存在电脑，禁止放进 ArkTS 工程或提交 Git。

这个专用启动入口：

- 默认监听 `0.0.0.0:5003`，关闭 Flask debugger 和自动重载。
- 只开放 `/api/mobile/v1/` 接口，其他网页与云端任务路由返回 404。
- 使用 `uploads/harmony-dev/tablet.db` 和独立随机会话密钥，不读取或修改日常使用的 `book.db`。开发账号与日常账号因此不共用。
- 首次运行自动建表；同名账号已存在时拒绝覆盖密码。
- 无需模型功能时可用 `--offline --init-only` 检查初始化。

正式接入现有部署时，移动端接口使用同一部署中的账号和陪伴历史；隔离数据库只属于以上开发启动入口。

## 平板连接

电脑和平板连到同一个可信 Wi-Fi，使用 `Get-NetIPAddress -AddressFamily IPv4` 查看电脑的 WLAN 地址。2026-10-16 本机观测值为 `192.168.43.6`，可能随网络变化。

1. 在平板浏览器访问 `http://<电脑IPv4>:5003/api/mobile/v1/bootstrap`，应看到 JSON；这一步验证网络，不等于原生应用通过验收。
2. 原生应用中填写根地址 `http://<电脑IPv4>:5003`，不要填写 `127.0.0.1`、接口路径或账号密码。
3. 勾选“允许本地开发 HTTP”，输入刚创建的开发账号。
4. 若连接失败，检查电脑服务、Wi-Fi 客户端隔离和 Windows 防火墙的专用网络规则；不要整体关闭防火墙。

局域网 HTTP 不加密，仅用于可信网络中的开发账号。公网部署使用有效证书的 HTTPS 地址。迁移服务器后退出登录再重新连接，客户端会清除旧会话。当前开发客户端不保存密码、会话或聊天到磁盘，退出应用后需要重新登录。

## API v1

| 方法与路径（前缀 `/api/mobile/v1`） | 用途 |
| --- | --- |
| `GET /bootstrap` | 协议/服务端版本、公开宠物列表、字数限制、会话 Cookie 名称 |
| `POST /session` | JSON `{username,password}` 登录，接收 Flask HttpOnly 会话 Cookie |
| `GET /session` | 校验当前普通用户账号 |
| `POST /logout` | JSON `{}` 退出；另保留 `DELETE /session` 给支持 DELETE body 的客户端 |
| `GET /history?petId=1` | 当前账号、指定宠物的最近 60 条消息 |
| `POST /chat` | JSON `{petId,message,requestId}`；固定 `surface=chat`，不会执行 3D 动作 |

除 bootstrap 和登录外必须登录普通用户账号。身份由签名 Cookie 和数据库查询决定，不接受 `userId` 指定身份。聊天复用现有 `chat_service`，记忆关闭时沿用现有不保存历史规则。客户端发送失败保留文本和请求编号；已完成请求返回原结果；当前进程内正在处理的重复请求返回 409，稍后可重试。

局限：登录限流、进行中请求去重均在单进程内；公网多进程部署需要共享限流与持久化任务幂等。沿用原系统的 Flask 签名 Cookie，退出清除客户端 Cookie，不提供被复制 Cookie 的服务端立即吊销；公网发布前应统一完善账号会话机制。当前网络组件的重定向行为还需 SDK/真机验证，开发服务返回 JSON，禁止在 API 前添加重定向登录页。

## 验证

```powershell
$env:PYTHONPATH='.;test'
$env:GLM_API_KEY='offline-test-placeholder'
.\venv\Scripts\python.exe -X utf8 -m unittest test_mobile test_companion
node test/harmony_client.cjs
```

Python 测试使用临时数据库与模拟模型，不调用真实供应商。Node 24 测试去除传输模块的类型后执行真实客户端逻辑，覆盖地址策略、Cookie、退出、过期、重试编号、迟到响应和资源释放；**不是 ArkTS 类型检查、ArkUI 渲染或 HAP 编译**。

收到 SDK 后的首轮验收：工程同步与编译 → 调试签名 → 平板安装 → 横竖屏/分屏/软键盘 → 连接与登录 → 四宠物切换 → 一轮真实聊天 → 历史刷新 → 断网重试 → 退出及切账号隔离。只有通过这些步骤，才可标记第一阶段真机完成。

## 后续迁移

1. **基础闭环（当前）**：原生 UI、账号、文本聊天、服务端历史；编译及真机待验收。
2. **原生 3D 验证**：先迁移一个宠物和一个小场景，检验 GLB、骨骼动画、触摸、寻路、帧率、内存和温升，再迁移完整岛屿。现有 Three.js 代码不能直接当作 ArkUI 组件运行。
3. **实时语音**：原生录音、PCM、WebSocket、音频播放与打断，复用服务端短期会话签发；验证麦克风权限、音频焦点和应用生命周期。
4. **业务迁移**：陪伴档案、种植园、补给、私人宠物重建、好友串门与分享。Windows Electron 桌宠和 PowerShell 感知要单独评估鸿蒙可用能力，不能直接承诺等价移植。
