import requests

url = "https://yunwu.ai/ideogram/v1/ideogram-v3/remix"

payload = {}
file_path = 'D:\\宠物聊天系统\\templates\\images\\c.png'

# 填入有效的访问令牌
access_token = "sk-RHOoG7f0dNDwQ6yQvmHkfz8N7QHXWTJcQIteGNrI7loI1Rv6"
headers = {
    'Accept': 'application/json',
    'Authorization': f'Bearer {access_token}'
}

try:
    # 使用 with 语句确保文件正确关闭
    with open(file_path, 'rb') as file:
        files = [
            ('image', (file_path, file, 'image/png'))
        ]
        response = requests.request("POST", url, headers=headers, data=payload, files=files)
        # 检查响应状态码，如果不是 200 会引发 HTTPError 异常
        response.raise_for_status()
        print(response.text)
except requests.exceptions.HTTPError as http_err:
    print(f"HTTP error occurred: {http_err}")
except requests.exceptions.RequestException as req_err:
    print(f"Request error occurred: {req_err}")
except FileNotFoundError:
    print("The specified file was not found.")