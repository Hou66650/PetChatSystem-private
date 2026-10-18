# TECHATHON 提交材料生成

`content.json` 保存项目说明与 11 页、285 秒路演内容。成员资料与汤圆真实参考帧从仓库外传入，不写入本目录；输出 PDF、PPTX、录屏与最终 ZIP 同样保存在仓库外。

材料分为说明文档、项目内容、展示材料。代码通过私有仓库链接与固定基线提供，不把整个工作目录、数据库、签名证书、上传资料或大模型直接压缩。声明保留签名栏，评委权限与未核清的第三方来源必须如实标明。

## 制作

按 PDF 和 Presentations 技能要求记录创建操作，使用配套运行时。以新的私有目录作为 `BUILD`，输出目录作为 `OUT`。

1. 准备本地成员 JSON，结构为 `team_name`、`contact`、`members`；成员包含 `name`、`role`、`school`、`program`。未提供字段留空。
2. 使用 `test/imprint_review_server.py` 的隔离服务准备 `BUILD/assets/memory-detail.png`、`den.png` 和可选 `park.png`。不确认未经主人认可的动作或叫声，不把合成测试回忆当作真实素材。
3. 执行 `scripts/build_techathon_materials.py prepare --out OUT --build BUILD --team TEAM_JSON --reference REFERENCE_PNG --project-python PROJECT_PYTHON --ppt-master PPT_MASTER_ROOT`。调用 Python 需有 ReportLab；项目 Python 用于提取真实安装的依赖与许可证。
4. 按用户指定的本机 `D:/ppt-master-main/skills/ppt-master/SKILL.md` 制作 PPT。先确认设计并锁定 `design_spec.md` 和 `spec_lock.md`，再逐页读取锁文件、顺序编写 SVG。当前设计为 16:9、楷体标题、微软雅黑正文、夜蓝/奶油白/琥珀/深绿；仅使用真实参考帧、项目截图与既有品牌素材。
5. SVG 质量检查后生成 `notes/total.md`，分别运行 PPT Master 的 `total_md_split.py PROJECT`、`finalize_svg.py PROJECT`、`svg_to_pptx.py PROJECT -o PROJECT/exports/派特岛_五分钟路演.pptx -t fade -a fade --animation-trigger after-previous --animation-duration 0.4 --animation-stagger 0.3`。保留原生和 SVG 参考双版本。`content.json` 中的口播是本次审阅版本，不从旧大纲回填。
6. 运行 `scripts/finish_techathon_deck.py --project PROJECT --output OUT/03_展示材料/派特岛_五分钟路演.pptx`（Python 需有 python-pptx 和 lxml）。第 02 页嵌入 `PROJECT/images/five-islands-logo.mp4`，以 `opening-frame.png` 为封面，点击播放；不自动换页。脚本核验页数、原生文字、字体、转场、动画时间 ID、口播及嵌入视频字节。再用 PowerPoint 实际打开导出逐页 PNG 到 `BUILD/rendered/slide-NN.png` 并视觉检查；换电脑仍需彩排字体与媒体播放。
7. 将实际浏览器录屏转为 H.264/yuv420p MP4，保存为 `03_展示材料/回忆模块实机演示_标准柴犬载体.mp4`。检查时长、解码与真实性；Logo MP4 和 HTML 动画仍单独提供作备用，不宣称已制作完整汤圆四岛影片。附上 PPT Master MIT 许可，保留本地 SVG、设计说明和备注源文件。
8. 逐页检查 PDF，再执行 `scripts/build_techathon_materials.py finalize --out OUT --build BUILD`，生成预览、SHA-256 清单和 ZIP 并检查 CRC。后续修改任何交付文件后重新执行。

固定功能核对基线为 `cfe0c74`，与素材生成时的工作区截图分别理解。已有产品验收记录不代表本次重跑全部产品测试。不得提交包含成员个人资料或私人影像的构建目录。
