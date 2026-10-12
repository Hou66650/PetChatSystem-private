import requests
from PIL import Image
import os
import base64

# 替换为您的 API 密钥
API_KEY = "sk-LEGeYsjcejXNid132C9ZsqW1nqwDnhTUbJy9bIsUIAhpBuwy"

# 输入图像文件路径
input_image_path = r"D:\宠物聊天系统\templates\images\dog1.png"

# 输出调整后的图像文件路径
resized_image_path = r"D:\宠物聊天系统\templates\images\resized_dog1.png"

# 输出生成图像的保存路径
output_dir = r"D:\宠物聊天系统\output_images"
os.makedirs(output_dir, exist_ok=True)  # 确保输出目录存在

# 允许的尺寸
allowed_dimensions = [
    (1024, 1024), (1152, 896), (1216, 832), (1344, 768), (1536, 640),
    (640, 1536), (768, 1344), (832, 1216), (896, 1152)
]

# 检查输入文件是否存在
if not os.path.exists(input_image_path):
    print(f"文件未找到: {input_image_path}")
    exit()

# 打开图像并调整尺寸
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
resized_image.save(resized_image_path)
print(f"图像已调整为允许的尺寸: {best_size}，保存路径: {resized_image_path}")

# 使用 Stability AI 的 API
url = "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/image-to-image"

# 请求头
headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Accept": "application/json",
}

# 请求数据
data = {
    "text_prompts[0][text]": "Transform the pet in the image into a cartoon style, with soft colors, cute and lively facial expressions, and a visually appealing effect.",
    "text_prompts[0][weight]": "1",
    "cfg_scale": "9",  # 控制生成图像的质量
    "clip_guidance_preset": "FAST_BLUE",
    "samples": "1",  # 生成图像的数量
    "steps": "50",  # 生成过程中的迭代步数
}

# 上传调整后的图像
try:
    with open(resized_image_path, "rb") as image_file:
        files = {
            "init_image": image_file,
        }
        response = requests.post(url, headers=headers, data=data, files=files)

    # 检查响应状态
    if response.status_code == 200:
        data = response.json()
        print("API 响应成功！解析图像数据...")
        # 解析并保存生成的图像
        for i, image in enumerate(data.get("artifacts", [])):
            if "base64" in image:
                base64_data = image["base64"]
                try:
                    # 解码 base64 数据
                    image_bytes = base64.b64decode(base64_data)
                    # 找到一个不存在的文件名
                    index = i
                    output_path = os.path.join(output_dir, f"output_image_{index}.png")
                    while os.path.exists(output_path):
                        index += 1
                        output_path = os.path.join(output_dir, f"output_image_{index}.png")
                    # 保存图像为 PNG 格式
                    with open(output_path, "wb") as f:
                        f.write(image_bytes)
                    print(f"图像生成成功，已保存为 {output_path}")
                except Exception as e:
                    print(f"解码或保存图像时发生错误: {e}")
            else:
                print("返回数据中缺少 base64 图像数据")
    else:
        print(f"请求失败，状态码: {response.status_code}")
        print(f"错误信息: {response.text}")

except requests.exceptions.RequestException as e:
    print(f"请求过程中发生错误: {e}")
except Exception as e:
    print(f"发生错误: {e}")
