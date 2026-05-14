# ============================================================
# 全网热点聚合分析器（完整版：并行抓取 + 定时邮件推送）
# ============================================================


# 第一部分：导入工具包
import requests
import os
import smtplib                           # Python内置，用来发送邮件
import schedule                          # 定时任务
import time                              # 时间控制
from email.mime.text import MIMEText     # 构建邮件内容
from email.mime.multipart import MIMEMultipart  # 构建多部分邮件
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor import resend # 并行抓取#发送邮件


# 第二部分：读取环境变量
load_dotenv()
KIMI_API_KEY = os.getenv("KIMI_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
GMAIL_PASSWORD = os.getenv("GMAIL_PASSWORD")
RECIPIENT = "308737902@qq.com"  # 收件人


# 第三部分：连接AI
client = OpenAI(
    api_key=KIMI_API_KEY,
    base_url="https://api.moonshot.cn/v1",
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


# 第四部分：各平台抓取函数

def fetch_baidu_hot():
    try:
        url = "https://top.baidu.com/board?tab=realtime"
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.encoding = "utf-8"
        soup = BeautifulSoup(response.text, "html.parser")
        items = soup.find_all("div", class_="c-single-text-ellipsis")
        return [item.get_text(strip=True) for item in items[:20] if item.get_text(strip=True)]
    except Exception as e:
        print(f"  百度热搜抓取失败：{e}")
        return []


def fetch_weibo_hot():
    try:
        url = "https://weibo.com/ajax/side/hotSearch"
        headers = {**HEADERS, "Referer": "https://weibo.com/"}
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        items = data.get("data", {}).get("realtime", [])
        return [item.get("word", "") for item in items[:20] if item.get("word")]
    except Exception as e:
        print(f"  微博热搜抓取失败：{e}")
        return []


def fetch_zhihu_hot():
    try:
        url = "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=20"
        headers = {**HEADERS, "Referer": "https://www.zhihu.com/"}
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        items = data.get("data", [])
        return [item.get("target", {}).get("title", "") for item in items[:20] if item.get("target", {}).get("title")]
    except Exception as e:
        print(f"  知乎热榜抓取失败：{e}")
        return []


def fetch_toutiao_hot():
    try:
        url = "https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc"
        headers = {**HEADERS, "Referer": "https://www.toutiao.com/"}
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        items = data.get("data", [])
        return [item.get("Title", "") or item.get("title", "") for item in items[:20] if item.get("Title") or item.get("title")]
    except Exception as e:
        print(f"  头条热榜抓取失败：{e}")
        return []


def fetch_international_news(category=""):
    try:
        url = "https://newsapi.org/v2/top-headlines"
        params = {
            "apiKey": NEWS_API_KEY,
            "language": "en",
            "pageSize": 20,
        }
        if category:
            params["category"] = category
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        if data.get("status") != "ok":
            return []
        return [
            f"{a.get('title', '')}（{a.get('source', {}).get('name', '')}）"
            for a in data.get("articles", []) if a.get("title")
        ]
    except Exception as e:
        print(f"  国际热点抓取失败：{e}")
        return []


# 第五部分：并行抓取所有数据源
def fetch_all_sources():
    """
    用ThreadPoolExecutor并行抓取所有平台
    相当于同时派出7个人去抓数据，而不是一个人跑7趟
    速度提升3-5倍
    """
    print("📡 并行抓取所有数据源...")

    # 定义要执行的任务列表：(任务名, 函数, 参数)
    tasks = {
        "baidu":        (fetch_baidu_hot, []),
        "weibo":        (fetch_weibo_hot, []),
        "zhihu":        (fetch_zhihu_hot, []),
        "toutiao":      (fetch_toutiao_hot, []),
        "intl_general": (fetch_international_news, []),
        "intl_tech":    (fetch_international_news, ["technology"]),
        "intl_business":(fetch_international_news, ["business"]),
    }

    sources = {}

    # 并行执行所有任务
    with ThreadPoolExecutor(max_workers=7) as executor:
        futures = {
            name: executor.submit(func, *args)
            for name, (func, args) in tasks.items()
        }
        # 等待所有任务完成，收集结果
        for name, future in futures.items():
            sources[name] = future.result()
            print(f"   ✅ {name}：{len(sources[name])} 条")

    total = sum(len(v) for v in sources.values())
    print(f"\n📊 共抓取 {total} 条热点数据")
    return sources


# 第六部分：AI分析生成简报
def analyze_and_report(sources, focus=""):

    def format_list(items):
        return "\n".join([f"- {item}" for item in items]) if items else "暂无数据"

    focus_text = f"\n⚠️ 用户特别关注方向：{focus}，请重点分析这个方向的相关内容。" if focus else ""

    prompt = f"""你是一位资深时事分析师。以下是今日从多个平台抓取的全网热点数据，请完成以下工作：

第一步：去重整理——合并相同或相似的话题，不要重复出现。
第二步：按热度排序——综合多平台出现频次，判断哪些话题最受关注。
第三步：深度分析——不要只是复述标题，要解释背景、意义和影响。{focus_text}

原始热点数据如下：

【百度热搜】
{format_list(sources.get('baidu', []))}

【微博热搜】
{format_list(sources.get('weibo', []))}

【知乎热榜】
{format_list(sources.get('zhihu', []))}

【今日头条热榜】
{format_list(sources.get('toutiao', []))}

【国际综合热点】
{format_list(sources.get('intl_general', []))}

【国际科技热点】
{format_list(sources.get('intl_tech', []))}

【国际商业热点】
{format_list(sources.get('intl_business', []))}

请按以下格式输出完整分析报告：

📰 今日热点深度简报 {datetime.now().strftime("%Y年%m月%d日 %H:%M")}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【今日TOP5重点事件深度分析】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔥 NO.1 【事件标题】
热度来源：（出现在哪些平台）
事件背景：（这件事的来龙去脉，100字左右）
核心影响：（这件事对哪些人、哪些领域产生影响）
后续预测：（基于现有信息，预测事件接下来可能的走向）

🔥 NO.2 【事件标题】
热度来源：
事件背景：
核心影响：
后续预测：

🔥 NO.3 【事件标题】
热度来源：
事件背景：
核心影响：
后续预测：

🔥 NO.4 【事件标题】
热度来源：
事件背景：
核心影响：
后续预测：

🔥 NO.5 【事件标题】
热度来源：
事件背景：
核心影响：
后续预测：

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【其他值得关注的事件】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
（简要列出5-8条次要热点，每条2-3句话说明）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【今日整体态势判断】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
（从宏观角度，用200字左右分析今日舆论和国际局势的整体走向）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【今日关键词】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
（提炼8-10个关键词，用 # 标签格式）"""

    response = client.chat.completions.create(
        model="moonshot-v1-8k",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content


# 第七部分：发送邮件
def send_email(content):
    """
    用Resend API发送简报
    Resend专为开发者设计，在服务器上稳定可靠
    """
    try:
        resend.api_key = os.getenv("RESEND_API_KEY")

        params = {
            "from": "onboarding@resend.dev",  # Resend默认发件地址
            "to": RECIPIENT,
            "subject": f"今日热点简报 {datetime.now().strftime('%Y年%m月%d日')}",
            "text": content,
        }

        email = resend.Emails.send(params)
        print(f"✅ 简报已发送到：{RECIPIENT}，邮件ID：{email['id']}")

    except Exception as e:
        print(f"❌ 邮件发送失败：{e}")


# 第八部分：保存简报
def save_report(content):
    if not os.path.exists("news_reports"):
        os.makedirs("news_reports")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"news_reports/简报_{timestamp}.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"💾 简报已保存到：{filename}")


# 第九部分：主任务（抓取+分析+发送）
def run_daily_report():
    print(f"\n{'='*40}")
    print(f"开始生成今日简报：{datetime.now().strftime('%Y年%m月%d日 %H:%M')}")
    print(f"{'='*40}\n")

    sources = fetch_all_sources()

    print("\n🤖 AI正在分析，请稍候...\n")
    report = analyze_and_report(sources)

    print(report)
    save_report(report)
    send_email(report)


# 第十部分：主程序
# GitHub Actions模式：直接运行一次，完成后退出
print("=== 全网热点聚合分析器 ===")
print(f"运行时间：{datetime.now().strftime('%Y年%m月%d日 %H:%M')}\n")

sources = fetch_all_sources()

print("\n🤖 AI正在分析，请稍候...\n")
report = analyze_and_report(sources)

print(report)
save_report(report)
send_email(report)

print("\n✅ 任务完成，程序退出")