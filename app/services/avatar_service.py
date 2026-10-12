# -*- coding: utf-8 -*-
"""头像动漫化管线：上传照片 → GLM-4V 描述 → CogView 生成动漫头像。

旧版直接调 gpt-image-1 的 images.edit（OpenAI 中转站），且把文件写到
硬编码的 D:\\宠物聊天系统\\... 绝对路径；新方案全部改走公司 GLM Key：
两步生成（看图 → 文生图），文件落盘到 uploads/avatars/，路径可配置。
"""
import os
import uuid
from datetime import datetime

from flask import current_app

from ..config import Config
from ..llm.client import LLMError

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

MIME_BY_EXT = {'png': 'image/png', 'jpg': 'image/jpeg',
               'jpeg': 'image/jpeg', 'webp': 'image/webp'}

# 生成图片的真实格式按魔数判断（CogView 实际返回 JPEG），扩展名随之确定
IMAGE_MAGIC = [
    (b'\x89PNG', 'png'),
    (b'\xff\xd8\xff', 'jpg'),
    (b'GIF8', 'gif'),
    (b'RIFF', 'webp'),  # RIFF....WEBP
]


def _new_name(prefix, ext):
    ts = datetime.now().strftime('%Y%m%d%H%M%S')
    return f'{prefix}_{ts}_{uuid.uuid4().hex[:6]}.{ext}'


def process_avatar(file_storage):
    """处理上传的头像图片，返回 (payload, http_status)。"""
    if file_storage is None or not file_storage.filename:
        return {'success': False, 'error': '未上传图片'}, 400

    ext = file_storage.filename.rsplit('.', 1)[-1].lower() if '.' in file_storage.filename else ''
    if ext not in ALLOWED_EXTENSIONS:
        return {'success': False, 'error': f'不支持的图片格式（仅限 {"、".join(sorted(ALLOWED_EXTENSIONS))}）'}, 400

    raw = file_storage.read()
    if not raw:
        return {'success': False, 'error': '图片内容为空'}, 400
    if len(raw) > Config.MAX_AVATAR_BYTES:
        return {'success': False, 'error': '图片超过 8MB 大小限制'}, 400

    os.makedirs(Config.AVATAR_DIR, exist_ok=True)
    # 保留上传原图便于排查（不对外暴露，仅供管理员查看 uploads/avatars/）
    raw_path = os.path.join(Config.AVATAR_DIR, _new_name('upload', ext))
    with open(raw_path, 'wb') as f:
        f.write(raw)

    client = current_app.extensions['llm']
    try:
        # 第一步：视觉模型描述照片主体（只描述头面部特征，降低误触发内容审核）
        desc = client.describe_image(
            raw, mime=MIME_BY_EXT[ext],
            prompt='描述图片主体头面部的外貌特征（如毛色/耳朵/眼睛/表情/配饰），'
                   '不要描述身体动作和场景，输出一段可直接用于 AI 绘画头像的中文提示词，不要多余解释。')
        # 第二步：按描述生成动漫头像
        prompt = f'二次元动漫风格头像，{desc}，柔和明亮的色调，干净的圆形头像构图，高清插画'
        try:
            image_bytes = client.generate_image(prompt)
        except LLMError as e:
            # CogView 内容审核（1301）对正常描述偶发误伤，换简化提示词重试一次
            if '1301' in str(e) or '敏感' in str(e):
                current_app.logger.warning('CogView 审核误伤，使用简化提示词重试')
                image_bytes = client.generate_image(
                    '可爱的二次元动漫风格头像，柔和明亮的色调，干净的圆形构图，高清插画')
            else:
                raise
    except LLMError as e:
        current_app.logger.error('头像生成失败: %s', e)
        return {'success': False, 'error': f'头像生成失败：{e}'}, 503

    ext = 'png'
    for magic, name in IMAGE_MAGIC:
        if image_bytes.startswith(magic):
            ext = name
            break
    out_name = _new_name('processed', ext)
    with open(os.path.join(Config.AVATAR_DIR, out_name), 'wb') as f:
        f.write(image_bytes)

    return {'success': True, 'image_url': f'/media/avatars/{out_name}'}, 200
