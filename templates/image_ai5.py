# 创建图片
from openai import OpenAI
import base64
client = OpenAI( base_url="https://yunwu.ai/v1",
    api_key="sk-DtqUh94seeYdFpOr6jv1WVREBN9TXaDKZbfLadE52Oz1ADjV")

prompt = """
为了对比不同超参数设置下 Vision Transformer（ViT）模型在图像分类任务中的性能，请生成以下参数变化曲线图：
对比不同学习率（如 0.001、0.0001、0.00001）下，模型训练损失随训练轮数的变化曲线，绘制在同一张图中进行对比。
不同批次大小（如 16、32、64）设置时，模型在验证集上的 F1 分数随训练时间的变化曲线。
曲线图需要有清晰的对比标识，便于区分不同超参数设置下的曲线。
"""

result = client.images.generate(
    model="gpt-image-1",
    prompt=prompt
)

image_base64 = result.data[0].b64_json
image_bytes = base64.b64decode(image_base64)

# Save the image to a file
with open("otter.png", "wb") as f:
    f.write(image_bytes)