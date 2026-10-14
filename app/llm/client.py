# -*- coding: utf-8 -*-
"""智谱 GLM 客户端（OpenAI 兼容协议，requests 直连，零额外依赖）。

对接方案来自《SONTIA 声灵 AI 助手-API 对接文档》：
- 直连 https://open.bigmodel.cn/api/paas/v4，公司 GLM Key 走环境变量注入；
- 借鉴声灵的稳定性设计：LLM 并发上限（BoundedSemaphore）、失败重试、
  密钥不进代码、请求无状态可随时换模型/换服务商（OpenAI 兼容）。
"""
import base64
import json
import threading
import time

import requests


class LLMError(RuntimeError):
    """LLM 调用失败（重试耗尽、鉴权失败或返回格式异常）。"""


class GLMClient:
    def __init__(self, api_key, base_url, models,
                 vision_model='glm-4v-flash', image_model='cogview-3-flash',
                 timeout=60, image_timeout=180,
                 max_retries=3, retry_delay=2, max_concurrency=2,
                 trust_env=False):
        if not api_key:
            raise LLMError('GLM_API_KEY 未配置：请检查 .env 文件')
        self.base_url = base_url.rstrip('/')
        self.models = list(models) or ['glm-4.5-flash']
        self.vision_model = vision_model
        self.image_model = image_model
        self.timeout = timeout
        self.image_timeout = image_timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._sem = threading.BoundedSemaphore(max_concurrency)
        self.session = requests.Session()
        self.session.trust_env = trust_env
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        })
        # 图片下载专用会话：不带 Authorization（发给图片 CDN 会被 403），
        # 但同样遵循 trust_env 直连策略
        self._download_session = requests.Session()
        self._download_session.trust_env = trust_env

    # ------------------------------------------------------------------
    # 内部：带重试的 POST。网络异常 / 429 / 5xx 重试，鉴权失败直接抛错。
    # 429 指数退避（2s→4s→8s）并尊重 Retry-After——快速重试会加重限流。
    # ------------------------------------------------------------------
    def _post(self, path, payload, timeout=None):
        url = f'{self.base_url}{path}'
        last_err = None
        for attempt in range(self.max_retries):
            try:
                with self._sem:  # 并发上限，防止打爆配额（声灵同款策略）
                    resp = self.session.post(url, json=payload,
                                             timeout=timeout or self.timeout)
                if resp.status_code == 401:
                    raise LLMError('GLM API Key 无效或已过期，请检查 .env 中的 GLM_API_KEY')
                if resp.status_code == 200:
                    return resp.json()
                # 429（限流/余额）与 5xx 视为可重试
                last_err = LLMError(f'GLM 服务返回 {resp.status_code}: {resp.text[:300]}')
                if resp.status_code == 429 and '余额' in resp.text:
                    raise last_err  # 余额不足重试无意义，直接失败
                if resp.status_code == 429:
                    # 限流：按 Retry-After 或指数退避，等够了再试
                    try:
                        wait = max(int(resp.headers.get('Retry-After', 0)),
                                   self.retry_delay * (2 ** attempt))
                    except (TypeError, ValueError):
                        wait = self.retry_delay * (2 ** attempt)
                    time.sleep(min(wait, 15))
                    continue
            except requests.RequestException as e:
                last_err = LLMError(f'网络错误: {e}')
            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay * (attempt + 1))
        raise last_err or LLMError('GLM 调用失败')

    @staticmethod
    def _content(data):
        try:
            return data['choices'][0]['message']['content'] or ''
        except (KeyError, IndexError, TypeError):
            raise LLMError(f'GLM 返回格式异常: {json.dumps(data, ensure_ascii=False)[:300]}')

    # ------------------------------------------------------------------
    # 对外：对话 / 看图 / 画图
    # ------------------------------------------------------------------
    def chat(self, messages, model=None, temperature=1.0, json_mode=False):
        """文本对话，返回助手回复文本。model 必须在白名单内。"""
        model = model or self.models[0]
        if model not in self.models:
            raise LLMError(f'模型 {model} 不在允许列表 {self.models} 中（可在 .env 的 GLM_MODELS 扩展）')
        payload = {'model': model, 'messages': messages, 'temperature': temperature}
        if json_mode:
            payload.update(response_format={'type':'json_object'}, thinking={'type':'disabled'}, max_tokens=1400)
        data = self._post('/chat/completions', payload)
        return self._content(data)

    def plan_once(self, messages):
        """Low-priority bounded background decision: no queue, retry or model fallback."""
        if not self._sem.acquire(blocking=False):
            raise LLMError('对话正在使用模型，探索使用本地策略')
        try:
            response=self.session.post(f'{self.base_url}/chat/completions',json={
                'model':self.models[0],'messages':messages,'temperature':.65,
                'response_format':{'type':'json_object'},'thinking':{'type':'disabled'},'max_tokens':160},timeout=(3,7))
            if response.status_code!=200:raise LLMError('后台探索模型暂不可用')
            return self._content(response.json())
        except (requests.RequestException,ValueError) as e:
            raise LLMError('后台探索模型暂不可用') from e
        finally:
            self._sem.release()

    def describe_image(self, image_bytes, mime='image/png', prompt=None):
        """视觉模型看图说话：头像动漫化管线的第一步（描述上传的照片）。"""
        prompt = prompt or (
            '描述这张图片主体的外貌特征（如毛色/发型/五官/服饰/神态），'
            '输出一段可直接用于 AI 绘画的中文提示词，不要任何多余解释。'
        )
        b64 = base64.b64encode(image_bytes).decode()
        data = self._post('/chat/completions', {
            'model': self.vision_model,
            'messages': [{
                'role': 'user',
                'content': [
                    {'type': 'image_url',
                     'image_url': {'url': f'data:{mime};base64,{b64}'}},
                    {'type': 'text', 'text': prompt},
                ],
            }],
        })
        return self._content(data)

    def generate_image(self, prompt, size='1024x1024'):
        """CogView 文生图：返回生成图片的二进制内容。"""
        data = self._post('/images/generations', {
            'model': self.image_model,
            'prompt': prompt,
            'size': size,
        }, timeout=self.image_timeout)
        try:
            url = data['data'][0]['url']
        except (KeyError, IndexError, TypeError):
            raise LLMError(f'CogView 返回格式异常: {json.dumps(data, ensure_ascii=False)[:300]}')
        # 生成成功后 CDN 对象可能尚未就绪（瞬时 403），短重试下载
        last_err = None
        for attempt in range(self.max_retries):
            try:
                resp = self._download_session.get(url, timeout=self.image_timeout)
            except requests.RequestException as e:
                last_err = str(e)
                time.sleep(self.retry_delay)
                continue
            if resp.status_code == 200:
                return resp.content
            last_err = f'HTTP {resp.status_code}'
            time.sleep(self.retry_delay)
        raise LLMError(f'下载生成图片失败: {last_err}')
