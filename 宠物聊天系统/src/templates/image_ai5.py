# 创建图片
from openai import OpenAI
import base64
client = OpenAI( base_url="https://yunwu.ai/v1",
    api_key="sk-DtqUh94seeYdFpOr6jv1WVREBN9TXaDKZbfLadE52Oz1ADjV")

prompt = """

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