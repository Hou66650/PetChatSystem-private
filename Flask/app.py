import openai
from flask import Flask, render_template, request, jsonify, send_from_directory

app = Flask(__name__)


class Users:
    def __init__(self, name, password):
        self.name = name
        self.password = password


# OpenAI 配置
class OpenApiConnect:
    def __init__(self, model_pattern, temperature=1):
        self.temperature = temperature
        self.__api_key = 'sk-RHOoG7f0dNDwQ6yQvmHkfz8N7QHXWTJcQIteGNrI7loI1Rv6'
        self.__api_url = 'https://api.wlai.vip/v1'

    def get_response(self, messages, model_pattern):
        client = openai.OpenAI(
            base_url=self.__api_url,
            api_key=self.__api_key,
        )
        response = client.chat.completions.create(
            model=model_pattern,
            messages=messages,
            temperature=self.temperature,
        )
        if response and hasattr(response, 'choices'):
            if response.choices:
                assistant_response_content = response.choices[0].message.content
                return assistant_response_content
            else:
                return 'No choice available in the response'
        else:
            return 'Invalid response'


# 初始化 OpenAI 连接
def get_openai_conn(model_pattern):
    return OpenApiConnect(model_pattern)


# 将其可以转化为gpt可读的形式
def convert_to_openai_messages(chat_history):
    messages = []
    for history in chat_history:
        role = history.get('sender')
        if role == 'w':
            role = 'user'  # 假设 'w' 表示用户消息
        elif role not in ['system', 'assistant', 'user', 'function']:
            role = 'user'  # 默认设置为 'user'，如果角色不在有效范围内

        content = history.get('message', '')
        messages.append({"role": role, "content": content})
    return messages


@app.route('/')
def index():
    user = Users('admin', 'admin')
    return render_template('index.html', user=user)


@app.route('/login')
def login():
    return render_template('login.html')


@app.route('/gpt')
def gpt():
    return render_template('gpt_me.html')


@app.route('/images/<filename>')
def serve_images(filename):
    return send_from_directory('templates/images', filename)


@app.route('/js/<filename>')
def serve_js(filename):
    return send_from_directory('templates/js', filename)


@app.route('/css/<filename>')
def serve_css(filename):
    return send_from_directory('templates/css', filename)


@app.route('/get_gpt_response', methods=['POST'])
def get_gpt_response():
    data = request.json
    print(data)
    user_message = data.get('message')
    # user_name = data.get('')
    chat_history = data.get('chatHistory')
    model_pattern = data.get('model_pattern')

    if not user_message:
        return jsonify({'error': 'Please enter a message.'}), 400

    # 将历史记录和当前消息合并为一个对话
    messages = chat_history + [
        {"role": chat_history[0]['sender'], "content": user_message}
    ]
    print(messages)

    openai_conn = get_openai_conn(model_pattern)
    messages = convert_to_openai_messages(messages)
    print(messages)
    assistant_response = openai_conn.get_response(messages, model_pattern)

    return jsonify({'reply': assistant_response})


if __name__ == '__main__':
    app.run(debug=True)
