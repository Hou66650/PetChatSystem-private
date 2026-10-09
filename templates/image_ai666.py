# 编辑图片
import base64
from openai import OpenAI

client = OpenAI(base_url="https://yunwu.ai/v1",
                api_key="sk-DtqUh94seeYdFpOr6jv1WVREBN9TXaDKZbfLadE52Oz1ADjV")

prompt = """
帮我根据这个装配图还原出他的实物图
"""

result = client.images.edit(
    model="gpt-image-1",
    image=open(r'D:\A-公众号-后其锦/t.jpg', 'rb'),
    prompt=prompt
)

image_base64 = result.data[0].b64_json
image_bytes = base64.b64decode(image_base64)

# Save the image to a file
with open("gift-basket.png", "wb") as f:
    f.write(image_bytes)
