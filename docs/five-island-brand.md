# 五岛爪印 Logo 与路演转场

## 设计

保留 F4 的手绘圆润 `pet` 路径、奶油白、夜蓝渐变与 e 中的琥珀色光点。移除下方小猫、小屋和单岛装饰，换成更大的五块爪垫轮廓。四枚趾垫分别对应四座生活岛，中央掌垫对应爪心乐园。保留岛屿方位关系，圆润化和向心收拢属于品牌抽象，不声称轮廓与地图逐像素相同。

| 岛屿 | 当前世界 X / Z | 图标位置 |
| --- | --- | --- |
| 樱花庭院 | -15 / 0 | 左侧趾垫 |
| 雪境木屋 | -6 / -10 | 左上趾垫 |
| 雾林温室 | 6 / -10 | 右上趾垫 |
| 山岭营地 | 15 / 0 | 右侧趾垫 |
| 爪心乐园 | 0 / 11 | 下方掌垫 |

## 文件与使用

- `static/images/pait-app-icon-f5.svg`：主矢量图标。对应 1024、512、180、32 PNG；180 尺寸补齐 Apple touch icon。
- `static/brand/five-islands/logo-transparent.svg` / `.png`：透明 Logo，适合深色 PPT。`logo-ink.svg` 适合浅色背景。
- `static/brand/five-islands/five-islands-logo.mp4`：1920 × 1080、30 FPS、9 秒、H.264、无声，可直接插入 PowerPoint / WPS。
- `static/brand/five-islands/index.html`：离线可打开的播放、暂停、拖动和全屏预览；保留同目录 JS 和图片。也可通过应用 `/static/brand/five-islands/index.html` 打开。
- `opening-frame.png`、`outline-frame.png`、`ending-frame.png`：剪辑衔接和静态备用画面。

PPT 将视频铺满 16:9 页面并设置自动播放；不用额外添加旋转、弹跳或擦除。下一页可以沿用结束帧做短淡化。无音轨，方便配合主人讲述或现有音乐。尚未制作整场 PPT，也未将前段汤圆四岛跟随影片剪入本视频。

## 时间线

0–1.2 秒：真实五岛模型的正俯视渲染。1.2–2.8 秒：沿岛屿外沿描线。2.4–3.8 秒：模型细节淡出。3.2–6 秒：轮廓逐点插值，收成圆润爪印。5.7–7.1 秒：`pet` 和光点显现。7–9 秒：出现中文名并停留。

五岛图来自本地 GLB 的正交渲染，不使用想象图替代。轮廓按渲染 alpha 径向采样；生成的 PNG、128 点轮廓与源模型 SHA256 固定在 `island-data.js` 中，播放不再依赖大型 GLB。中央乐园使用当前工作区 v3 preview；这些冻结图可以独立发布，v3 模型文件由乐园开发另行维护。

## 生成与验证

使用项目 Node.js，`NODE_PATH` 提供 `@resvg/resvg-js` 与 `playwright`：

```powershell
node scripts/build_paw_brand.cjs            # 生成 SVG、PNG、鸿蒙图标
node scripts/build_paw_brand.cjs --capture  # 重新取五岛正俯视；需本地 GLB
node scripts/export_paw_film.cjs            # 按固定时间轴导出 MP4
```

导出器使用 Chromium 计算 SVG 形变，再由 Resvg 渲染帧、FFmpeg 编码，避免网页录屏的实时卡顿。FFmpeg 默认来自项目 venv 的 imageio-ffmpeg，也可用 `FFMPEG_PATH` 指定；Chrome 可用 `PET_TEST_CHROME` 指定。

网页导航、登录、关于、观察台、路演入口和 Electron 窗口引用已切到 F5；鸿蒙 AppScope 引用改为 `app_icon_paw`。旧版文件保留用于历史回溯。本次不打包、安装鸿蒙或 Electron 应用，设备图标需重新构建安装后更新。
