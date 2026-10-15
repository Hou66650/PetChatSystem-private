# 派特岛标准猫骨架 v1

模板源：`static/models/petchat-cat-v3/cat.glb`。`template.json` 记录 45 个关节的静止位置、父子关系、核心骨骼与 12 个动作名。运行适配时报告还会记录实际模板 SHA-256，便于追溯。模板本身复用现有模型，不再拷贝一份大体积 GLB。

## 已实现

- 兼容骨架：验证核心骨骼、层级、静止朝向和相对骨长，保留输入蒙皮并复用标准动作。自定义名称可通过 CLI 的 `--bone-map` 提供“输入名称 → 标准名称”JSON；这不是任意骨架的通用重定向。
- 无骨骼站立猫：显式选择 `template-skin`，将模板骨架和权重源适配到输入边界，使用 Blender 最近表面插值转移权重。输入几何不被压扁成模板。形变键和过大比例差异会拒绝处理。
- 动作：站立、走路、跑动、坐下、起身、趴下、休息、吃饭、嗅闻、伸展、左右转身。
- 输出：自包含 `adapted.glb`、可编辑 `review.blend`、模板清单和检查报告。报告采样四只脚的位置，但不据此宣称脚掌滑动已解决。
- 工作室使用一个本机后台工作线程，限制处理时长；原始模型保留。删除或更换模型后，旧任务不会重新写回结果。资产和下载仍仅对本人开放。

## 验收边界

模板蒙皮是草稿，不是视觉识别关节位置的通用自动绑骨。当前没有自动接触相位 IK、任意静止姿势重定向，也不会生成缺失的眼睑或口腔结构。需要检查腋下、腹部、尾根、脚掌，以及头部附属结构。所有结果默认 `readyForIsland=false`；用户勾选动作验收只记录检查结果，不自动启用到岛屿或桌宠。

## 本地运行

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' -b --factory-startup --python scripts/blender/adapt_cat.py -- input.glb uploads/my-cat-review
# 无骨骼站立猫：追加 --mode template-skin --forward=-Y
# 自定义关节名：追加 --bone-map bone-map.json
```

服务端可用 `BLENDER_EXECUTABLE` 指向自己的 Blender 可执行文件。仅支持 GLB；不接受用户提供的脚本或 Blend 文件执行。

## 复现测试

1. 在 Blender 后台运行 `test/blender_cat_adaptation_fixtures.py`，生成高身形、长身形和无骨骼变体。
2. 对 `uploads/cat-adapter-fixtures/tall.glb`、`long.glb` 分别适配到 `uploads/cat-adapter-check/tall`、`long`。
3. 对 `bare.glb` 使用 `--mode template-skin`，输出到 `uploads/cat-adapter-check/bare-v2`。
4. 对原始标准猫适配到 `uploads/cat-adapter-check/native-v2`。
5. Electron 运行 `test/cat_adaptation_render.cjs` 和 `test/pet_studio_render.cjs`，用本地文件检查实际 GLB 动作及工作室交互。
6. 设置 `PET_ADAPT_REAL_TEST=1`，运行 `python -m unittest discover -s test -p test_pet_studio.py`，验证隔离数据库下的真实后台 Blender 任务。

测试变体都由标准猫生成，用于验证实现，不代表已经验证真实照片重建模型。所有测试产物在忽略的 `uploads/` 内。
