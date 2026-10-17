# 汤圆：实拍衔接与真实庭院审阅

这些脚本用于本地影片制作，不替换账号模型，不上传参考视频，也不自动提交新的云端建模任务。原始视频、标注、FBX、Blender / UE 工程及输出帧保留在仓库外。

## 制作顺序

1. 用 `scripts/blender/refine_tangyuan_match.py --input <已校正头颈的 neutral.blend> --output <本地目录>` 收窄前肩、同步毛发，并添加小幅下颌和舌尖绑定。不要再次对已校正资产执行 90° 头颈纠正。
2. 用 `scripts/blender/match_tangyuan_transition.py --input <refined-neutral.blend> --motion <motion.json> --output <matched目录>` 烘焙动作。`jaw_open` 是下颌局部 X 轴弧度，`tongue_extension` 是舌骨局部 Y 轴缩放；其他身体和相机轨迹沿用已审核拟合。
3. 用 `scripts/blender/export_tangyuan_island.py --island <项目sakura.glb> --character <matched.blend> --output <island目录>` 导出实际庭院，并搜索整段动作可用的落脚区。它保留原场景，导出副本围绕角色重新定位，因此不需要改动已匹配的动作和机位。
4. 在独立 UE 工程中启用 Python、Editor Scripting Utilities、Sequencer Scripting 和 Movie Render Pipeline。环境变量 `TANGYUAN_SHOT_CONFIG` 指向本地 JSON，再通过 `-ExecCmds="py <绝对路径>/scripts/unreal/tangyuan_match_review.py" -unattended -RenderOffscreen` 运行。
5. 完成实际渲染后，用 `scripts/build_tangyuan_match_review.py --revision sakura --source <实拍.mp4> --output <本地目录> --frames <此次帧目录> --motion <motion.json>` 生成原速硬切、四倍慢放和逐帧叠加页。目录内还需放置同机位的 `neutral-front.png`、`neutral-corrected.png`。当前打包器专用于 30 fps 源帧 42–71、切点 54，不接受任意视频时间范围。

Blender 脚本通过 `blender --background --python-exit-code 1 --python <脚本> -- <参数>` 执行。

## UE 本地配置

必填 `fbx`、`motion`、`output`；每轮使用新的 `asset_folder` 和 `frames_directory`。真实庭院配置如下：

```json
{
  "island": {
    "fbx": "<island目录>/Sakura.fbx",
    "materials": "<island目录>/materials.json",
    "asset_name": "SakuraIslandRevision"
  },
  "map_name": "SakuraMatchLevel",
  "sequence_name": "SakuraMatchedTransition",
  "exposure": 1.25,
  "sun_intensity": 3.0,
  "fill_intensity": 3.0,
  "sky_intensity": 1.5
}
```

只有材质与贴图完全未变、仅重新定位岛屿时，才使用 `island.reuse_materials: true`。其他情况重新生成材质。天空使用本地渐变穹顶，避免浮岛下半球显示空黑背景。

可另运行 `scripts/unreal/tangyuan_island_overview.py`，读取同一配置，保存独立全景关卡、序列和一张布局图；这不代表已完成从近景到全景的连续运镜。批次输出目录必须为空，避免旧帧被计入成功结果。

## 验收范围

- `pose-validation.json` 检查每个姿态的 IK、网格有限数值和严重拉裂。通过不等于解剖形态或运动捕捉精确。
- `placement-validation.json` 检查最低点和低处表面的地面距离、每 20 个顶点的障碍物邻近距离、四个关节及每 200 个表面顶点的相机视线。它属于镜头采样检查，不替代逐帧目检和完整碰撞检测。
- `unreal-report.json` 必须记录实际 MRQ 成功及 30 张输出帧。FBX 的第 31 个包端点不渲染，避免片尾回跳。
- 检查首帧、切点、末帧、原速与慢放。嘴内部及被遮挡的腿部仍是推定；需继续核对毛色、肩颈、落脚和个体相似度。
- 单独记录引擎启动自检、材质编译、内存和渲染错误；进程退出或导入成功都不能替代画面验收。
