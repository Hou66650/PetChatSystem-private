# -*- coding: utf-8 -*-
"""集中管理配置：优先读环境变量，缺省时回退到项目根目录的 .env 文件。

密钥类配置（GLM_API_KEY / SECRET_KEY）一律不写进代码，只放 .env，
.env 已加入 .gitignore（对应 SONTIA 声灵 /etc/sontia/glm-agent.env 的做法）。
"""
import os

# 项目根目录 = app/ 的上一级
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_env_file(path):
    """极简 .env 加载器：KEY=VALUE 每行一条，不覆盖已存在的环境变量。"""
    if not os.path.exists(path):
        return
    with open(path, encoding='utf-8-sig') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            key, value = key.strip(), value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


load_env_file(os.path.join(BASE_DIR, '.env'))


def _bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in ('1', 'true', 'yes', 'on')


def _int(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


class Config:
    """所有配置项集中在此，带默认值，可用环境变量覆盖。"""

    # --- Flask 基础 -------------------------------------------------
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-change-me')
    DEBUG = _bool('DEBUG', True)

    # --- 数据库 -----------------------------------------------------
    # 绝对路径，保证在任意工作目录下启动都能找到同一个库
    DATABASE_PATH = os.path.join(BASE_DIR, os.environ.get('DATABASE', 'book.db'))
    SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'schema.sql')

    # --- 目录 -------------------------------------------------------
    # 旧版页面资产（gpt_me.html 等通过 /images /js /css 代理访问）
    TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')
    AVATAR_DIR = os.path.join(BASE_DIR, 'uploads', 'avatars')   # 上传原图 + AI 生成头像
    PETS_DIR = os.path.join(BASE_DIR, 'data', 'pets')           # 宠物角色注册表

    # --- GLM（智谱，OpenAI 兼容协议）--------------------------------
    GLM_API_KEY = os.environ.get('GLM_API_KEY', '')
    GLM_BASE_URL = os.environ.get('GLM_BASE_URL', 'https://open.bigmodel.cn/api/paas/v4')
    # 对话模型白名单：前端下拉框由它生成；当前 Key 只有 glm-4.5-flash 有额度
    GLM_MODELS = [m.strip() for m in os.environ.get('GLM_MODELS', 'glm-4.5-flash').split(',') if m.strip()]
    GLM_VISION_MODEL = os.environ.get('GLM_VISION_MODEL', 'glm-4v-flash')   # 看图
    GLM_IMAGE_MODEL = os.environ.get('GLM_IMAGE_MODEL', 'cogview-3-flash')  # 画图

    # --- LLM 调用策略（借鉴 SONTIA 声灵：并发上限 + 重试）------------
    LLM_MAX_CONCURRENCY = _int('LLM_MAX_CONCURRENCY', 2)
    LLM_MAX_RETRIES = _int('LLM_MAX_RETRIES', 3)
    LLM_RETRY_DELAY = _int('LLM_RETRY_DELAY', 2)      # 秒，按次数线性递增
    LLM_TIMEOUT = _int('LLM_TIMEOUT', 60)             # 秒
    LLM_IMAGE_TIMEOUT = _int('LLM_IMAGE_TIMEOUT', 180)
    # bigmodel.cn 为国内直连，默认不走系统代理（本机代理反而会导致连接失败）
    LLM_TRUST_ENV = _bool('LLM_TRUST_ENV', False)

    # --- 业务参数 ---------------------------------------------------
    HISTORY_LIMIT = _int('HISTORY_LIMIT', 20)          # 送入 LLM 的最大历史条数
    MAX_MESSAGE_CHARS = _int('MAX_MESSAGE_CHARS', 2000)
    MAX_AVATAR_BYTES = _int('MAX_AVATAR_BYTES', 8 * 1024 * 1024)  # 头像上传上限 8MB

    # --- 宠物 TTS 音色（S1-04）--------------------------------------
    # 音色 ID 属于服务端供应商配置，只允许环境变量白名单，前端不传 voice。
    # 以下默认值已于 2026-10-11 用真实接口实测通过（同一句文本均返回 200 + wav）：
    #   tongtong 彤彤·女声明亮   jam 男声爽朗   xiaochen 女声俏皮   chuichui 锤锤·男声沉稳
    PET_TTS_VOICES = {
        1: os.getenv('PET_TTS_VOICE_1', 'tongtong'),    # 柴犬：元气明亮
        2: os.getenv('PET_TTS_VOICE_2', 'jam'),         # 哈士奇：爽朗略低沉
        3: os.getenv('PET_TTS_VOICE_3', 'xiaochen'),    # 猫咪：轻柔俏皮
        4: os.getenv('PET_TTS_VOICE_4', 'chuichui'),    # 德牧：稳定可靠
    }
    PET_TTS_DEFAULT_VOICE = 'tongtong'

    # --- 版本管理（强制）：每次改动必须升版本并记 CHANGELOG.md ----------------
    # 修复→补丁位 / 新功能→次版本位 / 破坏性→主版本位；
    # 用 scripts/bump_version.py 升号（自动校验 CHANGELOG 已记账），提交打同名 tag。
    APP_VERSION = os.environ.get('APP_VERSION', '1.36.1')

    # --- 真实宠物叫声（v1.0.0）：petId → 物种，决定叫声库目录 ---------------
    # 1 柴犬 / 2 哈士奇 / 4 德牧 = 狗；3 猫咪 = 猫。与前端 pet-sounds.js 保持一致。
    PET_SPECIES = {1: 'dog', 2: 'dog', 3: 'cat', 4: 'dog'}

    # --- GLM Realtime 实时语音（P0）--------------------------------------
    # 浏览器直连 Realtime WS；Flask 只签发短期 JWT，长期 GLM_API_KEY 不出后端。
    # 移动端优先 server_vad + PCM（官方建议）；token TTL 默认 600s、硬上限 900s。
    GLM_REALTIME_URL = os.environ.get(
        'GLM_REALTIME_URL', 'wss://open.bigmodel.cn/api/paas/v4/realtime')
    GLM_REALTIME_TOKEN_TTL = min(_int('GLM_REALTIME_TOKEN_TTL', 600), 900)
    GLM_REALTIME_ENABLED = _bool('GLM_REALTIME_ENABLED', True)
    GLM_REALTIME_VAD = os.environ.get('GLM_REALTIME_VAD', 'server_vad')
    GLM_REALTIME_INPUT_FORMAT = os.environ.get('GLM_REALTIME_INPUT_FORMAT', 'pcm16')
    GLM_REALTIME_OUTPUT_FORMAT = os.environ.get('GLM_REALTIME_OUTPUT_FORMAT', 'pcm')
