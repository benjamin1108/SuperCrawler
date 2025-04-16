import asyncio
import json
import time
import re
import os
import logging
from pathlib import Path
from urllib.parse import urljoin, urlparse

import yaml
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from playwright.async_api import async_playwright
import requests
from typing import Dict, List, Set, Optional, Any, Tuple
from extractor import Extractor

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("crawler.log", encoding='utf-8')
    ]
)
logger = logging.getLogger("Crawler")

class Crawler:
    """
    爬虫核心类，负责URL的爬取、内容下载和处理
    """
    def __init__(self, config: Dict[str, Any], 
                 output_dir: str = "output",
                 delay: float = 2.0,
                 max_retries: int = 3,
                 timeout: int = 30):
        """
        初始化爬虫实例
        
        参数:
            config: 爬虫配置
            output_dir: 输出目录
            delay: 请求间隔时间(秒)
            max_retries: 最大重试次数
            timeout: 请求超时时间(秒)
        """
        self.config = config
        self.name = config.get("name", "默认爬虫")
        self.start_url = config.get("start_url")
        self.base_url = config.get("base_url", self._get_base_url(self.start_url))
        self.url_patterns = config.get("url_patterns", {})
        self.schema_id = config.get("schema")
        self.schema = config.get("extraction_schema", {})
        
        self.output_dir = os.path.join(output_dir, self._get_domain(self.start_url))
        self.delay = delay
        self.max_retries = max_retries
        self.timeout = timeout
        
        self.visited_urls = set()
        self.failed_urls = set()
        self.extracted_urls = []
        self.extractor = Extractor(self.base_url)
        
        # 创建输出目录
        os.makedirs(self.output_dir, exist_ok=True)
        
        logger.info(f"初始化爬虫: {self.name}")
        logger.info(f"起始URL: {self.start_url}")
        logger.info(f"基础URL: {self.base_url}")
        logger.info(f"输出目录: {self.output_dir}")
    
    def start(self, max_urls: int = 100) -> Tuple[int, int]:
        """
        启动爬虫，开始处理URL
        
        参数:
            max_urls: 最大爬取URL数量
            
        返回:
            (成功处理的URL数量, 失败的URL数量)
        """
        if not self.start_url:
            logger.error("缺少起始URL，爬虫无法启动")
            return 0, 0
        
        urls_to_visit = [self.start_url]
        processed_count = 0
        failed_count = 0
        
        logger.info(f"爬虫启动: {self.name}")
        logger.info(f"最大URL数量: {max_urls}")
        
        while urls_to_visit and processed_count < max_urls:
            # 获取下一个URL
            current_url = urls_to_visit.pop(0)
            
            # 如果已经访问过，跳过
            if current_url in self.visited_urls or current_url in self.failed_urls:
                continue
            
            logger.info(f"处理URL [{processed_count + 1}/{max_urls}]: {current_url}")
            
            # 下载并处理页面
            success, new_urls = self._process_url(current_url)
            
            if success:
                processed_count += 1
                self.visited_urls.add(current_url)
                
                # 添加新发现的URL到队列
                for url in new_urls:
                    if (url not in self.visited_urls and 
                        url not in self.failed_urls and 
                        url not in urls_to_visit and
                        self._should_follow_url(url)):
                        urls_to_visit.append(url)
                        logger.debug(f"添加新URL到队列: {url}")
            else:
                failed_count += 1
                self.failed_urls.add(current_url)
            
            # 请求延迟
            if urls_to_visit:
                time.sleep(self.delay)
        
        logger.info(f"爬虫 {self.name} 完成")
        logger.info(f"成功处理: {processed_count} 个URL")
        logger.info(f"失败: {failed_count} 个URL")
        
        return processed_count, failed_count
    
    def _process_url(self, url: str) -> Tuple[bool, List[str]]:
        """
        处理单个URL，下载内容并提取信息
        
        返回:
            (是否成功, 提取的新URL列表)
        """
        new_urls = []
        
        # 尝试下载内容
        html_content = self._download_page(url)
        if not html_content:
            return False, new_urls
        
        # 提取URL
        try:
            if self.schema:
                extracted_urls = self.extractor.extract_urls(html_content, self.schema.get("urls", {}))
                new_urls.extend(extracted_urls)
            
            # 提取内容
            if self._is_content_page(url):
                self._extract_and_save_content(url, html_content)
        except Exception as e:
            logger.error(f"处理URL {url} 时出错: {e}")
            return False, new_urls
        
        return True, new_urls
    
    def _download_page(self, url: str) -> Optional[str]:
        """下载页面内容"""
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.debug(f"下载页面 {url} (尝试 {attempt}/{self.max_retries})")
                
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                    "Connection": "keep-alive",
                }
                
                response = requests.get(url, headers=headers, timeout=self.timeout)
                response.raise_for_status()
                
                # 检查内容类型
                content_type = response.headers.get("Content-Type", "")
                if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                    logger.warning(f"URL {url} 不是HTML内容: {content_type}")
                    return None
                
                # 设置正确的编码
                if response.encoding == "ISO-8859-1":
                    response.encoding = response.apparent_encoding
                
                return response.text
            
            except requests.exceptions.RequestException as e:
                logger.error(f"下载 {url} 失败 (尝试 {attempt}/{self.max_retries}): {e}")
                if attempt < self.max_retries:
                    # 增加重试延迟
                    time.sleep(self.delay * attempt)
        
        return None
    
    def _extract_and_save_content(self, url: str, html_content: str) -> bool:
        """提取并保存内容"""
        try:
            if not self.schema:
                logger.warning(f"未提供提取模式，无法提取内容: {url}")
                return False
            
            # 提取内容
            content_schema = self.schema.get("content", {})
            content = self.extractor.extract_content(html_content, content_schema)
            
            if not content:
                logger.warning(f"未能从 {url} 提取内容")
                return False
            
            # 添加元数据
            content["url"] = url
            content["crawled_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            
            # 保存内容
            filename = self._generate_filename(url, content)
            file_path = os.path.join(self.output_dir, filename)
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content.get("raw_content", ""))
            
            # 保存元数据
            meta_path = os.path.join(self.output_dir, f"{os.path.splitext(filename)[0]}.json")
            with open(meta_path, "w", encoding="utf-8") as f:
                import json
                json.dump(content, f, ensure_ascii=False, indent=2)
            
            logger.info(f"内容已保存: {file_path}")
            return True
        
        except Exception as e:
            logger.error(f"提取和保存内容失败 {url}: {e}")
            return False
    
    def _generate_filename(self, url: str, content: Dict) -> str:
        """根据URL和内容生成文件名"""
        # 尝试使用标题
        title = content.get("title", "")
        if title:
            # 清理标题，去除不合法字符
            import re
            title = re.sub(r'[\\/*?:"<>|]', "_", title)
            title = title.strip()
            if len(title) > 50:
                title = title[:50]
            return f"{title}.md"
        
        # 使用URL的最后部分
        path = urlparse(url).path
        filename = os.path.basename(path)
        
        if not filename or filename.endswith("/"):
            # 生成基于URL的唯一文件名
            import hashlib
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            return f"page_{url_hash}.md"
        
        return f"{os.path.splitext(filename)[0]}.md"
    
    def _should_follow_url(self, url: str) -> bool:
        """判断是否应该跟踪此URL"""
        # 检查是否与基础URL同源
        if not url.startswith(self.base_url):
            return False
        
        # 检查URL模式
        if self.url_patterns:
            import re
            # 包含模式
            include_patterns = self.url_patterns.get("include", [])
            if include_patterns:
                matched = False
                for pattern in include_patterns:
                    if re.search(pattern, url):
                        matched = True
                        break
                if not matched:
                    return False
            
            # 排除模式
            exclude_patterns = self.url_patterns.get("exclude", [])
            for pattern in exclude_patterns:
                if re.search(pattern, url):
                    return False
        
        return True
    
    def _is_content_page(self, url: str) -> bool:
        """判断URL是否为内容页面"""
        # 如果配置了内容页面模式，使用它
        content_patterns = self.url_patterns.get("content", [])
        if content_patterns:
            import re
            for pattern in content_patterns:
                if re.search(pattern, url):
                    return True
            return False
        
        # 没有配置时的默认行为：非目录页面都视为内容页面
        path = urlparse(url).path
        return not path.endswith("/")
    
    def _get_base_url(self, url: str) -> str:
        """从URL中提取基础URL"""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"
    
    def _get_domain(self, url: str) -> str:
        """从URL中获取域名作为目录名"""
        parsed = urlparse(url)
        return parsed.netloc


# 用于测试
if __name__ == "__main__":
    # 加载示例工作流
    with open("workflows/example.yaml", 'r', encoding='utf-8') as f:
        workflow = yaml.safe_load(f)
    
    # 初始化并运行爬虫
    crawler = Crawler(workflow)
    asyncio.run(crawler.start()) 