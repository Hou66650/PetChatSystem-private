import requests

url = "https://yunwu.ai/ideogram/v1/ideogram-v3/remix"

# 添加 prompt 参数
payload = {
    "prompt": "Keep the animal species in the original picture unchanged. Just change the visual quality of the picture."
}

file_path = r'D:\宠物聊天系统\templates\images\cat2.png'

# 填入有效的访问令牌
access_token = "sk-RHOoG7f0dNDwQ6yQvmHkfz8N7QHXWTJcQIteGNrI7loI1Rv6"
headers = {
    'Accept': 'application/json',
    'Authorization': f'Bearer {access_token}'
}

try:
    with open(file_path, 'rb') as file:
        files = [   
            ('image', (file_path, file, 'image/png'))
        ]
        response = requests.request("POST", url, headers=headers, data=payload, files=files)
        response.raise_for_status()
        print(response.text)
except requests.exceptions.HTTPError as http_err:
    print(f"HTTP error occurred: {http_err}")
except requests.exceptions.RequestException as req_err:
    print(f"Request error occurred: {req_err}")
except FileNotFoundError:
    print("The specified file was not found.")
