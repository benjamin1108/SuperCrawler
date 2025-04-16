import logging
from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from playwright.async_api import Page, ElementHandle

from src.extractors.xpath_processor import XPathProcessor

logger = logging.getLogger(__name__)

class WorkflowLinksExtractor:
    """工作流链接提取器，用于从页面中提取链接"""
    
    @staticmethod
    async def extract_links(page: Page, selector: str, should_generalize: bool = False) -> List[Dict[str, str]]:
        """
        从页面中提取链接
        
        参数:
            page: Playwright页面对象
            selector: 选择器(CSS或XPath)
            should_generalize: 是否需要泛化
            
        返回:
            链接项列表，每项包含 href 和 text
        """
        try:
            base_url = page.url
            items = []
            
            logger.info(f"使用选择器提取链接: {selector}")
            
            # 处理XPath选择器
            if selector.startswith("xpath="):
                clean_xpath = selector[6:]
                logger.info(f"处理XPath选择器: {clean_xpath}")
                
                # 对于AWS新闻页面，我们知道其结构，可以直接定位到列表项
                if "aws.amazon.com" in base_url and "whats-new" in base_url:
                    logger.info("检测到AWS新闻页面，使用专用处理逻辑")
                    
                    # 1. 先尝试定位列表项元素
                    locator = page.locator(f"xpath={clean_xpath}")
                    element_handles = await locator.all()
                    logger.info(f"找到 {len(element_handles)} 个列表项元素")
                    
                    # 2. 处理每个列表项
                    for element in element_handles:
                        # 使用专门的AWS列表项处理器
                        item = await XPathProcessor.process_list_item(element)
                        if item and 'href' in item:
                            # 构建完整URL
                            href = item.get('href', '')
                            if href:
                                full_url = urljoin(base_url, href)
                                items.append({
                                    'href': full_url,
                                    'text': item.get('title', '') or item.get('text', ''),
                                    'date': item.get('date', '')
                                })
                
                # 如果上面的专用处理没有找到链接，或者不是AWS页面，使用通用XPath处理
                if not items:
                    logger.info("使用通用XPath处理...")
                    # 使用增强的XPath处理器提取元素和字段
                    nested_selectors = {
                        "title": "child:0",  # 尝试从第一个子元素获取标题
                        "date": "child:1",   # 尝试从第二个子元素获取日期
                        "url": "a"           # 尝试获取链接
                    }
                    
                    elements = await XPathProcessor.extract_elements_by_xpath(page, f"xpath={clean_xpath}", nested_selectors)
                    
                    # 处理提取的结果
                    for item in elements:
                        href = item.get('href', '')
                        if not href and 'url' in item:
                            href = item.get('url', '')
                        
                        if href:
                            full_url = urljoin(base_url, href)
                            items.append({
                                'href': full_url,
                                'text': item.get('title', '') or item.get('text', ''),
                                'date': item.get('date', '')
                            })
            
            # 处理CSS选择器
            else:
                # 使用原始的CSS选择器处理
                css_selector = selector
                logger.info(f"处理CSS选择器: {css_selector}")
                elements = await page.query_selector_all(css_selector)
                
                for element in elements:
                    # 获取href属性
                    href = await element.get_attribute('href')
                    text = await element.text_content()
                    
                    if href:
                        # 构建完整URL
                        full_url = urljoin(base_url, href)
                        items.append({
                            'href': full_url,
                            'text': text.strip() if text else ''
                        })
            
            # 如果还没有找到链接，尝试全页面搜索
            if not items and should_generalize:
                logger.info("未找到链接，尝试全页面搜索...")
                html_content = await page.content()
                additional_items = await WorkflowLinksExtractor.extract_links_from_html(html_content, base_url)
                items.extend(additional_items)
            
            logger.info(f"提取到 {len(items)} 个链接")
            return items
            
        except Exception as e:
            logger.error(f"提取链接时出错: {str(e)}", exc_info=True)
            return []
    
    @staticmethod
    def _is_valid_link(href: str) -> bool:
        """检查是否是有效的链接"""
        if not href:
            return False
        
        # 排除常见的无效链接
        invalid_prefixes = ['javascript:', '#', 'mailto:', 'tel:']
        for prefix in invalid_prefixes:
            if href.startswith(prefix):
                return False
        
        return True
    
    @staticmethod
    async def extract_links_from_html(html_content: str, base_url: str) -> List[Dict[str, str]]:
        """从HTML内容中提取链接"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            items = []
            
            links = soup.find_all('a', href=True)
            for link in links:
                href = link.get('href')
                
                if WorkflowLinksExtractor._is_valid_link(href):
                    # 构建完整URL
                    full_url = urljoin(base_url, href)
                    items.append({
                        'href': full_url,
                        'text': link.get_text().strip()
                    })
            
            return items
            
        except Exception as e:
            logger.error(f"从HTML内容提取链接时出错: {str(e)}")
            return [] 