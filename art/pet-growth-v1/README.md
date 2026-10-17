# 派特岛成长独立模型 v1

本目录保存四种宠物幼年、少年及部分成年修正资产的可编辑来源和审核证据。模型只使用项目现有标准 GLB，没有读取或包含私人照片、私人模型、数据库或账号数据。

## 造型与资源覆盖

幼年/少年均从各物种自己的成年网格重新变形：改变真实顶点、形态键和 45 个关节的静止位置，再重定向动作位移并逐帧烘焙接地。不是复制 GLB 后修改对象缩放。成年猫和哈士奇复用现有合格资产；柴犬、德牧成年保留原几何，但重新烘焙接地，因此使用独立修正文件。

| 宠物 | 幼年 | 少年 | 成年 | 标准外观 |
|---|---:|---:|---:|---|
| 柴犬 | `.64` / `pet-growth-v1/shiba/default-juvenile.glb` | `.82` / `default-adolescent.glb` | `.95` / `default-adult.glb`（接地修正） | 默认橘白柴犬 |
| 哈士奇 | `.72` / `pet-growth-v1/husky/default-juvenile.glb` | `.91` / `default-adolescent.glb` | `1.05` / 原 `petchat-husky-v3/xueqiu.glb` | 默认黑白哈士奇 |
| 猫咪 | `.58` / `pet-growth-v1/cat/*-juvenile.glb` | `.72` / `*-adolescent.glb` | `.85` / 原 cat-v3 与 coats-v1 | 狸花、橘猫、奶牛、三花、布偶 |
| 德牧 | `.76` / `pet-growth-v1/shepherd/default-juvenile.glb` | `.96` / `default-adolescent.glb` | `1.12` / `default-adult.glb`（接地修正） | 默认黑背德牧 |

`static/data/pet-growth-models.json` 是 12 条“宠物 + 阶段”配置的正式清单，记录每个标准外观的独立路径和 SHA-256。猫的每条配置含五种毛色，合计 24 个可解析阶段资源路径（含成年复用路径）。私人工作室模型不在公共清单内，始终保持私人身份。

每套新阶段保持原三角形数、材质与 35 个动作：柴犬 160,839、哈士奇 169,146、猫咪 154,155、德牧 163,530。只加载当前阶段，不常驻三套模型。所有文件小于鸿蒙当前 32 MiB 下载上限。

## 可编辑来源

- `cat-juvenile.blend`、`cat-adolescent.blend`
- `shiba-juvenile.blend`、`shiba-adolescent.blend`、`shiba-adult.blend`
- `husky-juvenile.blend`、`husky-adolescent.blend`
- `shepherd-juvenile.blend`、`shepherd-adolescent.blend`、`shepherd-adult.blend`
- `*-build.json`：来源、参数、静止边界、脚骨权重覆盖、文件大小和哈希
- `*-validation.json`：等身高头身比、腿比例、躯干比例
- `*-motion-*.json`：Blender 实际蒙皮动作采样

`.blend` 使用 Blender 压缩保存；猫毛色 GLB 由 `scripts/build_growth_cat_coats.py` 从对应阶段的实际几何分别生成，布偶另有长毛顶点位移。

## 重建

在项目根目录使用 Blender 5.2：

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' -b --factory-startup --disable-autoexec --python scripts/blender/build_pet_growth.py -- --species cat
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' -b --factory-startup --disable-autoexec --python scripts/blender/build_pet_growth.py -- --species shiba
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' -b --factory-startup --disable-autoexec --python scripts/blender/build_pet_growth.py -- --species husky
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' -b --factory-startup --disable-autoexec --python scripts/blender/build_pet_growth.py -- --species shepherd
```

成年接地修正可单独重建：`--species shiba --stages adult` 或 `--species shepherd --stages adult`。

毛色构建使用项目既有顶点色规则，构建环境需要 NumPy 与 Pillow；NumPy 是美术构建依赖，不是 Flask 新增运行依赖：

```powershell
.\venv\Scripts\python.exe -m pip install numpy
.\venv\Scripts\python.exe -X utf8 scripts/build_growth_cat_coats.py --source static/models/pet-growth-v1/cat/tabby-juvenile.glb --stage juvenile
.\venv\Scripts\python.exe -X utf8 scripts/build_growth_cat_coats.py --source static/models/pet-growth-v1/cat/tabby-adolescent.glb --stage adolescent
```

静态对比和动作采样：

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' -b --factory-startup --disable-autoexec --python scripts/blender/validate_pet_growth.py -- --species cat --views
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' -b --factory-startup --disable-autoexec --python scripts/blender/validate_pet_growth.py -- --species cat --motion
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' -b --factory-startup --disable-autoexec --python scripts/blender/render_pet_growth_actions.py -- --species cat --work "$env:LOCALAPPDATA\Temp\pet-growth-actions-cat"
```

`validate_pet_growth.py` 的 `ASSETS` 是审核取景清单，不是 Web 运行时解析器。运行时以 `static/data/pet-growth-models.json` 为唯一资源清单。

## 审核结论与限制

`review/README.md` 记录制作端人工初审和证据索引。三阶段外形、毛色、等身高差异和 35 动作均经过实模图检查；不是只用数值检查代替美术审核。

- 柴犬成年 `sleep_loop` 的少量毛发采样最低点约 -5.5 mm，实模图未见明显穿地；保留为已知边界项，后续美术终审可继续调整。
- MatePad Air 真机仍被锁屏，尚未完成原生同层像素、遮挡和长期生命周期验收。默认 `static/js/den/native-den.js` 保持 Web 绘制。
- 独立美术终审和真机验收未完成前，不应把本目录描述为全任务最终放行。
