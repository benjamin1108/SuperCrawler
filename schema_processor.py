"""
通用Schema处理器，支持多种不同格式的Schema配置
可以处理不同结构的Schema，用于从HTML中提取数据
"""
import json
import logging
from typing import Dict, List, Any, Optional, Union
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import re
import markdownify

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("schema_processor.log", encoding='utf-8')
    ]
)
logger = logging.getLogger("SchemaProcessor")

class SchemaProcessor:
    """通用Schema处理器，可以处理多种不同格式的schema配置"""
    
    def __init__(self, base_url: str):
        """
        初始化Schema处理器
        
        参数:
            base_url: 基础URL，用于将相对URL转换为绝对URL
        """
        self.base_url = base_url
        logger.info(f"初始化SchemaProcessor，基础URL: {base_url}")
    
    def extract_urls(self, html_content: str, schema: Dict) -> List[str]:
        """
        从HTML内容中提取URLs
        
        参数:
            html_content: HTML内容
            schema: Schema配置，支持多种格式
            
        返回:
            提取的URL列表
        """
        if not html_content:
            logger.warning("HTML内容为空，无法提取URL")
            return []
        
        urls = set()  # 使用集合去重
        logger.info("开始从HTML提取URLs")
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 检测schema格式类型
            if self._is_legacy_format(schema):
                # 传统格式 (extractor.py兼容格式)
                logger.info("检测到传统格式Schema")
                urls = self._extract_urls_legacy_format(soup, schema)
            elif self._is_selectors_format(schema):
                # 新的选择器格式
                logger.info("检测到选择器格式Schema")
                urls = self._extract_urls_selectors_format(soup, schema)
            else:
                # 尝试通用方法
                logger.info("未检测到特定格式，尝试通用提取方法")
                urls = self._extract_urls_generic(soup, schema)
            
            logger.info(f"提取到 {len(urls)} 个URL")
            return list(urls)
            
        except Exception as e:
            logger.error(f"提取URL时出错: {e}", exc_info=True)
            return []
    
    def extract_content(self, html_content: str, schema: Dict) -> Dict[str, Any]:
        """
        从HTML内容中提取结构化内容
        
        参数:
            html_content: HTML内容
            schema: 内容提取Schema配置
            
        返回:
            提取的结构化内容
        """
        if not html_content:
            logger.warning("HTML内容为空，无法提取内容")
            return {}
        
        result = {}
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 检测schema格式类型
            if self._is_legacy_format(schema):
                # 传统格式 (extractor.py兼容格式)
                logger.info("检测到传统格式内容Schema")
                result = self._extract_content_legacy_format(soup, schema)
            elif self._is_selectors_format(schema):
                # 新的选择器格式
                logger.info("检测到选择器格式内容Schema")
                result = self._extract_content_selectors_format(soup, schema)
            else:
                # 尝试通用方法
                logger.info("未检测到特定格式，尝试通用提取方法")
                result = self._extract_content_generic(soup, schema)
            
            # 确保content_markdown字段存在
            if 'content' in result and 'content_markdown' not in result:
                result['content_markdown'] = result['content']
                
            if 'html_content' in result and 'content_markdown' not in result:
                result['content_markdown'] = markdownify.markdownify(result['html_content'])
            
            # 确保至少有一些内容
            if not result.get('content_markdown'):
                # 如果所有方法都未能提取内容，尝试获取整个页面内容
                logger.warning("未能提取到结构化内容，尝试使用整个页面内容")
                main_content = soup.find('main') or soup.find('article') or soup.find('body')
                if main_content:
                    result['content_markdown'] = markdownify.markdownify(str(main_content))
                    result['title'] = soup.title.text if soup.title else "未知标题"
            
            # 基本的URL过滤
            urls_found = self._extract_all_links(soup)
            result['urls'] = urls_found
            
            return result
            
        except Exception as e:
            logger.error(f"提取内容时出错: {e}", exc_info=True)
            return {}
    
    def _is_legacy_format(self, schema: Dict) -> bool:
        """检查是否为传统格式的schema"""
        # 传统格式通常具有container, link_selector, attribute等关键字段
        legacy_keys = ['container', 'link_selector', 'attribute', 'content', 'title', 'author', 'date']
        # 如果只是一个content格式，可能在content键的内部有传统格式
        if 'content' in schema and isinstance(schema['content'], dict):
            schema_to_check = schema['content']
        else:
            schema_to_check = schema
            
        return any(key in schema_to_check for key in legacy_keys)
    
    def _is_selectors_format(self, schema: Dict) -> bool:
        """检查是否为新的选择器格式schema"""
        # 新的选择器格式通常有selectors字段，包含元素和选择器定义
        return 'selectors' in schema
    
    def _extract_urls_legacy_format(self, soup: BeautifulSoup, schema: Dict) -> set:
        """使用传统格式schema提取URLs"""
        urls = set()
        
        # 获取URL提取配置
        url_schema = schema.get('urls', schema)  # 可能在urls子字段或者直接在根层级
        
        container_selector = url_schema.get('container', url_schema.get('container_selector', 'body'))
        link_selector = url_schema.get('link_selector', 'a')
        attribute = url_schema.get('attribute', url_schema.get('url_attribute', 'href'))
        
        # 查找容器元素
        if container_selector != 'body':
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
                    
                    # 只保留同域名的URL (可选)
                    # if urlparse(absolute_url).netloc == urlparse(self.base_url).netloc:
                    urls.add(absolute_url)
        
        # 应用URL过滤模式 (如果有)
        if 'patterns' in url_schema:
            filtered_urls = set()
            include_patterns = url_schema.get('patterns', {}).get('include', [])
            exclude_patterns = url_schema.get('patterns', {}).get('exclude', [])
            
            for url in urls:
                # 应用包含模式
                if include_patterns:
                    if not any(re.search(pattern, url) for pattern in include_patterns):
                        continue
                
                # 应用排除模式
                if exclude_patterns and any(re.search(pattern, url) for pattern in exclude_patterns):
                    continue
                
                filtered_urls.add(url)
            
            urls = filtered_urls
        
        return urls
    
    def _extract_urls_selectors_format(self, soup: BeautifulSoup, schema: Dict) -> set:
        """使用选择器格式schema提取URLs"""
        urls = set()
        selectors = schema.get('selectors', [])
        
        for selector_def in selectors:
            # 获取选择器类型和定义
            selector_type = selector_def.get('type')
            css_selector = selector_def.get('selector', {}).get('css')
            xpath_selector = selector_def.get('selector', {}).get('xpath')
            
            # 查找元素
            elements = []
            if css_selector:
                elements = soup.select(css_selector)
            elif xpath_selector:
                # BeautifulSoup不直接支持XPath，但我们可以使用lxml
                try:
                    import lxml.etree
                    dom = lxml.etree.HTML(str(soup))
                    xpath_results = dom.xpath(xpath_selector)
                    # 将xpath结果转换为BeautifulSoup元素
                    for result in xpath_results:
                        element_html = lxml.etree.tostring(result).decode('utf-8')
                        elements.append(BeautifulSoup(element_html, 'html.parser'))
                except ImportError:
                    logger.warning("lxml库未安装，无法使用XPath选择器")
                except Exception as e:
                    logger.error(f"XPath处理出错: {e}")
            
            # 处理找到的元素
            for element in elements:
                # 检查此选择器是否有URL字段提取
                url_field = selector_def.get('fields', {}).get('url')
                
                if url_field:
                    # 使用字段定义提取URL
                    field_type = url_field.get('type')
                    field_selector = url_field.get('selector', '.')
                    field_attribute = url_field.get('attribute')
                    
                    # 找到目标元素
                    target = element
                    if field_selector != '.':
                        targets = element.select(field_selector)
                        if targets:
                            target = targets[0]
                    
                    # 根据类型提取URL
                    if field_type == 'attribute' and field_attribute:
                        url = target.get(field_attribute)
                        if url:
                            absolute_url = urljoin(self.base_url, url)
                            urls.add(absolute_url)
                else:
                    # 默认尝试查找所有a标签
                    for link in element.find_all('a', href=True):
                        url = link['href']
                        if url and not url.startswith('#') and not url.startswith('javascript:'):
                            absolute_url = urljoin(self.base_url, url)
                            urls.add(absolute_url)
        
        return urls
    
    def _extract_urls_generic(self, soup: BeautifulSoup, schema: Dict) -> set:
        """通用的URL提取方法，尝试各种提取策略"""
        urls = set()
        
        # 策略1: 尝试找到主要内容区域
        content_selectors = [
            'main', 'article', '.content', '.post-content', '.article-content', 
            '.entry-content', '#content', '[role="main"]'
        ]
        
        for selector in content_selectors:
            try:
                content_areas = soup.select(selector)
                if content_areas:
                    for area in content_areas:
                        # 在内容区域中查找所有链接
                        for link in area.find_all('a', href=True):
                            url = link['href']
                            if url and not url.startswith('#') and not url.startswith('javascript:'):
                                absolute_url = urljoin(self.base_url, url)
                                urls.add(absolute_url)
                    # 如果找到了内容区域并提取了链接，可以停止
                    if urls:
                        break
            except Exception as e:
                logger.debug(f"在选择器 {selector} 中提取链接时出错: {e}")
        
        # 策略2: 如果没有找到特定内容区域，尝试查找所有链接
        if not urls:
            for link in soup.find_all('a', href=True):
                url = link['href']
                if url and not url.startswith('#') and not url.startswith('javascript:'):
                    absolute_url = urljoin(self.base_url, url)
                    urls.add(absolute_url)
        
        return urls
    
    def _extract_all_links(self, soup: BeautifulSoup) -> List[str]:
        """从页面提取所有链接"""
        urls = set()
        for link in soup.find_all('a', href=True):
            url = link['href']
            if url and not url.startswith('#') and not url.startswith('javascript:'):
                absolute_url = urljoin(self.base_url, url)
                urls.add(absolute_url)
        return list(urls)
    
    def _extract_content_legacy_format(self, soup: BeautifulSoup, schema: Dict) -> Dict[str, Any]:
        """使用传统格式schema提取内容"""
        result = {}
        
        # 如果schema是嵌套的，提取content部分
        content_schema = schema.get('content', schema)
        
        # 提取标题
        title_selector = content_schema.get('title', content_schema.get('title_selector', 'h1'))
        title_element = soup.select_one(title_selector)
        if title_element:
            result['title'] = title_element.get_text().strip()
        else:
            logger.warning(f"未找到标题元素: {title_selector}")
            # 尝试使用页面标题
            if soup.title:
                result['title'] = soup.title.get_text().strip()
            else:
                result['title'] = "未知标题"
        
        # 提取作者
        author_selector = content_schema.get('author', content_schema.get('author_selector'))
        if author_selector:
            author_element = soup.select_one(author_selector)
            if author_element:
                result['author'] = author_element.get_text().strip()
        
        # 提取日期
        date_selector = content_schema.get('date', content_schema.get('date_selector'))
        if date_selector:
            date_element = soup.select_one(date_selector)
            if date_element:
                # 优先从日期属性中获取
                date_attr = content_schema.get('date_attribute')
                if date_attr and date_element.has_attr(date_attr):
                    result['date'] = date_element[date_attr]
                else:
                    result['date'] = date_element.get_text().strip()
        
        # 提取主要内容
        content_selector = content_schema.get('content', content_schema.get('content_container_selector', 'article'))
        content_element = soup.select_one(content_selector)
        
        if not content_element:
            logger.warning(f"未找到主要内容元素: {content_selector}")
            # 尝试常见的内容容器选择器
            for selector in ['article', 'main', '.content', '.entry-content', '.post-content']:
                content_element = soup.select_one(selector)
                if content_element:
                    logger.info(f"使用备选选择器找到内容: {selector}")
                    break
        
        if content_element:
            # 提取原始HTML
            raw_html = str(content_element)
            result['html_content'] = raw_html
            
            # 移除不需要的元素
            if "remove" in content_schema:
                remove_selectors = content_schema.get("remove", [])
                for selector in remove_selectors:
                    for element in content_element.select(selector):
                        element.decompose()
            
            # 转换为Markdown
            markdown = markdownify.markdownify(str(content_element), heading_style="ATX")
            result['raw_content'] = markdown
            result['content_markdown'] = markdown
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
    
    def _extract_content_selectors_format(self, soup: BeautifulSoup, schema: Dict) -> Dict[str, Any]:
        """使用选择器格式schema提取内容"""
        result = {}
        selectors = schema.get('selectors', [])
        
        # 临时存储所有提取的内容片段
        all_content_fragments = []
        
        for selector_def in selectors:
            selector_type = selector_def.get('type')
            css_selector = selector_def.get('selector', {}).get('css')
            xpath_selector = selector_def.get('selector', {}).get('xpath')
            
            # 查找元素
            elements = []
            if css_selector:
                elements = soup.select(css_selector)
            elif xpath_selector:
                # 使用lxml处理XPath
                try:
                    import lxml.etree
                    dom = lxml.etree.HTML(str(soup))
                    xpath_results = dom.xpath(xpath_selector)
                    # 将xpath结果转换为BeautifulSoup元素
                    for result in xpath_results:
                        element_html = lxml.etree.tostring(result).decode('utf-8')
                        elements.append(BeautifulSoup(element_html, 'html.parser'))
                except ImportError:
                    logger.warning("lxml库未安装，无法使用XPath选择器")
                except Exception as e:
                    logger.error(f"XPath处理出错: {e}")
            
            # 处理找到的元素
            for element in elements:
                fields = selector_def.get('fields', {})
                
                # 处理每个字段定义
                for field_name, field_def in fields.items():
                    field_type = field_def.get('type')
                    field_selector = field_def.get('selector', '.')
                    field_attribute = field_def.get('attribute')
                    
                    # 找到目标元素
                    target = element
                    if field_selector != '.':
                        targets = element.select(field_selector)
                        if targets:
                            target = targets[0]
                    
                    # 根据字段类型提取内容
                    if field_type == 'attribute' and field_attribute:
                        if target.has_attr(field_attribute):
                            field_value = target[field_attribute]
                            result[field_name] = field_value
                            
                    elif field_type == 'text' or not field_type:
                        field_value = target.get_text().strip()
                        result[field_name] = field_value
                        
                        # 如果是内容相关的字段，保存为内容片段
                        if field_name == 'content':
                            all_content_fragments.append(str(target))
                
                # 检查是否有子元素定义
                children = selector_def.get('children', {})
                if children:
                    # 处理嵌套内容
                    for child_name, child_def in children.items():
                        if isinstance(child_def, dict):
                            child_type = child_def.get('type')
                            child_selector = child_def.get('selector')
                            
                            if child_type == 'elements' and child_selector:
                                # 查找所有匹配的子元素
                                child_elements = element.select(child_selector)
                                
                                # 如果是内容相关的子元素，保存为内容片段
                                if child_name in ['content', 'paragraphs', 'sections']:
                                    for child in child_elements:
                                        all_content_fragments.append(str(child))
        
        # 如果有多个内容片段，组合它们
        if all_content_fragments:
            combined_content = '\n'.join(all_content_fragments)
            # 转换为Markdown
            markdown_content = markdownify.markdownify(combined_content, heading_style="ATX")
            result['content_markdown'] = markdown_content
            result['html_content'] = combined_content
        
        # 确保有标题
        if 'title' not in result and soup.title:
            result['title'] = soup.title.get_text().strip()
        
        return result
    
    def _extract_content_generic(self, soup: BeautifulSoup, schema: Dict) -> Dict[str, Any]:
        """通用的内容提取方法，尝试识别页面中的主要内容"""
        result = {}
        
        # 提取标题
        title_candidates = [
            soup.find('h1'),
            soup.select_one('header h1'),
            soup.select_one('.entry-title'),
            soup.select_one('.post-title'),
            soup.select_one('article h1'),
            soup.select_one('.headline'),
            soup.title
        ]
        
        for candidate in title_candidates:
            if candidate:
                result['title'] = candidate.get_text().strip()
                break
        
        if 'title' not in result:
            result['title'] = "未知标题"
        
        # 尝试找到主要内容区域
        content_selectors = [
            'article', 'main article', '.post-content', '.article-content', 
            '.entry-content', '#content', 'main .content', 'div[itemprop="articleBody"]', 
            '.blog-post', '.blog-entry', 'main', 'section'
        ]
        
        content_element = None
        for selector in content_selectors:
            try:
                elements = soup.select(selector)
                if elements:
                    # 使用第一个元素作为内容
                    content_element = elements[0]
                    break
            except Exception as e:
                logger.debug(f"选择器 {selector} 提取内容时出错: {e}")
        
        if content_element:
            # 提取HTML内容
            html_content = str(content_element)
            result['html_content'] = html_content
            
            # 转换为Markdown
            markdown_content = markdownify.markdownify(html_content, heading_style="ATX")
            result['raw_content'] = markdown_content
            result['content_markdown'] = markdown_content
        else:
            logger.warning("未找到主要内容元素，使用body内容")
            # 如果找不到特定内容区域，使用body内容
            body = soup.find('body')
            if body:
                html_content = str(body)
                result['html_content'] = html_content
                result['content_markdown'] = markdownify.markdownify(html_content, heading_style="ATX")
        
        # 尝试提取元数据
        try:
            # 找到发布日期
            date_candidates = [
                soup.select_one('time'),
                soup.select_one('[itemprop="datePublished"]'),
                soup.select_one('.published'),
                soup.select_one('.post-date'),
                soup.select_one('meta[property="article:published_time"]')
            ]
            
            for candidate in date_candidates:
                if candidate:
                    if candidate.name == 'meta':
                        result['date'] = candidate.get('content', '')
                    elif candidate.has_attr('datetime'):
                        result['date'] = candidate['datetime']
                    else:
                        result['date'] = candidate.get_text().strip()
                    break
            
            # 找到作者
            author_candidates = [
                soup.select_one('[itemprop="author"]'),
                soup.select_one('.author'),
                soup.select_one('.byline'),
                soup.select_one('[rel="author"]'),
                soup.select_one('meta[name="author"]')
            ]
            
            for candidate in author_candidates:
                if candidate:
                    if candidate.name == 'meta':
                        result['author'] = candidate.get('content', '')
                    else:
                        result['author'] = candidate.get_text().strip()
                    break
        except Exception as e:
            logger.debug(f"提取元数据时出错: {e}")
        
        return result 