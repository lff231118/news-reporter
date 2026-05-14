# ============================================================
# 诗词解析工具 - 网页版（带对话记忆）
# 逻辑顺序：导入工具 → 连接AI → 创建应用 → 定义页面 → 定义路由 → 启动服务
# ============================================================


# 第一部分：导入工具包
from flask import Flask, request, jsonify, render_template_string, session
# session 是新加的，用来存每个用户的对话记录
from openai import OpenAI
import os
from dotenv import load_dotenv


# 第二部分：读取环境变量，连接AI
load_dotenv()

client = OpenAI(
    api_key=os.getenv("KIMI_API_KEY"),
    base_url="https://api.moonshot.cn/v1",
)


# 第三部分：创建Flask应用
app = Flask(__name__)

# secret_key 是Session的加密密钥，用来保护用户数据安全
# 实际项目里应该用随机字符串，这里用简单的示例
app.secret_key = "poetry_app_secret_key"


# 第四部分：定义系统设定
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


# 第五部分：定义网页HTML
HTML = """
<!DOCTYPE html>
<html lang="zh">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>诗词解析工具</title>
    <style>
        body {
            font-family: "Microsoft YaHei", sans-serif;
            max-width: 800px;
            margin: 40px auto;
            padding: 0 20px;
            background: #f5f0e8;
            color: #333;
        }
        h1 {
            text-align: center;
            color: #8b4513;
            font-size: 28px;
            margin-bottom: 30px;
        }
        /* 对话记录区域 */
        .chat-history {
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            min-height: 100px;
            max-height: 500px;
            overflow-y: auto;  /* 内容太多时可以滚动 */
        }
        /* 每一条对话 */
        .message {
            margin-bottom: 20px;
            padding-bottom: 20px;
            border-bottom: 1px solid #eee;
        }
        .message:last-child {
            border-bottom: none;
        }
        /* 用户的问题 */
        .user-msg {
            color: #8b4513;
            font-weight: bold;
            margin-bottom: 8px;
        }
        /* AI的回答 */
        .ai-msg {
            white-space: pre-wrap;
            line-height: 1.8;
        }
        /* 输入区域 */
        .input-area {
            display: flex;
            gap: 10px;
            margin-bottom: 10px;
        }
        input {
            flex: 1;
            padding: 12px;
            font-size: 16px;
            border: 1px solid #ccc;
            border-radius: 6px;
            outline: none;
        }
        button {
            padding: 12px 24px;
            background: #8b4513;
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 16px;
            cursor: pointer;
        }
        button:hover { background: #a0522d; }
        .clear-btn {
            background: #888;
            width: 100%;
            margin-top: 5px;
        }
        .clear-btn:hover { background: #666; }
        .loading {
            text-align: center;
            color: #888;
            padding: 10px;
            display: none;
        }
        /* 空状态提示 */
        .empty-hint {
            text-align: center;
            color: #bbb;
            padding: 20px;
        }
    </style>
</head>
<body>
    <h1>诗词解析工具</h1>

    <!-- 对话记录显示区域 -->
    <div class="chat-history" id="chatHistory">
        <div class="empty-hint" id="emptyHint">输入诗词名称或某一句诗词开始解析</div>
    </div>

    <div class="loading" id="loading">正在解析，请稍候...</div>

    <!-- 输入区域 -->
    <div class="input-area">
        <input type="text" id="input" placeholder="输入诗词名称或追问..." />
        <button onclick="analyze()">发送</button>
    </div>
    <button class="clear-btn" onclick="clearHistory()">清空对话记录</button>

    <script>
        // 发送解析请求
        async function analyze() {
            const input = document.getElementById("input").value.trim();
            if (!input) return;

            // 隐藏空状态提示
            document.getElementById("emptyHint").style.display = "none";

            // 在页面上显示用户的问题
            const chatHistory = document.getElementById("chatHistory");
            const msgDiv = document.createElement("div");
            msgDiv.className = "message";
            msgDiv.innerHTML = `<div class="user-msg">你：${input}</div><div class="ai-msg" id="waiting">正在解析...</div>`;
            chatHistory.appendChild(msgDiv);

            // 清空输入框
            document.getElementById("input").value = "";

            // 滚动到最新内容
            chatHistory.scrollTop = chatHistory.scrollHeight;

            // 发送请求给后端
            const response = await fetch("/analyze", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({input: input})
            });

            const data = await response.json();

            // 把"正在解析..."替换成真实结果
            msgDiv.querySelector(".ai-msg").textContent = data.result;

            // 再次滚动到最新内容
            chatHistory.scrollTop = chatHistory.scrollHeight;
        }

        // 清空对话记录
        async function clearHistory() {
            await fetch("/clear", {method: "POST"});
            document.getElementById("chatHistory").innerHTML = 
                '<div class="empty-hint" id="emptyHint">输入诗词名称或某一句诗词开始解析</div>';
        }

        // 按回车发送
        document.getElementById("input").addEventListener("keypress", function(e) {
            if (e.key === "Enter") analyze();
        });
    </script>
</body>
</html>
"""


# 第六部分：定义路由

# 首页
@app.route("/")
def index():
    return render_template_string(HTML)


# 处理解析请求
@app.route("/analyze", methods=["POST"])
def analyze():
    user_input = request.json.get("input", "")

    # 从Session里读取对话历史
    # 如果没有历史记录，就初始化为空列表
    history = session.get("history", [])

    # 把用户这次的输入加入历史
    history.append({
        "role": "user",
        "content": user_input
    })

    # 调用AI，带上完整历史记录
    response = client.chat.completions.create(
        model="moonshot-v1-8k",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT}
        ] + history
    )

    ai_reply = response.choices[0].message.content

    # 把AI回复也加入历史
    history.append({
        "role": "assistant",
        "content": ai_reply
    })

    # 把更新后的历史存回Session
    session["history"] = history

    return jsonify({"result": ai_reply})


# 清空对话记录
@app.route("/clear", methods=["POST"])
def clear():
    # 清空Session里的历史记录
    session["history"] = []
    return jsonify({"status": "ok"})


# 第七部分：启动服务
if __name__ == "__main__":
    app.run(debug=True,port=5000)