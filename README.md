# MPC 宠物聊天系统（重构版）

情绪陪伴向的宠物角色聊天系统：用户与多只拟人化宠物（柯基/萨摩耶/猫咪/德牧）对话，
支持头像 AI 动漫化、聊天日记、宠物评分，并保留了旧图书借阅管理功能。

- **后端**：Flask 3 + SQLite，应用工厂 + 蓝图分层
- **AI**：智谱 GLM（OpenAI 兼容协议直连），`glm-4.5-flash` 对话 + `glm-4v-flash` 识图 + `cogview-3-flash` 画图
- **密钥管理**：全部走 `.env` 环境变量，代码中不含任何密钥

## 快速开始

```bash
pip install -r requirements.txt      # 仅需 flask + requests
cp .env.example .env                 # 填入 GLM_API_KEY（开发机 .env 已配好）
python run.py --init-db              # 首次运行：建表（幂等，不动存量数据）
python run.py                        # 启动 http://127.0.0.1:5000
```

跑回归测试（需服务已在 5000 端口运行，会真实调用 GLM）：

```bash
python test/refactor_e2e.py
```

## 目录结构

```
run.py                  启动入口（--init-db 建库）
.env / .env.example     配置与密钥（.env 不进 git）
app/
  config.py             全部配置项集中定义，环境变量可覆盖
  db.py                 SQLite 访问层（连接/查询/执行/初始化）
  decorators.py         登录校验装饰器
  schema.sql            建表脚本（幂等）
  llm/
    client.py           GLMClient：对话/识图/画图，带重试+并发上限
    pets.py             宠物角色注册表（data/pets/petN.json 白名单加载）
  services/
    chat_service.py     聊天编排：角色提示词+历史清洗截断
    avatar_service.py   头像管线：上传→4V描述→CogView生成→落盘
  routes/
    main.py             首页/关于/登出/静态资产代理
    auth.py             读者与管理员的登录注册
    chat.py             聊天页/AI对话/头像/日记/评分
    reader.py           读者侧（个人中心/检索/借阅）
    manager.py          管理员侧（图书与用户管理）
data/pets/pet*.json     宠物角色配置（人设/头像/背景/默认评分）
uploads/avatars/        用户上传原图 + AI 生成头像（运行时产物）
templates/ static/      页面与资产（沿用旧版，模板端点已加蓝图前缀）
test/refactor_e2e.py    端到端回归测试
book.py                 旧入口已退役，运行会提示改用 run.py（旧代码在 legacy/book.py）
```

## 配置项（.env）

| 变量 | 默认值 | 说明 |
|---|---|---|
| `GLM_API_KEY` | 无（必填） | 智谱开放平台 Key |
| `GLM_BASE_URL` | `https://open.bigmodel.cn/api/paas/v4` | 可换任何 OpenAI 兼容服务 |
| `GLM_MODELS` | `glm-4.5-flash` | 对话模型白名单（逗号分隔），前端下拉框由此生成 |
| `GLM_VISION_MODEL` | `glm-4v-flash` | 识图模型（头像管线第一步） |
| `GLM_IMAGE_MODEL` | `cogview-3-flash` | 文生图模型（头像管线第二步） |
| `SECRET_KEY` | dev 默认 | 生产环境务必更换 |
| `LLM_MAX_CONCURRENCY` | `2` | LLM 并发上限（信号量） |
| `LLM_MAX_RETRIES` | `3` | 网络错误/限流/5xx 重试次数 |
| `LLM_TRUST_ENV` | `0` | 是否走系统代理；bigmodel.cn 国内直连建议 0 |

## 宠物角色管理

新增/修改宠物只需编辑 `data/pets/petN.json`：

```json
{
  "id": 1, "name": "柯基", "role": "一只活泼的柯基",
  "description": "人设描述（进 system prompt）",
  "avatar": "f.png",        // 聊天页头像，放 templates/images/
  "background": "css/b.jpg", // 聊天页背景，放 templates/css/
  "rating": 4.0              // 首页展示的默认评分（有真实评分后自动被平均分取代）
}
```

前端不再传角色文件路径（旧版有路径遍历风险），只传 `petId`，后端按编号白名单加载。

## 相比旧版（book.py）的主要变化

1. **AI 接入切换为智谱 GLM 直连**（原先走 OpenAI 中转站，密钥硬编码在代码里，已全部移除）
2. 单文件 830 行拆为 config / db / llm / services / routes 分层，蓝图注册
3. 修复：AI 历史消息被当成用户发言（记忆错乱）、头像硬编码 `D:\` 路径、
   启动即清空 borrows/histroys、消息内容 XSS、宠物头像永远显示默认图、
   宠物评分页 404、未登录访问读者页 500 等问题
4. 头像动漫化改为两步管线（4V 描述照片 → CogView 生成），输出带审核误伤降级重试
5. 聊天历史按条数截断（默认 20 条）送入模型，避免长对话 token 爆炸

## 已知遗留（按需后续处理）

- 聊天记录仍存浏览器 localStorage，与账号不关联（换设备即丢）
- 宠物反馈页 remark_pet.html 目前只在前端 console 打印，未落库（评分走 /remark）
- 图书借阅（reader_book/borrows）为旧系统遗产，与宠物业务无耦合，仅保持原功能
- reader/manager 仅校验"已登录"，不区分角色（与旧版行为一致）

## UI 重构（2026-10-10）

全站已完成"温暖治愈系"视觉与交互重构，规范文档见 `docs/UI重构设计文档.md`（经独立评审 Agent 六轮评审至 100 分）：

- **设计系统**：`static/css/theme.css`（色彩/字号/间距 token、按钮六态、toast、顶栏页脚组件），蜜橙 #FF9E58 主色 + 奶油白 #FFF8F0 底 + 暖棕文字，全套对比度达 WCAG 4.5:1
- **全站统一顶栏/页脚**：`templates/_navbar.html` / `_footer.html`
- **聊天页重写**：宠物选择条（替换巨型圆按钮）、发送 loading+正在输入+失败重试、历史恢复（50 条）、设置弹层、AI 回复 Markdown 渲染、`?pet=N` 直达
- **CDN 全部本地化**：marked/html2canvas/jspdf 在 `static/js/vendor/`，移除 jQuery/Google Fonts
- **反馈落库**：/remark_pet 四宠物评分（真实名字）走 /remark 接口写入 reviews 表，与评分详情页互通
- **质量关卡**：e2e 回归 28/28（`test/refactor_e2e.py`）+ 视觉评审（8 页均分 91.6，无高/中严重度问题）


## 私人宠物重建工作室（v1.46.0）

入口 `/pet-studio`，登录后创建猫咪档案并上传正面 / 左侧 / 右侧 / 背面照片。保存素材不调用云端；勾选上传与计费确认后才提交一次混元 3D 3.1 任务。服务端需要 `.env` 中的 `HUNYUAN_3D_API_KEY` 和本机 Blender（可用 `BLENDER_EXECUTABLE` 指定）。使用 API Key 原值鉴权，不使用 SecretId，也不加 Bearer 前缀。

流程：照片 → 云端生成 → 自动下载 GLB → Blender 保留几何、将贴图降至 2K → 外貌确认 → 本机模板体积蒙皮 / 兼容骨骼动作复用 → 12 个动作预览与 8 项人工验收 → 手动启用猫咪岛。账号数据保持私有；可随时恢复市场外观。通过动作验收的私人重建模型支持桌宠与好友串门：桌面使用一次性配对后的行程凭证读取模型，串门仅向有效行程双方提供动画模型，原始照片仍为账号私有。召回、过期或关闭访客权限后停止模型访问；启用私人模型不会自动开启访客。视频输入与自动抽帧尚未实现。

云端任务编号先落库再查询，刷新只恢复原任务；下载或查询失败可继续查询。提交超时且没有编号时进入“结果未知”，不会自动重复扣费，需要管理员先去腾讯云核对。删除本地档案不能取消已经提交的云端任务或退费。当前本机服务使用单进程后台线程；生产多进程部署前应改成持久任务队列。

模型适配是草稿，尤其坐卧姿势、尾根、脸部、脚掌需要检查，不能保证任意照片生成的模型都自然可动。只有用户核对当前动作版本后才可启用。测试账户的自动勾选只验证接口状态门槛，不代表视觉质量认证。

验证命令（PowerShell）：

```powershell
$env:PYTHONPATH='.;test'
python -X utf8 -m unittest test_pet_generation.GenerationTests test_pet_studio.PetStudioTests
```

真实结果回归需 `PET_STUDIO_QUERY_JOB` 指定已有完成任务，并准备 `uploads/hunyuan-test-cat-20261015/{front,left,back}.png`。测试拦截提交、只查询指定原任务，不产生新的生成请求；随后真实下载、运行 Blender、验证私有启用和撤销。隔离数据库结果保存到 `uploads/hunyuan-test-cat-20261015/paid-check-20261015/workflow-e2e/`，可用 `test/studio_workflow_render.cjs`、`test/studio_island_render.cjs` 在 Electron 中验证工作室及小岛页面；这两个本地页面夹具不访问用户浏览器、登录会话或远端 API。
