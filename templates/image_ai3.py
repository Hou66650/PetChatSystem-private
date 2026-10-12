import requests
import base64
from PIL import Image
import os

# 填入你的 API Key
API_KEY = "sk-LEGeYsjcejXNid132C9ZsqW1nqwDnhTUbJy9bIsUIAhpBuwy"

# 输入图像文件路径
input_image_path = r"D:\宠物聊天系统\templates\images\dog5.png"

# 允许的尺寸
allowed_dimensions = [
    (1024, 1024), (1152, 896), (1216, 832), (1344, 768), (1536, 640),
    (640, 1536), (768, 1344), (832, 1216), (896, 1152)
]

# 打开图像
image = Image.open(input_image_path)
width, height = image.size
# 计算输入图像的宽高比
input_ratio = width / height

# 找到最接近输入图像宽高比的允许尺寸
min_diff = float('inf')
best_size = None
for size in allowed_dimensions:
    size_ratio = size[0] / size[1]
    diff = abs(input_ratio - size_ratio)
    if diff < min_diff:
        min_diff = diff
        best_size = size

# 调整图像尺寸
resized_image = image.resize(best_size, Image.LANCZOS)

# 保存调整后的图像到临时文件
temp_image_path = "temp_resized_image.png"
resized_image.save(temp_image_path)

# 使用 stable-diffusion-xl-1024-v1-0 模型
url = "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/image-to-image"

headers = {
    "Accept": "application/json",
    "Authorization": f"Bearer {API_KEY}"
}

# 直接以文件形式打开调整后的图像
with open(temp_image_path, "rb") as image_file:
    payload = {
        "text_prompts[0][text]": "I hope to transform the animals in the picture into a Japanese anime style, "
                                 "with a profound sense of Japanese anime aesthetics and a blurred background.. Pay "
                                 "attention"
                                 "to making the facial expressions cute and lively, the body proportions well - "
                                 "coordinated, and the color combination soft and rich in layers. Overall, "
                                 "create an attractive and visually appealing anime effect.",
        "text_prompts[0][weight]": "1",
        "cfg_scale": "7",
        "clip_guidance_preset": "FAST_BLUE",
        "samples": "1",
        "steps": "30"
    }
    files = {
        "init_image": image_file
    }

    response = requests.post(url, headers=headers, data=payload, files=files)

# 删除临时文件
os.remove(temp_image_path)

if response.status_code == 200:
    data = response.json()
    # 保存生成的图像
    for i, image in enumerate(data["artifacts"]):
        with open(f"output_image_{i}.png", "wb") as f:
            f.write(base64.b64decode(image["base64"]))
    print("图像生成成功并保存。")
else:
    print(f"请求失败，状态码: {response.status_code}，错误信息: {response.text}")
