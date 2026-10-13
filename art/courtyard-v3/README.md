# 樱花庭院：灯笼与栏杆 v3

网页版本 v1.5.5。延续现有樱花树与柴犬的柔和风格，升级庭院路灯和后方栏杆。

- 灯笼：八角石基、莲瓣承托、刻纹立柱、分层托盘、四面暖光窗格、樱花金属饰纹、曲面翘角屋檐与顶部饰件、底座苔藓。
- 栏杆：五根倒角立柱、石质柱脚、金属柱帽、黄铜销钉、横梁与斜撑、竖向格栅、几何木纹。
- 灯笼高度约 1.44 m；栏杆高度约 0.73 m。新几何合并为 11 个材质批次，约 35,828 个三角面；完整庭院 GLB 约 12.2 MB。
- 更新灯笼光源位置，基座避障半径 0.38 m；栏杆避障宽 3.7 m、厚 0.26 m。

## 文件

- `courtyard-v3.blend`：可编辑 Blender 工程，包含摄影棚灯光。
- `courtyard.png`、`lantern-detail.png`、`fence-detail.png`：实际 Blender 渲染。
- `../../static/models/petchat-courtyard-v3/sakura.glb`：网页资产。
- `build-report.json`：构建统计；本地 `validation.json` 为可重新生成的检查报告。

使用 `scripts/blender/build_courtyard_v3.py` 重建，`scripts/blender/validate_courtyard.py` 重新导入检查。通过用户指定的 Blender MCP 本地桥接执行，也可在独立 Blender 进程中用 `--background --python` 执行。脚本会清空其运行场景，不要在未保存的个人工程中运行。

新部件按材质合并以减少网页绘制次数；编辑时可在编辑模式按松散部件分离。窗面使用不透明暖色自发光材质，网页另配点光源，没有使用昂贵的体积光或透明玻璃叠层。渲染图和网页的光照条件不同。
