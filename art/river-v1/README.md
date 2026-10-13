# 河流与木拱桥

v1.7.0 庭院模型。可编辑源文件为 `river-bridge.blend`，网页资产为 `../../static/models/petchat-river-v1/sakura.glb`。

- 真正切开草坪与岛体的河道，水面位于地面下约 6 cm；石砌河岸、浅色波纹和岸边小植物。
- 2.3 m 长、1.9 m 宽的木拱桥，拱高 18 cm，30 块桥板、木纹、金属钉、立柱、双层扶手、格栅和石桥台。
- 树、路灯、栏杆、食盆及玩具保持原模型；坐垫缩小后移，为桥头让出空间。
- 38 个材质网格批次，完整庭院约 14.1 MB。水面使用不透明材质和静态细波纹，没有水体物理模拟。

`static/js/den/sakura-river-layout.js` 是模型与导航的共同尺寸来源（Three.js 坐标）。建模脚本转换为 Blender 坐标。河面禁止通行，桥宽扣除护栏和宠物安全半径后才允许通行；其他道具不会被桥面豁免。拖拽松手在下降前移到安全位置，落地高度包含桥拱。

重建：在专用空白 Blender 会话中通过 `scripts/blender/bridge.py scripts/blender/build_river_bridge.py` 执行。脚本清空当前场景，请先保存个人工程。

验证：

- `node test/river_navigation.cjs`：不同体型、两岸往返、随机行走、河面拒绝、护栏、安全放下与高度，检查超过 14,000 个采样/运动位置。
- `scripts/blender/bridge.py scripts/blender/validate_river_bridge.py`：重导入 GLB，逐网格检查保留道具，并对实际桥板和水面射线采样。
- `courtyard.png` 和 `bridge-detail.png` 是 Blender 实际渲染，光照与网页略有不同。
