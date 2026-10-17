# 成长模型制作端初审记录

日期：2026-10-17。初审方式：Kimi 逐张查看 Blender 与 Chromium 实模图，不只依据脚本返回值。

## 结论

四种宠物的幼年、少年、成年静态造型通过制作端初审：头身比、口鼻、四肢和躯干均有物种内成长变化，毛色与身份一致；未发现多余肢体、双尾、明显接缝、材质丢失或整套模型仅靠缩放伪造的情况。

35 个动作均完成 Blender 中点联系表检查及 Chromium 完整推进检查。腋下、腹部、尾根、四肢和面部未见明显爆网格。柴犬、德牧成年另做了接地修正；德牧修正后动作采样最低点恢复为正值。

本结论是制作端初审，不代替 Codex 2 号/用户的独立美术终审，也不代替 MatePad Air 真机验收。

## 证据索引

- `cat-stages.png`、`cat-equal-height.png`
- `shiba-stages.png`、`shiba-equal-height.png`
- `husky-stages.png`、`husky-equal-height.png`
- `shepherd-stages.png`、`shepherd-equal-height.png`
- `{cat,shiba,husky,shepherd}-{juvenile,adolescent,adult}-{front,side,back,three-quarter}.png`：固定灯光和相机视角
- `cat-coats-{juvenile,adolescent}.png`：五种标准毛色联系表
- `{species}-{stage}-actions.png`：Blender 35 动作联系表
- `{species}-{stage}-browser-actions.png`：Chromium 35 动作联系表（猫）；犬类 Chromium 原始报告见下
- `browser-motion-{cat,shiba,husky,shepherd}.json`：每阶段 35 动作的加载、蒙皮边界、渲染三角形和 draw call 记录
- `performance.json`：12 阶段切换、60 帧采样及连续 20 次切换的本机 Chromium 数据
- 上级目录 `*-build.json`、`*-validation.json`、`*-motion-*.json`：构建、比例和 Blender 动作采样

真实 `/den` 截图保留在本机临时目录 `C:\Users\17958\AppData\Local\Temp\pet-growth-den-LTcVs1`，包含猫三阶段、柴犬幼年、哈士奇少年、德牧成年和加载失败回退。临时目录不是版本库交付的一部分，可重新用 `test/growth_den_browser.cjs` 生成。

## 已知限制

- 柴犬成年 `sleep_loop` 少量毛发采样最低点约 -5.5 mm，实模图未见明显穿地。
- 数值中的大边拉伸也存在于成年原资产的毛发，不能单独作为撕裂结论；最终以实际动作图和浏览器画面共同判断。
- 真机锁屏使原生同层像素与透明合成尚未验收。默认保持 Web 绘制。
