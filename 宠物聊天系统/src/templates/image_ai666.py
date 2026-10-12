# 编辑图片
import base64
from openai import OpenAI

client = OpenAI(base_url="https://yunwu.ai/v1",
                api_key="sk-DtqUh94seeYdFpOr6jv1WVREBN9TXaDKZbfLadE52Oz1ADjV")

prompt = """
转换成动漫的风格
"""

result = client.images.edit(
    model="gpt-image-1",
    image=open(r'D:\宠物聊天系统\templates\images\dog4.png', 'rb'),
    prompt=prompt
)

image_base64 = result.data[0].b64_json
image_bytes = base64.b64decode(image_base64)

# Save the image to a file
with open("gift-basket.png", "wb") as f:
    f.write(image_bytes)
