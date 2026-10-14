# 德牧 · 云岭守望营地

先用内置 imagegen 生成 `design-board.png`，再以 Blender 脚本实际建模。设计图表达构图、材质与细节方向，实际网页使用 GLB 网格，不把概念图当作模型。

- 德牧：重新制作连续体态、黑棕鞍状毛色、长口鼻、立耳、琥珀虹膜、双眼皮形变、护毛细线、爪趾与趾甲、下垂长尾、缝线项圈。继承成熟的45关节骨架与35段动作；这是风格化模型。
- 营地：半径5.6米，原活动岛半径3.2米。草地活动面积随半径扩大，后部山岩、松林、石塔与木屋形成高低层次；两岸有护栏、花草、长椅、路灯、石板桥和双侧瀑布。
- 导航：`alpine-layout.js` 与 Blender 共用尺寸；河面不能落脚，桥面可通行，建筑、树根、玩具柜、悬崖边缘有避让。大狗占用半径纳入过桥净宽。
- 加载：仅选中德牧才请求其狗、场景和当前昼夜背景，切换释放网格、骨架、材质与背景；场景按材质合批，瀑布使用既有时间 uniform 着色器，沿用自动清晰度与阴影预算。
- 可编辑原件：`shepherd-studio.blend`、`alpine-studio.blend`。实际模型预览：对应 PNG。`dog-report.json`、`stage-report.json` 为最终导出统计。
- 更多菜单中提供“近看德牧 / 营地全景”，650ms 缓动，尊重减少动态效果设置；直接拖动视角会取消镜头动画。

## 验证

`test/shepherd_alpine.cjs` 检查动作、骨架、睁眼默认值、体积预算、河流与障碍导航；`test/shepherd_geometry.cjs` 用真实 GLB 量取狗体半径并验证过桥净宽、射线采样桥面与导航高度、动画骨骼矩阵。`validate_shepherd.py` 从导出 GLB 重新导入，渲染跑动、坐姿和邀请玩耍姿态。既有哈士奇、动作、选中资源加载、玩具与性能预算测试均通过。

实际页面验证了昼夜背景、德牧表情、近景/全景、七种玩具列表、拿球后的沉浸模式。内置浏览器显示 Intel UHD 核显、自动流畅档约50 FPS；这不是 RTX 5060 上的实测值。

## 重建

Blender 5.2 执行 `scripts/blender/build_shepherd.py` 和 `scripts/blender/build_alpine_stage.py`。共享几何工具为 `shepherd_geometry.py`。狗骨架与动作来源为仓库现有 `petchat-motion-v1/xueqiu.glb`，外观网格重新制作。

## 图片提示词与产物

均使用内置 imagegen；背景只做 WebP 编码以便浏览器使用。设计图和背景文件已保存在项目中。

1. 设计图：professional 3D game production concept sheet for a beautiful German Shepherd companion and its monumental floating alpine island home; stratified cliffs, cascading waterfalls, tall pine forest, timber and stone alpine lookout lodge and tower, arched stone bridge, safe central grass area, lanterns, trail signs, wildflowers and toy cabinet. Warm stylized realism. German Shepherd tan and charcoal saddle coat, tapered black muzzle, amber eyes, pointed ears, layered neck ruff, lowered fluffy tail, toe pads and nails, teal collar with brass tag; head, paw and pose studies. Daylight plus blue-hour inset. No UI or watermark.
2. 白天背景：wide landscape background for a premium 3D companion pet alpine floating island scene; distant snow-touched mountain range above a sea of clouds, golden morning daylight, atmospheric perspective, lower two thirds luminous clouds and open space for a 3D island overlay; no foreground objects, dog, buildings, text or borders.
3. 夜晚背景：edit the day image, change only time of day to clear moonlit night; preserve mountain silhouette positions, cloud composition and framing; deep indigo sky, delicate stars, silver-blue moonlight, muted navy shadows, remove sun glow, subtle moon above peaks; no island, characters, buildings, text or UI.

背景：`static/textures/alpine-sky-v1/day.webp`、`night.webp`。预览参数：`/den?pet=4&scene=day` 或 `scene=night`。
