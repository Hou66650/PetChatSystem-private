# 成长阶段独立模型与接入

## 阶段语义

`app/services/growth_service.py` 继续按出生日期的日历月判断：不足六个月为幼年，不足十二个月为少年，其后成年。领养默认三个月；生日决定年龄，领养/相识日期决定陪伴天数。六月、十二月及月末边界由 `test/test_growth.py` 使用临时数据库验证，没有改成固定 180/365 天。

`static/data/pet-growth-models.json` 含 12 条阶段配置。Web、旅行/桌面传送门和鸿蒙资源白名单都以该清单核对资源身份。没有成长资料的用户保持原行为；私人工作室模型不替换为通用幼宠。

## 资源与尺寸规则

- 受支持阶段使用清单中的独立 GLB 和目标高度，不再叠加旧 `appearance.scale`。
- 旧 scale 只保留给语音音高及私人/未支持外观的旧回退行为。
- 阶段模型使用 `PetModelBounds` 测量真实蒙皮边界，不再用旧 `Box3 + skeleton.pose()` 近似。每次替换重算贴地、碰撞半径、步幅、交互高度和近景中心。
- 所有阶段资源启用有限足底采样贴地，避免旧 Box3 归一化造成浮空，也避免成年旧动作的局部穿地。
- 猫的五种标准毛色均有独立成长路径；私人模型保持授权 API 和身份，不进入公共缓存或鸿蒙白名单。

Web 阶段更新先下载并解析新 GLB，旧宠物继续可见；请求带宠物/阶段序号，切宠或换装后旧结果失效。失败时保留当前模型；初次加载失败依次回退当前成年外观和旧备用模型，并显示提示。

公共 GLB 继续复用 `SelectedAssets` 的 IndexedDB、ETag/Last-Modified、损坏重下和取消逻辑。阶段使用独立 pathname，`?v=` 不是缓存身份。首页不预取四种宠物的所有阶段。

旅行与桌面由 `app/services/growth_asset_service.py` 在服务端读取同一清单，保持现有账号隔离和私人模型授权。

## 鸿蒙状态

`NativeAssets.ets` 已登记全部阶段公共资源、中心和三角形数；`NativeDenProtocol` 使用相同白名单。嵌入模式沿用 Web 世界变换，不乘预览缩放。

`static/js/den/native-den.js` 的 `PATHS` 目前为空，即默认 Web 绘制。只有 MatePad Air 上实际看到正确像素、透明合成、遮挡和生命周期后，才能逐路径开放。ArkTS/HAP 构建已成功，但真机启动时锁屏，尚未取得本次成长模型的真机证据。

本机构建命令（示例路径按本机环境）：

```powershell
$env:DEVECO_SDK_HOME='C:\Users\17958\AppData\Local\Programs\Huawei\DevEcoStudio\sdk'
$env:JAVA_HOME='C:\Users\17958\AppData\Local\Programs\Huawei\DevEcoStudio\jbr'
$env:PATH="$env:JAVA_HOME\bin;$env:PATH"
& "$env:LOCALAPPDATA\Programs\Huawei\DevEcoStudio\tools\hvigor\bin\hvigorw.bat" assembleHap --no-daemon
```

签名配置只使用本机已有内容，不读取、输出或提交。

## 验证命令

```powershell
$env:PYTHONPATH='.;test'
$env:GLM_API_KEY='offline-test-placeholder'
.\venv\Scripts\python.exe -X utf8 -m unittest discover -s test -p 'test_growth*.py'
.\venv\Scripts\python.exe -X utf8 -m unittest discover -s test -p 'test_portals.py'
node test/growth_assets.cjs
node test/growth_models.cjs
node test/growth_harmony_assets.cjs
node test/growth_runtime.cjs
node test/growth_haptics.cjs
node test/model_cache.cjs
node test/pet_grounding.cjs
node test/dog_locomotion.cjs
node test/locomotion_smoothness.cjs
node test/portal_navigation.cjs
node test/harmony_native_behavior.cjs
```

真实浏览器（Playwright 使用隔离测试环境，`PET_TEST_CHROME` 指向本机 Chrome）：

```powershell
$env:PET_GROWTH_SPECIES='cat' # 可改 shiba / husky / shepherd
node test/growth_motion_render.cjs
$env:PET_GROWTH_DEN_BASE='http://127.0.0.1:5012'
node test/growth_den_browser.cjs
node test/growth_performance.cjs
node test/pet_motion_render.cjs
```

测试服务必须使用临时 `DATABASE` 和 `GLM_API_KEY=offline-test-placeholder`，不能指向 `D:\PetChatSystem\book.db`。Chromium 动作测试逐段完整推进 35 个动作；`/den` 测试覆盖真实 API 阶段变化、缓存后刷新、失败回退、快速切宠和三种犬类。

## 本机 Chromium 性能对照

环境：隔离服务、1280×800、无头 Chrome、60 帧采样。以下是开发机对照，不是 MatePad FPS 或生产网络承诺。切换耗时包含真实 API、资源读取/解析和可见移交。

| 宠物 / 阶段 | 切换 ms | 帧时间 p50 / p95 / p99 ms | JS 堆 MiB |
|---|---:|---:|---:|
| 猫 幼年 | 1702 | 4.2 / 4.3 / 4.3 | 30.3 |
| 猫 少年 | 1443 | 4.2 / 4.3 / 4.3 | 30.7 |
| 猫 成年 | 1309 | 4.2 / 4.3 / 4.3 | 30.8 |
| 柴犬 幼年 | 1937 | 4.2 / 4.3 / 4.4 | 31.4 |
| 柴犬 少年 | 1193 | 4.2 / 4.3 / 4.4 | 31.6 |
| 柴犬 成年 | 1148 | 4.2 / 4.3 / 4.3 | 31.6 |
| 哈士奇 幼年 | 1657 | 4.2 / 4.3 / 4.3 | 32.5 |
| 哈士奇 少年 | 1181 | 4.2 / 4.3 / 4.3 | 32.6 |
| 哈士奇 成年 | 1203 | 4.2 / 4.3 / 4.3 | 32.7 |
| 德牧 幼年 | 1237 | 4.2 / 4.3 / 4.3 | 32.4 |
| 德牧 少年 | 1208 | 4.2 / 4.3 / 4.4 | 32.5 |
| 德牧 成年 | 1211 | 4.2 / 4.3 / 4.3 | 32.5 |

再次进入猫幼年耗时 1242 ms。连续 20 次幼年/成年切换后，几何资源计数为 65（前后相同），JS 堆从 32,906,483 到 33,307,536 字节，属于小幅波动；这不是长期稳定性验收。另一次前序对照保存在 `performance-baseline.json`，两次数据均只代表本机当时负载。

完整数据在 `art/pet-growth-v1/review/performance.json`。

## 回退与未完成项

- 无成长资料、私人外观、未支持外观及加载失败均保留旧路径；鸿蒙默认全部 Web 回退。
- 制作端初审通过，但独立美术终审尚未完成。
- MatePad Air `LRT-W20` 已连接，HAP 安装成功一次，但启动时锁屏。需要设备所有者解锁后重做原生像素、透明遮挡、互动、前后台和真机性能验收。
- 本任务未部署到 `D:\PetChatSystem`，未修改其数据库、配置或其他本地工作。
