# ============================================================
# 诗词解析工具（升级版：带记忆的对话）
# 逻辑顺序：导入工具 → 连接AI → 定义功能 → 保存文件 → 运行主程序
# ============================================================


# 第一部分：导入工具包
from openai import OpenAI
import os
from datetime import datetime
from dotenv import load_dotenv


# 第二部分：连接AI
load_dotenv()  # 加载 .env 文件中的环境变量
client = OpenAI(
    api_key=os.getenv("KIMI_API_KEY"),
    base_url="https://api.moonshot.cn/v1",
)


# 第三部分：定义系统设定
# 单独拿出来，方便以后修改
SYSTEM_PROMPT = """你是一位专业的古典诗词研究者和影像导演。
用户输入诗词名称或某一句诗词，你需要按以下格式输出：

【诗词正文】
诗名：
作者：
朝代：
正文：

【意境解读】
（解读这首诗的意境和意义，200字左右）

【相关诗词】
1. 诗名 · 作者
   相关原因：
2. 诗名 · 作者
   相关原因：
3. 诗名 · 作者
   相关原因：

【视频场景描述】
场景一：（对应诗词开头，描述画面、光线、色调、镜头运动，100字左右）
场景二：（对应诗词中段，描述画面、光线、色调、镜头运动，100字左右）
场景三：（对应诗词结尾，描述画面、光线、色调、镜头运动，100字左右）

如果用户问的是追问或补充问题，结合上下文回答即可，不必重复完整格式。"""


# 第四部分：定义"对话"功能
# history 是对话历史列表，每次对话都会往里面加内容
def chat(history, user_input):

    # 把用户这次说的话，加入历史记录
    history.append({
        "role": "user",
        "content": user_input
    })

    # 发给AI的内容 = 系统设定 + 完整对话历史
    # 这样AI就能"记住"之前说过的内容
    response = client.chat.completions.create(
        model="moonshot-v1-8k",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT}
        ] + history  # 把历史记录拼接进去
    )

    # 取出AI的回复
    ai_reply = response.choices[0].message.content

    # 把AI的回复也加入历史记录，下次对话时AI能看到自己说过什么
    history.append({
        "role": "assistant",
        "content": ai_reply
    })

    # 返回AI的回复和更新后的历史记录
    return ai_reply, history


# 第五部分：定义"保存文件"功能
def save_result(history):

    # 如果文件夹不存在就创建
    if not os.path.exists("poetry_results"):
        os.makedirs("poetry_results")

    # 用时间戳命名文件
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"poetry_results/对话记录_{timestamp}.md"

    # 把完整对话历史写入文件
    with open(filename, "w", encoding="utf-8") as f:
        f.write("# 诗词对话记录\n\n")
        for message in history:
            if message["role"] == "user":
                f.write(f"**你：** {message['content']}\n\n")
            elif message["role"] == "assistant":
                f.write(f"**AI：** {message['content']}\n\n")
                f.write("---\n\n")

    print(f"\n对话已保存到：{filename}")


# 第六部分：主程序
print("=== 诗词解析工具 ===")
print("输入诗词名称或某一句诗词，按回车获取解析")
print("输入『保存』保存当前对话记录")
print("输入『退出』结束程序")
print()

# 初始化对话历史为空列表
# 每次启动程序，都从空白开始
history = []

while True:

    user_input = input("你：")

    if user_input == "退出":
        break

    if user_input == "保存":
        save_result(history)
        continue  # continue的意思是跳过本次循环剩余部分，回到while重新开始

    print("\n正在解析，请稍候...\n")

    # 调用对话功能，传入历史记录和用户输入
    # 拿回AI回复和更新后的历史记录
    ai_reply, history = chat(history, user_input)

    print(f"AI：{ai_reply}")
    print("\n" + "="*40 + "\n")