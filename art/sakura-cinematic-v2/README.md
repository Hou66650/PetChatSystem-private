# 樱云长境：樱花岛客户端美术母版

本次交付是可编辑 Blender 场景与实际渲染审阅图。保留原樱花庭院作为抵达区，新增古樱主台地、茶亭、云端眺望台和静谧花园，桥与台阶连接四处空间。它不替换网页场景，也不读取账户植物、聊天或宠物数据。

## 审阅入口

- `index.html`：五张实际渲染与上一版空间对照。
- `sakura-archipelago.blend`：本地高精度、可编辑母版，纹理随原母版打包，体积较大，不纳入 Git。
- `build-report.json`：源资产及母版 SHA-256、渲染设备、图片摘要、几何统计、拟定游览路线。
- `validation.json`：在本机运行校验后的结果，本地忽略。

全景与树下镜头采用透视相机；茶亭、花枝近景和俯视使用正交相机，便于审阅结构。正式 PNG 为 2400 × 1800、128 samples、Cycles / OptiX。它们是模型渲染，不是生成式概念图。

## 建模及检查要点

1. 庭院、主台地、眺望台和静谧花园各有高度与用途，保留宠物生活尺寸的小屋、垫子、食水碗与玩具。
2. 曲面瓦片、顺屋面下置椽条、梁柱托架、木格栅、地板缝、桥面固定件、吊灯、茶具和根系台地均可编辑。
3. 樱花由有缺口与卷曲的五瓣、深色花心、花蕊和花梗构成，主枝、次枝与短花枝分层生长；特写花枝实际连接在主树上，未使用粉色球体或透明花冠卡片。
4. 新岩体有内收的侵蚀轮廓、连续顶沿、局部几何起伏和独立裂隙凹凸；复用并打包仓库已有 `art/mistwood-v1/limestone-albedo.png` 岩石纹理。前院的原围栏在新桥入口处开口。
5. 迭代中通过实际渲染修正了直枝聚束、花朵缺少花心、屋面椽条及托架穿插、岩壁顶沿漏缝和天空黑色地平线。瀑布由薄水幕、银色气泡线和落点薄雾组成；远景使用三层实际山体、有限范围的柔边体积云和大气衰减。
6. 材质保持深栗木、暗朱色柱、墨绿瓦、浓绿草地与有深浅变化的粉樱。石材保留较亮的自然反射，避免把全场简单压暗。

## 构建

使用 Blender 5.2.2 LTS。当前源母版为 `D:/PetChatSystem/art/cinematic-islands-v1/sakura/island-master.blend`，只读，生成目录独立。

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' -b --python-exit-code 1 --python scripts/blender/build_sakura_cinematic_v2.py -- --preview
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' -b --python-exit-code 1 --python scripts/blender/build_sakura_cinematic_v2.py -- --render-only
python scripts/validate_sakura_cinematic_v2.py
```

只重渲染单个镜头时，可增加 `--shot 03-tea-pavilion` 等参数。`--no-render` 只建立并保存母版。预览使用 1200 × 900、32 samples。

## 客户端接入边界

此母版优先提供细节与布局审阅，**不是已经通过实时性能验收的游戏关卡**。尚需完成：程序材质的 Unreal 等效重建或烘焙、按场景模块拆分、适宜的 Nanite/LOD 策略、植被阴影成本控制、碰撞、台阶高度及坡度校验、导航、宠物可交互点配置、流式加载和实际 GPU 帧时间测量。

`V2 06 Intended walking route markers` 中的 Empty 对象只是美术意图标记，不等同于可运行的导航网格。离线渲染速度不代表客户端 FPS。后续导入时保留母版，新建运行时派生资产，不能直接覆盖网页低配资源。

## 本轮仍需打磨的视觉项

远山轮廓仍偏风格化，地质细节与大气透视可以进一步自然化；瀑布虽已改为薄水幕，气泡线仍有较均匀的重复感，尚未做流体动态。此版用于用户审阅完整场景与工艺细节，不标记为“写实验收通过”或“电影资产终审”。
