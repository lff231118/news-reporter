from openai import OpenAI
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
        api_key=os.getenv("KIMI_API_KEY"),
        base_url="https://api.moonshot.cn/v1",
)

while True:
    user_input = input("你：")
    
    if user_input == "退出":
        break
    
    response = client.chat.completions.create(
        model="moonshot-v1-8k",
        messages=[
            {"role": "user", "content": user_input}
        ]
    )
    
    print("Kimi：" + response.choices[0].message.content)
    print()