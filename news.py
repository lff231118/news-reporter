"""
全网热点聚合分析器 v2.0
=========================
优化内容：
  - 并行抓取 10+ 数据源（国内+国际+技术社区）
  - 自动重试机制，单源挂了不影响整体
  - Kimi 32K 模型深度分析
  - QQ邮箱推送 + 本地保存

改进记录：
  v2.0 (2026-06-16)
    - 新增 Hacker News、GitHub Trending、Reddit、B站 数据源
    - 新增自动重试机制
    - 清理死代码、无用依赖
    - 升级 AI 模型至 moonshot-v1-32k
    - 改用 logging 替代 print
    - 补充 README
"""

import os
import re
import smtplib
import time
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from openai import OpenAI
from dotenv import load_dotenv
from bs4 import BeautifulSoup

# ── 日志 ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("news-reporter")

# ── 环境变量 ──
load_dotenv()
KIMI_API_KEY = os.getenv("KIMI_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
QQ_EMAIL = os.getenv("QQ_EMAIL")
QQ_PASSWORD = os.getenv("QQ_PASSWORD")
RECIPIENT = os.getenv("RECIPIENT_EMAIL")
if not RECIPIENT:
    raise ValueError("请设置 RECIPIENT_EMAIL 环境变量")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

client = OpenAI(api_key=KIMI_API_KEY, base_url="https://api.moonshot.cn/v1")


# ════════════════════════════════════════════════
# 工具函数
# ════════════════════════════════════════════════

def retry(max_attempts=3, delay=2):
    """重试装饰器：静默重试，全挂则返回空列表"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_err = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_err = e
                    logger.warning("  %s 第%s次失败: %s", func.__name__, attempt, e)
                    if attempt < max_attempts:
                        time.sleep(delay)
            logger.error("  %s 已重试%s次，放弃", func.__name__, max_attempts)
            return []
        return wrapper
    return decorator


def safe_get(url, headers=None, params=None, timeout=15, json_mode=False):
    """带超时的 GET 请求"""
    resp = requests.get(
        url, headers=headers or HEADERS, params=params, timeout=timeout
    )
    resp.raise_for_status()
    return resp.json() if json_mode else resp


# ════════════════════════════════════════════════
# 数据源抓取
# ════════════════════════════════════════════════

# ── 国内主流 ──

@retry()
def fetch_baidu_hot():
    """百度热搜"""
    url = "https://top.baidu.com/board?tab=realtime"
    resp = safe_get(url)
    resp.encoding = "utf-8"
    soup = BeautifulSoup(resp.text, "html.parser")
    items = soup.find_all("div", class_="c-single-text-ellipsis")
    return [i.get_text(strip=True) for i in items[:20] if i.get_text(strip=True)]


@retry()
def fetch_weibo_hot():
    """微博热搜"""
    url = "https://weibo.com/ajax/side/hotSearch"
    headers = {**HEADERS, "Referer": "https://weibo.com/"}
    data = safe_get(url, headers=headers, json_mode=True)
    items = data.get("data", {}).get("realtime", [])
    return [i.get("word", "") for i in items[:20] if i.get("word")]


@retry()
def fetch_zhihu_hot():
    """知乎热榜"""
    url = "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=20"
    headers = {**HEADERS, "Referer": "https://www.zhihu.com/"}
    data = safe_get(url, headers=headers, json_mode=True)
    items = data.get("data", [])
    return [
        i.get("target", {}).get("title", "")
        for i in items[:20] if i.get("target", {}).get("title")
    ]


@retry()
def fetch_toutiao_hot():
    """今日头条热榜"""
    url = "https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc"
    headers = {**HEADERS, "Referer": "https://www.toutiao.com/"}
    data = safe_get(url, headers=headers, json_mode=True)
    items = data.get("data", [])
    return [
        i.get("Title", "") or i.get("title", "")
        for i in items[:20] if i.get("Title") or i.get("title")
    ]


@retry()
def fetch_bilibili_hot():
    """B站热门"""
    url = "https://api.bilibili.com/x/web-interface/ranking/v2?rid=0&type=all"
    headers = {**HEADERS, "Referer": "https://www.bilibili.com/"}
    data = safe_get(url, headers=headers, json_mode=True)
    videos = data.get("data", {}).get("list", [])
    return [
        f"{v.get('title', '')}（播放:{v.get('stat', {}).get('view', 0)}）"
        for v in videos[:15] if v.get("title")
    ]


# ── 国际新闻 ──

@retry()
def fetch_newsapi(category=""):
    """NewsAPI 国际新闻"""
    url = "https://newsapi.org/v2/top-headlines"
    params = {"apiKey": NEWS_API_KEY, "language": "en", "pageSize": 20}
    if category:
        params["category"] = category
    data = safe_get(url, params=params, json_mode=True)
    if data.get("status") != "ok":
        return []
    return [
        f"{a['title']}（{a['source']['name']}）"
        for a in data.get("articles", []) if a.get("title")
    ]


# ── 技术社区 ──

@retry()
def fetch_hackernews():
    """Hacker News 热榜（Firebase API，极稳定）"""
    top_ids = safe_get(
        "https://hacker-news.firebaseio.com/v0/topstories.json",
        json_mode=True,
    )
    ids = top_ids[:20]

    def get_hn_item(iid):
        item = safe_get(
            f"https://hacker-news.firebaseio.com/v0/item/{iid}.json",
            json_mode=True,
        )
        title = item.get("title", "")
        score = item.get("score", 0)
        url_item = item.get("url", "")
        return f"[{score}⭐] {title}  {url_item}" if title else None

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(get_hn_item, ids))

    items = [r for r in results if r]
    items.sort(key=lambda x: int(x.split("⭐")[0].strip("[]")), reverse=True)
    return items[:15]


@retry()
def fetch_github_trending():
    """GitHub Trending 今日热门仓库"""
    url = "https://github.com/trending"
    resp = safe_get(url)
    soup = BeautifulSoup(resp.text, "html.parser")
    results = []
    for repo in soup.select("article.Box-row")[:20]:
        name_el = repo.select_one("h2 a")
        desc_el = repo.select_one("p")
        stars_el = repo.select_one("a[href*='stargazers']")
        if name_el:
            name = name_el.get_text(strip=True).replace(" ", "")
            desc = desc_el.get_text(strip=True) if desc_el else ""
            stars = stars_el.get_text(strip=True) if stars_el else "0"
            results.append(f"{name} ⭐{stars}  {desc}")
    return results


@retry()
def fetch_reddit():
    """Reddit r/all 今日热帖"""
    url = "https://www.reddit.com/r/all/top/.json?limit=20&t=day"
    headers = {**HEADERS, "Accept": "application/json"}
    data = safe_get(url, headers=headers, json_mode=True)
    children = data.get("data", {}).get("children", [])
    items = []
    for child in children[:20]:
        c = child.get("data", {})
        title = c.get("title", "")
        sub = c.get("subreddit", "")
        score = c.get("score", 0)
        comments = c.get("num_comments", 0)
        url_r = c.get("url", "")
        if title:
            items.append(f"[⬆{score}/💬{comments}] r/{sub}：{title}  {url_r}")
    return items


# ════════════════════════════════════════════════
# 聚合调度
# ════════════════════════════════════════════════

SCRAPERS = {
    "百度热搜":      fetch_baidu_hot,
    "微博热搜":      fetch_weibo_hot,
    "知乎热榜":      fetch_zhihu_hot,
    "今日头条热榜":  fetch_toutiao_hot,
    "B站热门":       fetch_bilibili_hot,
    "国际综合":      lambda: fetch_newsapi(""),
    "国际科技":      lambda: fetch_newsapi("technology"),
    "国际商业":      lambda: fetch_newsapi("business"),
    "Hacker News":   fetch_hackernews,
    "GitHub Trending": fetch_github_trending,
    "Reddit 热帖":   fetch_reddit,
}


def fetch_all_sources():
    """并行抓取所有数据源"""
    logger.info("📡 并行抓取 %d 个数据源...", len(SCRAPERS))
    sources = {}

    with ThreadPoolExecutor(max_workers=12) as executor:
        future_map = {
            executor.submit(func): name
            for name, func in SCRAPERS.items()
        }
        for fut in as_completed(future_map):
            name = future_map[fut]
            try:
                result = fut.result()
                sources[name] = result
                logger.info("  ✅ %s：%d 条", name, len(result))
            except Exception as e:
                sources[name] = []
                logger.error("  ❌ %s 异常: %s", name, e)

    total = sum(len(v) for v in sources.values())
    logger.info("📊 共抓取 %d 条热点数据", total)
    return sources


# ════════════════════════════════════════════════
# AI 分析
# ════════════════════════════════════════════════

def format_source_block(items):
    return "\n".join(f"- {it}" for it in items) if items else "（暂无数据）"


def analyze_and_report(sources, focus=""):
    now = datetime.now().strftime("%Y年%m月%d日 %H:%M")
    focus_text = (
        f"\n⚠️ 用户特别关注方向：{focus}，请重点分析。"
        if focus else ""
    )

    parts = []
    for name in SCRAPERS:
        items = sources.get(name, [])
        parts.append(f"【{name}】\n{format_source_block(items)}")
    sources_text = "\n\n".join(parts)

    prompt = f"""你是一位资深时事分析师。以下是今日从多个平台抓取的全网热点数据，请完成以下工作：

第一步：去重整理——合并相同或相似的话题，不要重复出现。
第二步：按热度排序——综合多平台出现频次，判断哪些话题最受关注。
第三步：深度分析——解释背景、意义和影响。{focus_text}

原始热点数据如下：

{sources_text}

请按以下格式输出完整分析报告：

📰 今日热点深度简报 {now}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【今日TOP5重点事件深度分析】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔥 NO.1 【事件标题】
热度来源：（出现在哪些平台）
事件背景：（来龙去脉，100字左右）
核心影响：（对哪些人、哪些领域产生影响）
后续预测：（接下来可能的走向）

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
（5-8条次要热点，每条2-3句话）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【今日整体态势判断】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
（200字左右，宏观分析今日舆论和国际局势走向）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【今日关键词】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
（8-10个关键词，# 标签格式）"""

    logger.info("🤖 AI 分析中（模型: moonshot-v1-32k）...")
    response = client.chat.completions.create(
        model="moonshot-v1-32k",
        max_tokens=4000,
        temperature=0.7,
        messages=[{"role": "user", "content": prompt}],
    )
    content = response.choices[0].message.content
    logger.info("✅ AI 分析完成（%d 字符）", len(content))
    return content


# ════════════════════════════════════════════════
# 输出
# ════════════════════════════════════════════════

def save_report(content):
    os.makedirs("news_reports", exist_ok=True)
    filename = f"news_reports/简报_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    logger.info("💾 简报已保存至: %s", filename)


def send_email(content):
    try:
        if not QQ_EMAIL or not QQ_PASSWORD:
            logger.warning("⚠️ QQ邮箱未配置，跳过邮件发送")
            return

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"今日热点简报 {datetime.now().strftime('%Y年%m月%d日')}"
        msg["From"] = QQ_EMAIL
        msg["To"] = RECIPIENT
        msg.attach(MIMEText(content, "plain", "utf-8"))

        with smtplib.SMTP_SSL("smtp.qq.com", 465) as server:
            server.login(QQ_EMAIL, QQ_PASSWORD)
            server.sendmail(QQ_EMAIL, RECIPIENT, msg.as_string())

        logger.info("✅ 简报已发送至 %s", RECIPIENT)
    except Exception as e:
        logger.error("❌ 邮件发送失败: %s", e)


# ════════════════════════════════════════════════
# 主入口
# ════════════════════════════════════════════════

def main():
    logger.info("=" * 45)
    logger.info("📰 全网热点聚合分析器 v2.0")
    logger.info("   运行时间: %s", datetime.now().strftime("%Y年%m月%d日 %H:%M"))
    logger.info("=" * 45)

    sources = fetch_all_sources()
    report = analyze_and_report(sources)

    print("\n" + report + "\n")
    save_report(report)
    send_email(report)

    logger.info("✅ 任务完成")


if __name__ == "__main__":
    main()
