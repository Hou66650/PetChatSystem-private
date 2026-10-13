# 空岛双侧瀑布 v1

v1.7.2，在原有河流与木桥模型上延伸两侧出口，保留庭院的 38 个原网格。新增 14 片连续入口、末端错落分离的水帘，以及银亮细流、破碎水沫、水滴和透明薄雾，共 18 个新增网格批次。完整 GLB 约 15.4 MB。

- `waterfalls.blend`：可编辑源文件。
- `courtyard.png`、`waterfall-detail.png`：Blender 实际渲染。
- `../../static/models/petchat-waterfalls-v1/sakura.glb`：网页模型，包含流向 UV、部件角色及打包的水雾纹理。
- `../../static/js/den/waterfall-flow.js`：运行时高光流动与微小水帘摆动。水滴与雾的形状由模型提供；这是轻量视觉效果，不是流体物理模拟。

尺寸从 `static/js/den/sakura-river-layout.js` 读取。河水高度 -0.055 m，沿半径 3.2 m 的圆形岛缘接出，主水帘下落约 1.0–1.5 m，末端水滴和雾渐散。导航未增加任何可行走区域。

在独立 Blender 会话运行 `scripts/blender/build_waterfalls.py` 重建（会清空当前场景）。通过 `scripts/blender/bridge.py` 可调用已连接的 Blender MCP。执行 `scripts/blender/validate_waterfalls.py` 验证 GLB 回读；旧网格采用双向点云 0.01 mm 容差以允许浮点重导出误差。

验证命令：`node test/waterfall_flow.cjs`、`node test/river_navigation.cjs`、`node test/shiba_expression.cjs`。网页还需检查实际着色器编译与日夜背景显示。
