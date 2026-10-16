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

以上 v1.58.2 记录覆盖原生模型与独立渲染场景；当时未加载上传模型。后续私有样本覆盖见下方。两轮均未测试登录、实时语音、完整小岛页面或真实桌宠窗口，不能扩大为这些场景的验收结论。

## 上传模型（v1.58.3）

本机部署数据位于 `D:\PetChatSystem\book.db`，与当前开发检出目录不同。模型保存在 `pet_studio_assets.data`，应测试已完成适配的 `adapted` 槽；原始 `model` 槽可能没有骨骼与动画。读取数据库须用 SQLite 只读连接，将测试副本放到临时目录，不改装备状态、验收状态或用户数据，不把副本提交到 Git。

对每份本地已适配 GLB 分别运行：

```powershell
$env:PET_MOTION_TEST_GLB = '填写临时测试副本的绝对路径'
$env:PET_GROUNDING_TEST_GLB = $env:PET_MOTION_TEST_GLB
$env:PET_FEEDING_TEST_GLB = $env:PET_MOTION_TEST_GLB
$env:PET_LIFE_TEST_GLB = $env:PET_MOTION_TEST_GLB
$env:PET_PORTAL_TEST_GLB = $env:PET_MOTION_TEST_GLB
node test/pet_grounding.cjs
node test/cat_feeding_station.cjs
node test/cat_life.cjs
node test/portal_navigation.cjs
node test/pet_motion_render.cjs
```

渲染脚本仍使用前述 Playwright/Chrome 配置。设置 `PET_MOTION_TEST_GLB` 后，只加载该私有文件，并按小窝的 `custom` 流程处理：保留绑定姿态、测量变形后的网格边界、关闭原生专用表情、以 walk 复用小跑动画。额外生成坐姿、睡姿、进食、嗅闻、伸展及食盆站位截图；HTTP 只提供这个指定的私有文件，不开放私有目录。

2026-10-17 验证了数据库中两份 `reviewed` 样本：当前使用的灰猫及另一份小狗外形的模板适配模型。上述测试全部通过，并检查了运动与姿态截图。两份过桥贴地最低采样间隙约 3 mm；加强前腿采样后，食盆架最小测得距离分别约 15 mm、88 mm。浏览器复现并修复了 walk/trot 复用片段的步频突降，`maxAliasCadenceError` 修复后接近浮点误差。

另外一份原始上传 GLB 没有 skin/动画，数据库状态为 `needs_manual`，适配报告提示外形或朝向与站立猫模板差异过大。它没有可测试的运动片段，保持原状态，需要人工校正朝向或关节，未视为运动通过。两份已适配模型的技术检查通过也不代表任意上传模型自动可用；尤其小狗模板样本的脚部蒙皮权重较分散，精细动作质量仍受原始适配结果约束。
