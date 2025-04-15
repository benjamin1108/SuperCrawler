import json
import logging
import re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import markdownify
from typing import Dict, List, Any, Optional

# 配置日志
logger = logging.getLogger("Extractor")

class Extractor:
    """
    内容提取器，负责从HTML内容中提取URLs和结构化数据
    """
    def __init__(self, base_url: str):
        """
        初始化提取器
        
        参数:
            base_url: 基础URL，用于将相对URL转换为绝对URL
        """
        self.base_url = base_url
    
    def extract_urls(self, html_content: str, url_schema: Dict) -> List[str]:
        """
        从HTML内容中提取URLs
        
        参数:
            html_content: HTML内容
            url_schema: URL提取模式配置
            
        返回:
            提取的URL列表
        """
        if not html_content:
            logger.warning("HTML内容为空，无法提取URL")
            return []
        
        urls = set()  # 使用集合去重
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 获取配置 - 支持新旧字段名
            container_selector = url_schema.get("container", url_schema.get("container_selector", "body"))
            link_selector = url_schema.get("link_selector", "a")
            attribute = url_schema.get("attribute", url_schema.get("url_attribute", "href"))
            
            # 查找容器元素
            if container_selector != "body":
                containers = soup.select(container_selector)
                if not containers:
                    logger.warning(f"未找到容器元素: {container_selector}，使用整个文档")
                    containers = [soup]
            else:
                containers = [soup]
            
            # 从每个容器中提取链接
            for container in containers:
                links = container.select(link_selector)
                logger.debug(f"在容器中找到 {len(links)} 个链接元素")
                
                for link in links:
                    url = link.get(attribute)
                    if url:
                        # 跳过空链接、锚点链接和JavaScript链接
                        if not url or url.startswith('#') or url.startswith('javascript:'):
                            continue
                        
                        # 将相对URL转换为绝对URL
                        absolute_url = urljoin(self.base_url, url)
                        
                        # 只保留同域名的URL
                        if urlparse(absolute_url).netloc == urlparse(self.base_url).netloc:
                            urls.add(absolute_url)
                        else:
                            logger.debug(f"跳过外部链接: {absolute_url}")
                            
            # 过滤URL
            if url_schema.get("patterns"):
                filtered_urls = []
                include_patterns = url_schema.get("patterns", {}).get("include", [])
                exclude_patterns = url_schema.get("patterns", {}).get("exclude", [])
                
                for url in urls:
                    # 应用包含模式
                    if include_patterns:
                        if not any(re.search(pattern, url) for pattern in include_patterns):
                            continue
                    
                    # 应用排除模式
                    if exclude_patterns and any(re.search(pattern, url) for pattern in exclude_patterns):
                        continue
                    
                    filtered_urls.append(url)
                
                urls = set(filtered_urls)
            
            logger.info(f"提取到 {len(urls)} 个URL")
            return list(urls)
            
        except Exception as e:
            logger.error(f"提取URL时出错: {e}")
            return []
    
    def extract_content(self, html_content: str, content_schema: Dict) -> Dict[str, Any]:
        """
        从HTML内容中提取结构化内容
        
        参数:
            html_content: HTML内容
            content_schema: 内容提取模式配置
            
        返回:
            提取的结构化内容
        """
        if not html_content:
            logger.warning("HTML内容为空，无法提取内容")
            return {}
        
        result = {}
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 提取标题 - 支持新旧字段名
            title_selector = content_schema.get("title", content_schema.get("title_selector", "h1"))
            title_element = soup.select_one(title_selector)
            if title_element:
                result["title"] = title_element.get_text().strip()
            else:
                logger.warning(f"未找到标题元素: {title_selector}")
            
            # 提取作者 - 支持新旧字段名
            author_selector = content_schema.get("author", content_schema.get("author_selector"))
            if author_selector:
                author_element = soup.select_one(author_selector)
                if author_element:
                    result["author"] = author_element.get_text().strip()
            
            # 提取日期 - 支持新旧字段名
            date_selector = content_schema.get("date", content_schema.get("date_selector"))
            if date_selector:
                date_element = soup.select_one(date_selector)
                if date_element:
                    # 优先从日期属性中获取
                    date_attr = content_schema.get("date_attribute")
                    if date_attr and date_element.has_attr(date_attr):
                        result["date"] = date_element[date_attr]
                    else:
                        result["date"] = date_element.get_text().strip()
            
            # 提取主要内容 - 支持新旧字段名
            content_selector = content_schema.get("content", content_schema.get("content_container_selector", "article"))
            content_element = soup.select_one(content_selector)
            
            if not content_element:
                logger.warning(f"未找到主要内容元素: {content_selector}")
                # 尝试常见的内容容器选择器
                for selector in ["article", "main", ".content", ".entry-content", ".post-content"]:
                    content_element = soup.select_one(selector)
                    if content_element:
                        logger.info(f"使用备选选择器找到内容: {selector}")
                        break
            
            if content_element:
                # 提取原始HTML
                raw_html = str(content_element)
                
                # 移除不需要的元素
                if "remove" in content_schema:
                    remove_selectors = content_schema.get("remove", [])
                    for selector in remove_selectors:
                        for element in content_element.select(selector):
                            element.decompose()
                
                # 转换为Markdown
                markdown = markdownify.markdownify(str(content_element), heading_style="ATX")
                
                result["raw_content"] = markdown
                result["html_content"] = raw_html
            else:
                logger.warning("未能找到内容元素")
            
            # 提取其他自定义字段
            if "custom_fields" in content_schema:
                custom_fields = content_schema.get("custom_fields", {})
                for field_name, selector in custom_fields.items():
                    element = soup.select_one(selector)
                    if element:
                        if isinstance(selector, dict) and "attribute" in selector:
                            # 提取属性值
                            attribute = selector["attribute"]
                            if element.has_attr(attribute):
                                result[field_name] = element[attribute]
                        else:
                            # 提取文本
                            result[field_name] = element.get_text().strip()
            
            return result
            
        except Exception as e:
            logger.error(f"提取内容时出错: {e}")
            return {}
    
    def clean_text(self, text: str) -> str:
        """清理文本，移除多余空白"""
        if not text:
            return ""
        
        # 替换多个空白为单个空格
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def extract_metadata(self, soup: BeautifulSoup) -> Dict[str, str]:
        """提取页面元数据"""
        metadata = {}
        
        # 提取页面标题
        title = soup.title
        if title:
            metadata['title'] = title.string.strip()
        
        # 提取元标签
        meta_tags = {
            'description': ['description', 'og:description'],
            'keywords': ['keywords'],
            'author': ['author', 'og:author'],
            'published_time': ['article:published_time', 'og:published_time', 'published_time'],
            'modified_time': ['article:modified_time', 'og:modified_time', 'modified_time'],
            'image': ['og:image', 'twitter:image']
        }
        
        for key, meta_names in meta_tags.items():
            for name in meta_names:
                # 检查 name 属性
                meta = soup.find('meta', attrs={'name': name})
                if not meta:
                    # 检查 property 属性
                    meta = soup.find('meta', attrs={'property': name})
                
                if meta and meta.has_attr('content') and meta['content'].strip():
                    metadata[key] = meta['content'].strip()
                    break
        
        return metadata
    
    def extract_custom_element(self, html_content, custom_schema):
        """从HTML中提取自定义元素"""
        logger.info("正在从HTML中提取自定义元素")
        results = []
        
        if not html_content:
            logger.error("HTML内容为空")
            return results
        
        if not custom_schema or not isinstance(custom_schema, dict):
            logger.error("自定义Schema格式无效")
            return results
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            elements = custom_schema.get('elements', [])
            
            if not elements:
                logger.error("Schema中没有elements字段")
                return results
            
            for idx, element_def in enumerate(elements):
                logger.info(f"处理第 {idx+1}/{len(elements)} 个元素定义")
                
                # 获取选择器信息
                css_selector = element_def.get('cssSelector')
                xpath = element_def.get('xpath')
                
                # 只支持CSS选择器
                if not css_selector:
                    logger.warning(f"元素 #{idx+1} 没有提供CSS选择器，跳过")
                    continue
                
                # 查找元素
                try:
                    found_elements = soup.select(css_selector)
                    logger.info(f"CSS选择器 '{css_selector}' 找到 {len(found_elements)} 个元素")
                    
                    for i, el in enumerate(found_elements):
                        element_info = {
                            'index': i,
                            'html': str(el),
                            'text': el.get_text(),
                            'selector': css_selector
                        }
                        results.append(element_info)
                except Exception as e:
                    logger.error(f"CSS选择器查找出错: {e}")
            
            logger.info(f"总共提取了 {len(results)} 个元素")
            return results
        except Exception as e:
            logger.error(f"提取自定义元素时出错: {e}")
            return results
    
    def html_to_markdown(self, html_content):
        """将HTML转换为Markdown"""
        if not html_content:
            return ""
        
        try:
            return markdownify.markdownify(html_content, heading_style="ATX", strip=['script', 'style'], keep_attrs=['src', 'alt', 'href'])
        except Exception as e:
            logger.error(f"HTML转换为Markdown时出错: {e}")
            return "" 