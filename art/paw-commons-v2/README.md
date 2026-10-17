# 爪心乐园第二版：从效果图到可编辑三维设计

本版由 Codex 接手。四座生活岛继续沿用，不重建。

- `design/01-overall-concept.png`：整体效果概念，使用内置 imagegen 生成。
- `design/02-facility-details.png`：六类设施的材质、连接和剖面视觉参考，使用第一张图保持设计语言。
- `design/layout.json`：人工落实的游戏场景尺寸、分区和坐标；图像中的结构不视为工程测量依据。

概念图的目的是真实自然材质与克制的可爱细节；不得把概念图当成已经实现的游戏截图。尺寸用于虚拟场景，不是现实施工或动物设施安全认证。

## 精细三维成果

- `paw-commons-detailed.blend`：精细母版，保留分组、可编辑几何、木件倒角和摄影灯光。
- `../../static/models/paw-commons-v2/park-detailed.glb`：可旋转检查的真实模型，约 177 万三角面、84.6 MB；用于设计审阅，不直接部署到鸿蒙。
- `review/06-detailed-overview.png`：实际母版整体渲染。
- `review/07-detailed-tunnels.png`：双隧道、草坡及低桥实际渲染。
- `review/08-detailed-treehouse.png`、`09-detailed-canopy.png`：设施研究图，暂时隐藏树冠以核对结构；完整模型保留植被。
- `design/layout-detailed.json`：精细版名义尺寸、平台高度、第二隧道与中央树坛避障范围。
- `design/03-dimensions.svg`：五岛关系、乐园分区、隧道与桥尺寸图。四座生活岛仍引用原资产，本稿没有重新制作它们。
- `detailed-build-report.json`：导出后的真实面数、字节数与 SHA-256。
- `review/browser-validation.json`：实际浏览器加载、几何有限值、边界和审阅页检查结果。

细化内容包括：双端贯通的橡木隧道与有肩部坡度的覆草丘、逐板低桥、叶形踏台、连续台阶、螺旋麻绳、双圆门木屋、分层屋面、叶形遮棚主梁与肋条、座椅、饮水排水板、收纳柜、爪印铺装、灯具、紧固件、分枝树冠、草簇、花境和垂藤。模型与图像均由本项目生成，无外部付费模型或私人宠物资产。

## MCP 制作与复现

使用 [MCP for Blender](https://github.com/ahujasid/mcp-for-blender) 的真实 stdio MCP 服务、`execute_blender_code` 工具及 Blender 插件执行；不是把普通后台脚本执行标为 MCP。插件仅在独立 Blender 会话中监听 `127.0.0.1:9876`，遥测关闭。

1. 用 Blender 5.2 运行 `scripts/blender/build_paw_commons_v2.py -- --render`，生成基础尺寸稿。
2. 将官方插件 `addon.py` 放在本机忽略目录 `uploads/blender-mcp/addon.py`。本次复用已有安装副本，未修改全局 Blender 配置。
3. 用 Blender `--background --factory-startup --python scripts/blender/paw_mcp_headless.py` 启动独立制作会话；它在主线程处理官方插件的命令队列。
4. `uvx --from mcp-for-blender==2.1.9 python scripts/blender/paw_mcp_client.py scripts/blender/detail_paw_commons_mcp.py` 派发精细建模、保存和导出。
5. 同样通过 MCP 派发 `scripts/blender/present_paw_commons_mcp.py`，补充摄影环境和设施研究视图。云层仅保留在 Blender 摄影工程，不写入 GLB。

首轮图形会话导出遇到上下文缺失，已通过明确的视图上下文修复。后续一次渲染会话退出，已保留导出结果并改用独立后台 MCP 会话完成摄影。

## 审阅与验证

运行 `venv/Scripts/python.exe scripts/review_paw_commons.py`，打开 `http://127.0.0.1:5089/art/paw-commons-v2/index.html`。服务仅监听本机，路径白名单不提供 `.env`、数据库或其他项目文件。审阅页按需加载模型，视角变化时才重绘。

安装 Playwright 后运行 `node test/paw_design_review.cjs`。截图保存在忽略目录 `uploads/park-review`。

## 当前边界

这是高精度设计母版，不宣称百分之百复刻概念图。概念图中的自然植物形态、地形起伏和真实材质仍有差距；已用实际模型渲染供逐项对照。运行版已接入当前代码的首页和 `/park`，见下节；设施专属互动、宠物之间的实体碰撞、移动端 GPU 压缩贴图和鸿蒙真机帧率验收尚未完成。四座生活岛模型没有修改。

基础稿 `paw-commons.blend`、`park.glb` 与旧渲染仅保留作设计演进对照，最新审阅入口默认打开精细母版。

本次环境：Blender 5.2.2 LTS、MCP for Blender 2.1.9、插件 1.8 / protocol 13。插件本机文件 SHA-256：`eb0facf69781a30e69792532087d8d41c6a14fcd323353250abe7988ee297fa5`。`review/structure-validation.json` 记录 MCP 内的隧道通路与树屋门前平台射线检查。

## 运行场景接入

沿用上述 MCP 会话，用 `paw_mcp_client.py scripts/blender/build_paw_runtime_mcp.py` 从精细母版导出两级静态场景。按完整植株组件疏密处理叶片，降低岩石和曲面面数，保留设施、草坪与环路轮廓，按材质合并并保留 UV。母版不修改。

| 用途 | 文件 | 三角面 | 网格/材质批次 | GLB / gzip 传输 |
| --- | --- | ---: | ---: | ---: |
| 首页中央岛 | `preview.glb` | 156,274 | 19 | 7.14 / 3.50 MB |
| 公共乐园 | `play.glb` | 442,738 | 19 | 19.90 / 8.75 MB |

资源位于 `static/models/paw-commons-v2`，SHA-256 和真实字节数见 `runtime-report.json`。服务器按 Accept-Encoding 提供 gzip，保留 ETag 和 Vary；浏览器复用现有 IndexedDB 模型缓存，命中后条件验证。场景未就绪时禁用入园，失败显示重试。无人且视角静止时停止提交画面，有宠物时上限 30 FPS；这不是实测真机帧率承诺。

`navigation.json` 同时驱动浏览器 A* 路线和服务端位置/线段校验，绕开中央树坛及活动区边缘的隧道、饮水区和坡道。点击不可通行处会投影到可达草坪；原有打招呼、玩球、闻闻、休息和多人同步继续使用。设施现阶段是精细场景，尚不能让宠物自动钻洞、登树屋或通过桥梁。

验证命令：`node test/park_runtime_assets.cjs`、`node test/park_navigation.cjs`、`node test/selected_assets.cjs`、`venv/Scripts/python.exe -X utf8 -m unittest discover -s test -p test_park.py -v`。启动隔离的 `test/park_review_server.py` 后，运行 `test/public_park_render.cjs` 和 `test/park_runtime_browser.cjs` 做双账号、导航、失败重试和缓存检查。测试服务只监听本机 5088，使用临时数据库；不能把它作为正式服务部署到局域网。

本批接入在当前仓库的隔离开发预览完成；`D:\PetChatSystem` 的旧运行目录有大量未同步修改，未整目录覆盖，也未更新平板连接的 5005 服务。上线前需先完成该运行目录的差异合并和鸿蒙真机验收。
