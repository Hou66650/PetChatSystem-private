# 宠物动作实模验证

GLB 已在仓库跟踪。若代码存在但模型目录为空，先检查 `git sparse-checkout list` 与 `git ls-files -t -- static/models`；`S` 表示文件被稀疏检出排除，不能据此判断仓库缺模型。

在已启用非 cone 稀疏检出的工作区，补入本套测试需要的模型：

```powershell
git sparse-checkout add --skip-checks '/static/models/petchat-motion-v1/*.glb' '/static/models/petchat-v3/*.glb' '/static/models/petchat-husky-v2/*.glb' '/static/models/petchat-cat-v3/*.glb' '/static/models/petchat-cat-v2/*.glb' '/static/models/petchat-cat-home-v1/*.glb' '/static/models/petchat-mistwood-v1/*.glb' '/static/models/petchat-shiba-v4/*.glb' '/static/models/petchat-husky-v3/*.glb' '/static/models/petchat-shepherd-v2/*.glb' '/static/models/petchat-cat-coats-v1/*.glb'
```

数值与骨骼回归，不依赖浏览器：

```powershell
node test/locomotion_smoothness.cjs
node test/dog_locomotion.cjs
node test/portal_navigation.cjs
node test/pet_grounding.cjs
node test/cat_life.cjs
node test/cat_feeding_station.cjs
```

带贴图实模渲染需要 Node 可解析 `playwright`。可通过 `NODE_PATH` 指向已有工具环境的 `node_modules`；浏览器由 Playwright 提供或通过 `PET_TEST_CHROME` 指定，不使用日常浏览器个人资料。

```powershell
$env:PET_TEST_CHROME = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
$env:PET_TEST_VIDEO = '1' # 可选：额外录制四种宠物的连续运动
node test/pet_motion_render.cjs
```

脚本使用仅监听 127.0.0.1 的静态测试服务，加载仓库原始 GLB 和内嵌贴图，提取 `templates/den.html` 的 `playAction` 函数，配合实际运动控制、视线、表情及猫咪贴地模块。输出目录由终端打印，包含 16 张阶段截图、JSON 报告，以及启用录像时的四段 WebM；均写入系统临时目录。

2026-10-16 / v1.58.2 验证结果：以上全部通过。犬类 45 个关节与 35 个片段检查通过；8 个原生/毛色 GLB 在 32 组岛屿/体型组合中可通行；猫咪过桥四方向、猫窝睡姿、吃喝与打断后退通过，贴地最低采样间隙约 3 mm，食盆架前腿最小测得间距约 12 mm。四种宠物的渲染、有限骨骼值、转速与命令切换加速度检查通过，截图和录像抽帧未发现明显姿态突变。

这套检查覆盖原生模型与独立渲染场景。未加载用户上传模型，也未测试登录、实时语音、完整小岛页面或真实桌宠窗口。不要把上述通过项扩大为这些场景的验收结论。
