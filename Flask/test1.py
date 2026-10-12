import openai
import time

# 打印openai的版本
print(openai.__version__)

client = openai.OpenAI(
    base_url="https://yunwu.ai/v1",
    api_key="sk-RHOoG7f0dNDwQ6yQvmHkfz8N7QHXWTJcQIteGNrI7loI1Rv6"
)

messages = [
    {"role": "system", "content": "You are a helpful assistant."}
]

while True:
    user_input = input("You: ")
    messages.append({"role": "user", "content": user_input})

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=messages,
        temperature=1
    )

    assistant_response = response.choices[0].message.content
    print(f"Assistant: {assistant_response}")

    messages.append({"role": "assistant", "content": assistant_response})
    time.sleep(1)