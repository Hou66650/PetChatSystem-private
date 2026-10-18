# 鸿蒙桌宠接入状态（0.12.0）

## 当前结论

**MatePad Air / HarmonyOS 6.1 / API 24 尚不能启用跨应用桌宠。** 0.12.0 已安装并实测能力检测：当前签名没有 `ohos.permission.SYSTEM_FLOAT_WINDOW`，准备窗口时返回明确原因，不创建服务端行程，原猫咪仍可见并活动。不得把浏览器渲染器测试、应用内小窝或原生预览当作系统桌宠已上线。

本机 SDK 的 `PermissionDefinitions.json` 将 `SYSTEM_FLOAT_WINDOW` 定义为 `system_grant / system_basic / provisionEnable:true`。普通运行时弹窗不能授予；本次没有添加未经授权的权限声明、改动签名权限或伪造后台任务。`@ohos.window.floatView` 是 API 26.0.0 起的新接口，不能在 API 24 上直接调用。`floatingBall` 从 API 20 起提供模板球，但也是受控权限，不能作为任意 3D 桌宠窗口使用。`setWindowBackgroundColor` 的编译诊断另提示 tablet 不支持，透明承载仍需单独验证。

参考本机安装 SDK：`openharmony/ets/api/@ohos.window.d.ts`、`@ohos.window.floatView.d.ts`、`@ohos.window.floatingBall.d.ts`、`openharmony/toolchains/lib/PermissionDefinitions.json`。正式开放前需要核实华为对目标设备与桌宠用途的权限开放条件；即使获得权限也仍需真机验证，不能承诺只改配置就能在这台平板使用。

## 已实现的接入代码

- `TabletDesktopHost.ets`：权限检查 → 创建窗口 → 设置内容 → 显示；只有完整成功才准备传送。独立窗口仅接受已配置站点，手势位移有限幅和屏幕边界，重复创建拒绝，窗口关闭释放资源。主应用退到后台不会直接销毁独立桌宠；独立窗口隐藏/锁屏则主动召回，节省资源。
- `/tablet-companion`：独立、受 CSP 约束的绘制页面。复用桌宠动画编排器和 25 动作目录，轻触摸头、拖动移动窗口、长按选择动作、暂停/继续、自主小动作与召回。窗口是带操作条的矩形区域，尚未承诺透明空白区域触控穿透。
- `tablet-desktop-session.js`：复用现有一次性配对、manifest、ready、depart-complete、arrived、心跳和 return 协议。不新建第二套宠物状态。模型与饰品通过 GLB 头、字节预算、SHA-256 校验并完成绘制准备后才发送 ready；取消后迟到结果不再改变场景。
- 凭证只在窗口内存，配对码不进入 URL、不持久化；请求限定当前站点并拒绝重定向。HTTPS 或 USB 回环安全上下文可使用模型校验；不支持 WebCrypto 的普通 HTTP 页面明确拒绝传送。
- 网络失联超过 40 秒、服务器结束行程、绘制上下文丢失、关闭/隐藏窗口时收起桌宠并尝试 return。进程被杀或离线时由原服务端租约恢复小窝，不伪造音频、导航、定位后台任务保活；暂停动作仍维持行程心跳。
- 原网页传送门在鸿蒙先检查窗口；权限不足时不会展示 Windows 配对步骤、消费配对码或隐藏小窝模型。准备失败也不会关闭已存在的另一行程窗口。

## 验证与未完成项

已通过：ArkTS 编译和安装；真机权限拒绝及小窝模型保留；状态机取消竞争、断网、撤销和窗口显示失败；原生接口替身测试的窗口生命周期、拖动边界；真实 Chromium 与隔离后端的 25 动作、两件饰品、睡觉起身移动、暂停、拖动、召回；原 Windows 动画与传送门相关回归。

浏览器联调的 **OS 窗口宿主由测试模拟**，不是实际跨应用悬浮验证。尚未完成：取得可用的系统窗口承载条件，真机桌面透明合成/拖动/触控穿透，真实后台/锁屏生命周期验收，四宠长时间性能与发热测试。新 API 26 的标准悬浮窗适配不在这批代码中。

测试：`node test/tablet_desktop.cjs`；运行独立 `test/desktop_transfer_server.py` 后执行 `node test/tablet_desktop_browser.cjs`。测试服务用临时数据库和本地回答，不调用生产账号或付费 API。
