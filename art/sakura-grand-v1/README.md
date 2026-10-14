# 大樱花主景 · v1.14.0

在 `petchat-toys-v1/sakura.glb` 的互动岛屿基础上，仅替换旧树的 8 个网格。桥梁、河流、瀑布、庭院与可拾取球保留原来的位置和交互元数据；玩具柜仍由前端单独加载。

- 15 组主枝，93 组花簇，4,929 朵五瓣花；含缺口花瓣、花心、花蕊、嫩叶、花苞与落瓣。
- 树的世界空间包围盒约 4.74 × 4.51 × 3.26（宽 × 高 × 深）。
- 438,361 个树三角面，8 个材质合并批次；整岛 GLB 40,761,840 字节。首次加载比旧岛更大，仍只加载当前选中的岛屿，继续使用自适应像素与阴影预算。
- 树根导航半径增至 0.55；樱花岛镜头重新构图，避开顶部选择栏并保留宠物、桥面和玩具柜视野。

## 文件

- `sakura-grand.blend`：可编辑 Blender 源文件。
- `courtyard.png`、`tree-detail.png`：Blender 渲染预览。
- `build-report.json`：构建统计。
- `../../static/models/petchat-sakura-grand-v1/sakura.glb`：浏览器运行资产。

在项目根目录使用 Blender 5.2 运行：

```powershell
& 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' --background --python scripts/blender/build_sakura_grand.py
node test/sakura_grand.cjs
```

验证覆盖树冠尺寸与批次数、所有旧岛非树对象的位置、球与瀑布元数据，以及相关导航、玩具、动作、按需加载、宽高比和渲染预算回归。浏览器另检查日夜实景；没有将内置浏览器帧率作为用户 Chrome / RTX 5060 的性能测量。
