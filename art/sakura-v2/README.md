# 樱花庭院：树木重建 v2

本次在原庭院中重新制作樱花树，保持灯笼、围栏、地垫、食盆和球的位置。网页资产为 `static/models/petchat-sakura-v2/sakura.glb`，版本为 v1.5.1。

- 弯曲渐细的主干、七条根部支撑、多级分枝和纵向树皮起伏。
- 1,404 朵有缺口的五瓣花，使用珍珠粉、浅粉和少量玫红形成层次；添加花心、花蕊尖端、花苞和嫩叶。
- 不规则、留有空隙的花冠，树下散落花瓣；根部避障半径调整为 0.36 米。
- 树木按八种材质合并网格，约 13 万三角面；完整庭院 GLB 约 10.7 MB。花朵为实际几何，没有使用透明花冠贴片。

`sakura-v2.blend` 是可编辑源文件。`courtyard.png` 和 `tree-detail.png` 是真实 Blender 渲染。`build-report.json` 保存实际资产统计。所有图像均为模型实渲，本轮未使用 AI 概念图。

通过用户指定的 Blender MCP 插件本地连接执行 `scripts/blender/build_sakura_v2.py`。也可在独立 Blender 进程中运行：

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --python scripts/blender/build_sakura_v2.py
```

重建脚本会清空其运行场景，请在独立进程使用。随机种子固定，可重复生成同一棵树。当前为静态树木，网页原有飘落花瓣效果继续使用；未新增枝叶风摆动画。
