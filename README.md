# 全网热点聚合分析器 News Reporter

每日自动抓取多平台热点 → AI 深度分析 → QQ 邮箱推送

## 数据源

| 平台 | 类型 | 方式 |
|------|------|------|
| 百度热搜 | 国内热点 | HTML 抓取 |
| 微博热搜 | 国内热点 | API |
| 知乎热榜 | 国内热点 | API |
| 今日头条热榜 | 国内热点 | API |
| B站热门 | 视频热点 | API |
| NewsAPI | 国际新闻 | API（需 Key） |
| Hacker News | 技术社区 | Firebase API |
| GitHub Trending | 开源项目 | HTML 抓取 |
| Reddit 热帖 | 社区热点 | JSON API |

## 工作流程

1. **并行抓取** 11 个数据源（~10 秒）
2. **Kimi AI**（moonshot-v1-32k）深度分析 → 生成 TOP5 简报
3. 简报保存至 `news_reports/` 目录
4. 通过 **QQ邮箱** 推送到指定收件人

## 配置

在 GitHub 仓库 Settings → Secrets and variables → Actions 中设置：

| Secret | 说明 |
|--------|------|
| `KIMI_API_KEY` | Kimi API Key（必填）|
| `NEWS_API_KEY` | NewsAPI Key（可选，影响国际新闻）|
| `QQ_EMAIL` | QQ邮箱地址（必填，用于发送）|
| `QQ_PASSWORD` | QQ邮箱 SMTP 授权码（必填）|

## 运行方式

**GitHub Actions（自动）：** 每天 UTC 01:30（北京时间 09:30）

**手动：**
```bash
pip install -r requirements.txt
python news.py
```

## 许可

MIT
