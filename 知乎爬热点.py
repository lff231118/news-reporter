import requests
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime
from pathlib import Path
import logging
import random
from typing import List, Dict, Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ZhihuCrawler:
    """知乎热点爬取工具（优化版）"""
    
    # 多个User-Agent池
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    ]
    
    def __init__(self):
        self.base_url = "https://www.zhihu.com/"
        self.api_url = "https://www.zhihu.com/api/v3/feed/topstory"
        self.timeout = 15
        self.hot_topics: List[Dict] = []
        self.retry_count = 3
        self.retry_delay = 2
        
    def get_headers(self) -> Dict:
        """获取随机User-Agent的请求头"""
        return {
            'User-Agent': random.choice(self.USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Referer': 'https://www.zhihu.com/',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
        }
        
    def get_page_content(self, url: str, use_api: bool = False) -> Optional[str]:
        """获取页面内容，带重试机制"""
        for attempt in range(self.retry_count):
            try:
                logger.info(f"正在请求 (尝试 {attempt + 1}/{self.retry_count}): {url}")
                
                headers = self.get_headers()
                if use_api:
                    headers['X-Requested-With'] = 'XMLHttpRequest'
                
                response = requests.get(
                    url, 
                    headers=headers, 
                    timeout=self.timeout,
                    allow_redirects=True
                )
                response.encoding = 'utf-8'
                response.raise_for_status()
                
                logger.info(f"请求成功 (状态码: {response.status_code})")
                return response.text
                
            except requests.Timeout:
                logger.warning(f"请求超时，{self.retry_delay}秒后重试...")
                time.sleep(self.retry_delay)
            except requests.ConnectionError:
                logger.warning(f"连接错误，{self.retry_delay}秒后重试...")
                time.sleep(self.retry_delay)
            except requests.RequestException as e:
                logger.warning(f"请求异常: {e}，{self.retry_delay}秒后重试...")
                time.sleep(self.retry_delay)
        
        logger.error("超过最大重试次数")
        return None
        
    def parse_hot_topics(self, html_content: str) -> List[Dict]:
        """解析热点话题（改进版，多种策略）"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            hot_items = []
            
            logger.info("开始解析页面...")
            
            # 策略1: 查找所有文章链接和标题
            logger.info("策略1: 寻找文章标题...")
            articles = soup.find_all('div', class_=['Feed-item', 'PostItem', 'post-item'])
            if articles:
                for article in articles[:15]:
                    title_elem = article.find(['h2', 'h3', 'span'])
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        if title and len(title) > 3:
                            hot_items.append({
                                'title': title,
                                'source': 'feed-item'
                            })
            
            # 策略2: 查找热榜区域
            if not hot_items:
                logger.info("策略2: 寻找热榜...")
                hot_list = soup.find('div', {'data-testid': 'HotList'})
                if not hot_list:
                    hot_list = soup.find('div', class_=['hot-list', 'HotList'])
                
                if hot_list:
                    items = hot_list.find_all(['li', 'div'], limit=20)
                    for item in items:
                        title = item.get_text(strip=True)
                        if title and len(title) > 3:
                            hot_items.append({
                                'title': title,
                                'source': 'hot-list'
                            })
            
            # 策略3: 查找所有链接中的文本
            if not hot_items:
                logger.info("策略3: 从链接提取...")
                links = soup.find_all('a', href=True)
                for link in links[:20]:
                    title = link.get_text(strip=True)
                    if title and 3 < len(title) < 200 and not title.startswith('http'):
                        # 避免重复
                        if not any(item['title'] == title for item in hot_items):
                            hot_items.append({
                                'title': title,
                                'source': 'link',
                                'url': link.get('href', '#')
                            })
            
            # 策略4: 查找所有文本容器
            if not hot_items:
                logger.info("策略4: 从文本容器提取...")
                containers = soup.find_all(['article', 'section', 'main'])
                for container in containers:
                    titles = container.find_all(['h1', 'h2', 'h3', 'h4'], limit=5)
                    for title_elem in titles:
                        title = title_elem.get_text(strip=True)
                        if title and 3 < len(title) < 200:
                            hot_items.append({
                                'title': title,
                                'source': 'container'
                            })
            
            # 去重
            seen = set()
            unique_items = []
            for item in hot_items:
                if item['title'] not in seen:
                    seen.add(item['title'])
                    unique_items.append(item)
            
            self.hot_topics = unique_items[:20]  # 最多20个
            logger.info(f"成功获取 {len(self.hot_topics)} 个热点")
            
            return self.hot_topics
            
        except Exception as e:
            logger.error(f"解析页面失败: {e}")
            return []
    
    def crawl_hot_topics(self) -> bool:
        """爬取知乎热点主函数（改进版）"""
        logger.info("="*60)
        logger.info("开始爬取知乎热点（优化版）")
        logger.info("="*60)
        
        # 方法1: 尝试获取首页内容
        logger.info("\n[方法1] 尝试从首页获取...")
        html = self.get_page_content(self.base_url)
        if html:
            topics = self.parse_hot_topics(html)
            if topics:
                logger.info("✓ 成功获取热点!")
                return True
        
        # 方法2: 尝试获取热榜页面
        logger.info("\n[方法2] 尝试从热榜页面获取...")
        hot_url = "https://www.zhihu.com/hot"
        html = self.get_page_content(hot_url)
        if html:
            topics = self.parse_hot_topics(html)
            if topics:
                logger.info("✓ 从热榜页面成功获取!")
                return True
        
        # 方法3: 尝试获取推荐页面
        logger.info("\n[方法3] 尝试从推荐页面获取...")
        recommend_url = "https://www.zhihu.com/recommended"
        html = self.get_page_content(recommend_url)
        if html:
            topics = self.parse_hot_topics(html)
            if topics:
                logger.info("✓ 从推荐页面成功获取!")
                return True
        
        # 如果没有获取到任何数据
        if not self.hot_topics:
            logger.warning("\n⚠ 未能爬取到热点数据")
            logger.info("可能原因:")
            logger.info("1. 知乎网站要求JavaScript渲染（需要使用Selenium或Playwright）")
            logger.info("2. IP被限制或需要登录")
            logger.info("3. 网络连接问题")
            return False
        
        logger.info("✓ 爬取完成!")
        return True
    
    def save_to_json(self, filename: Optional[str] = None) -> bool:
        """保存为JSON文件"""
        if not self.hot_topics:
            logger.warning("没有热点数据可保存")
            return False
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"zhihu_hot_{timestamp}.json"
        
        try:
            data = {
                'crawl_time': datetime.now().isoformat(),
                'total_count': len(self.hot_topics),
                'topics': self.hot_topics
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✓ JSON已保存到: {filename}")
            return True
        except Exception as e:
            logger.error(f"✗ 保存JSON失败: {e}")
            return False
    
    def save_to_markdown(self, filename: Optional[str] = None) -> bool:
        """保存为Markdown文件"""
        if not self.hot_topics:
            logger.warning("没有热点数据可保存")
            return False
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"zhihu_hot_{timestamp}.md"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("# 知乎热点\n\n")
                f.write(f"**更新时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write(f"**热点总数**: {len(self.hot_topics)}\n\n")
                f.write("---\n\n")
                
                for idx, topic in enumerate(self.hot_topics, 1):
                    f.write(f"## {idx}. {topic['title']}\n\n")
                    f.write(f"- **来源**: {topic.get('source', '未知')}\n")
                    if 'url' in topic:
                        f.write(f"- **链接**: {topic['url']}\n")
                    f.write("\n")
            
            logger.info(f"✓ Markdown已保存到: {filename}")
            return True
        except Exception as e:
            logger.error(f"✗ 保存Markdown失败: {e}")
            return False
    
    def save_to_csv(self, filename: Optional[str] = None) -> bool:
        """保存为CSV文件"""
        if not self.hot_topics:
            logger.warning("没有热点数据可保存")
            return False
        
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"zhihu_hot_{timestamp}.csv"
        
        try:
            import csv
            with open(filename, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['序号', '标题', '来源', '链接', '采集时间'])
                writer.writeheader()
                
                for idx, topic in enumerate(self.hot_topics, 1):
                    writer.writerow({
                        '序号': idx,
                        '标题': topic['title'],
                        '来源': topic.get('source', '未知'),
                        '链接': topic.get('url', ''),
                        '采集时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
            
            logger.info(f"✓ CSV已保存到: {filename}")
            return True
        except Exception as e:
            logger.error(f"✗ 保存CSV失败: {e}")
            return False
    
    def display_topics(self):
        """显示热点列表"""
        if not self.hot_topics:
            print("❌ 没有热点数据")
            return
        
        print("\n" + "="*70)
        print(f"📊 知乎热点 (共 {len(self.hot_topics)} 个)")
        print(f"⏰ 更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70 + "\n")
        
        for idx, topic in enumerate(self.hot_topics, 1):
            print(f"{idx:2d}. {topic['title']}")
            if 'source' in topic:
                print(f"    📌 来源: {topic['source']}")
            if 'url' in topic:
                print(f"    🔗 链接: {topic['url']}")
            print()
        
        print("="*70 + "\n")


def main():
    """主函数"""
    print("\n")
    print("╔" + "="*68 + "╗")
    print("║" + " "*15 + "知乎热点爬取工具 v2.0 (优化版)" + " "*18 + "║")
    print("╚" + "="*68 + "╝")
    print()
    
    try:
        # 创建爬虫实例
        crawler = ZhihuCrawler()
        
        # 爬取热点
        success = crawler.crawl_hot_topics()
        
        if success and crawler.hot_topics:
            # 显示热点
            crawler.display_topics()
            
            # 保存数据
            print("\n💾 正在保存数据...")
            crawler.save_to_json()
            crawler.save_to_markdown()
            crawler.save_to_csv()
            
            print("\n✅ 爬取完成!")
            return True
        else:
            print("\n⚠️  爬取失败或未获取到数据")
            print("\n建议方案:")
            print("1️⃣  使用动态渲染方案（Selenium/Playwright）")
            print("2️⃣  检查网络连接")
            print("3️⃣  检查IP是否被限制")
            print("4️⃣  查看知乎API是否有变化")
            return False
            
    except KeyboardInterrupt:
        print("\n\n⏹️  用户中断")
        return False
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        logger.exception("详细错误信息:")
        return False


if __name__ == "__main__":
    main()
