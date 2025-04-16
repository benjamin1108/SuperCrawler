import logging
from typing import Dict, List, Any, Optional, Union
from bs4 import BeautifulSoup
from playwright.async_api import Page, ElementHandle, Locator
import re

logger = logging.getLogger(__name__)

class XPathProcessor:
    """
    增强对XPath选择器的处理能力
    支持从XPath选择的大范围元素中提取特定字段
    """
    
    @staticmethod
    async def extract_elements_by_xpath(page: Page, xpath_selector: str, nested_selectors: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
        """
        使用XPath提取页面元素
        
        参数:
            page: Playwright页面对象
            xpath_selector: XPath选择器字符串(可以包含"xpath="前缀)
            nested_selectors: 嵌套选择器字典，用于提取子元素
            
        返回:
            提取的元素列表
        """
        try:
            clean_xpath = xpath_selector
            if xpath_selector.startswith("xpath="):
                clean_xpath = xpath_selector[6:]
            
            logger.info(f"使用XPath提取元素: {clean_xpath}")
            
            # 使用Playwright的locator API
            locator = page.locator(f"xpath={clean_xpath}")
            elements = await locator.all()
            
            logger.info(f"找到 {len(elements)} 个匹配的元素")
            
            results = []
            for element in elements:
                item = {}
                
                # 提取href属性(如果元素是链接)
                href = await element.get_attribute('href')
                if href:
                    item['href'] = href
                
                # 提取文本内容
                text = await element.text_content()
                if text:
                    item['text'] = text.strip()
                
                # 处理嵌套选择器
                if nested_selectors:
                    for field, selector in nested_selectors.items():
                        try:
                            # 处理特殊的child:n选择器
                            if selector.startswith('child:'):
                                try:
                                    index = int(selector.split(':')[1])
                                    # 使用evaluate在浏览器中执行JS以获取第n个子元素
                                    child_element = await element.evaluate(f"node => node.childNodes[{index}]")
                                    if child_element:
                                        item[field] = child_element.textContent.strip()
                                except (IndexError, ValueError) as e:
                                    logger.debug(f"处理child选择器时出错: {e}")
                            # 处理常规选择器
                            else:
                                child_element = await element.query_selector(selector)
                                if child_element:
                                    if field == 'url' or field == 'href':
                                        value = await child_element.get_attribute('href')
                                    else:
                                        value = await child_element.text_content()
                                    
                                    if value:
                                        item[field] = value.strip()
                        except Exception as e:
                            logger.debug(f"处理嵌套选择器 '{field}: {selector}' 时出错: {e}")
                
                # 如果没有提取到有效数据，尝试使用特殊的列表项处理
                if not item or all(not v for v in item.values()):
                    processed_item = await XPathProcessor.process_list_item(element)
                    if processed_item:
                        item.update(processed_item)
                
                if item:
                    results.append(item)
            
            return results
            
        except Exception as e:
            logger.error(f"使用XPath提取元素时出错: {str(e)}", exc_info=True)
            return []
    
    @staticmethod
    async def _auto_extract_fields(element: ElementHandle, html_content: str) -> Dict[str, Any]:
        """自动提取元素内的常见字段"""
        result = {}
        
        # 解析HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 提取URL (如果元素是链接或包含链接)
        links = soup.find_all('a')
        if links:
            for link in links:
                href = link.get('href')
                if href and not href.startswith('#') and not href.startswith('javascript:'):
                    result['href'] = href
                    # 提取链接文本作为标题
                    text = link.get_text().strip()
                    if text:
                        result['text'] = text
                    break
        
        # 如果元素本身是链接
        if not result.get('href'):
            try:
                href = await element.get_attribute('href')
                if href:
                    result['href'] = href
                    text = await element.text_content()
                    if text:
                        result['text'] = text.strip()
            except:
                pass
        
        # 提取标题
        for heading in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            headings = soup.find_all(heading)
            if headings:
                result['title'] = headings[0].get_text().strip()
                break
        
        # 如果没有找到标题，尝试从内部结构推断
        if not result.get('title') and not result.get('text'):
            # 查找最有可能的标题元素 (通常是第一个有意义的文本块)
            for tag in ['div', 'span', 'p']:
                elements = soup.find_all(tag)
                for el in elements:
                    text = el.get_text().strip()
                    if len(text) > 10 and len(text) < 200:  # 合理的标题长度
                        result['title'] = text
                        break
                if result.get('title'):
                    break
        
        # 提取日期
        date_elements = soup.find_all(['time', 'span', 'div'], class_=lambda c: c and any(date_term in c.lower() for date_term in ['date', 'time', 'published', 'modified']))
        if date_elements:
            result['date'] = date_elements[0].get_text().strip()
        else:
            # 查找包含日期格式的文本
            date_pattern = r'\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4}|\d{1,2}[-/]\w{3,9}[-/]\d{4}'
            for tag in soup.find_all(['div', 'span', 'p']):
                text = tag.get_text()
                match = re.search(date_pattern, text)
                if match:
                    result['date'] = match.group(0)
                    break
        
        # 如果没有足够的信息，直接获取元素文本
        if len(result) <= 1:  # 只有element_index或空
            try:
                text = await element.text_content()
                if text:
                    result['text'] = text.strip()
            except:
                pass
        
        return result
    
    @staticmethod
    async def _extract_field(element: ElementHandle, selector: str, field_name: str) -> Any:
        """从元素中提取特定字段"""
        try:
            # 处理不同类型的选择器
            if selector.startswith('css:'):
                # CSS选择器
                css_selector = selector[4:]
                inner_element = await element.query_selector(css_selector)
                if inner_element:
                    if field_name in ['href', 'src']:
                        # 对于链接和图片URL，获取属性值
                        return await inner_element.get_attribute(field_name)
                    else:
                        # 对于其他字段，获取文本内容
                        return (await inner_element.text_content()).strip()
            
            elif selector.startswith('xpath:'):
                # 相对XPath选择器
                xpath = selector[6:]
                # 注意: Playwright在元素内执行XPath查询时有一些限制
                # 这里简化处理，使用evaluate来执行XPath
                result = await element.evaluate(f"""(element) => {{
                    const node = document.evaluate('{xpath}', element, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                    if (!node) return null;
                    if ('{field_name}' === 'href' || '{field_name}' === 'src') return node.getAttribute('{field_name}');
                    return node.textContent.trim();
                }}""")
                return result
            
            elif selector.startswith('attr:'):
                # 直接获取属性
                attr_name = selector[5:]
                return await element.get_attribute(attr_name)
            
            elif selector.startswith('regex:'):
                # 使用正则表达式提取
                pattern = selector[6:]
                text = await element.text_content()
                match = re.search(pattern, text)
                return match.group(0) if match else None
            
            elif selector == 'text':
                # 直接获取文本内容
                return (await element.text_content()).strip()
            
            elif selector == 'html':
                # 获取HTML内容
                return await element.evaluate("el => el.outerHTML")
            
            elif selector.startswith('child:'):
                # 获取特定子元素，格式: child:index
                index = int(selector[6:])
                children = await element.query_selector_all(':scope > *')
                if index < len(children):
                    return (await children[index].text_content()).strip()
            
            elif selector.startswith('js:'):
                # 使用JavaScript表达式提取
                js_expr = selector[3:]
                return await element.evaluate(f"el => {js_expr}")
            
            else:
                # 默认当作简单选择器处理
                inner_element = await element.query_selector(selector)
                if inner_element:
                    return (await inner_element.text_content()).strip()
        
        except Exception as e:
            logger.warning(f"提取字段 '{field_name}' 使用选择器 '{selector}' 时出错: {str(e)}")
        
        return None
    
    @staticmethod
    async def process_list_item(element: Union[ElementHandle, Locator]) -> Dict[str, Any]:
        """
        处理列表项元素，提取标题、链接和日期
        
        参数:
            element: 列表项元素句柄或Locator对象
            
        返回:
            包含提取数据的字典
        """
        try:
            item_data = {}
            
            # 检查元素类型并相应处理
            is_locator = isinstance(element, Locator)
            
            # 获取href和文本内容（基本属性）
            if is_locator:
                try:
                    href = await element.get_attribute('href')
                    text_content = await element.text_content()
                    
                    if href:
                        item_data['href'] = href
                    if text_content:
                        item_data['text'] = text_content.strip()
                        
                    # 对于Locator对象，使用locator方法查找子元素
                    link_locator = element.locator('a')
                    link_count = await link_locator.count()
                    if link_count > 0:
                        link = link_locator.first
                        href = await link.get_attribute('href')
                        if href:
                            item_data['href'] = href
                        
                        title_text = await link.text_content()
                        if title_text:
                            item_data['title'] = title_text.strip()
                        
                        # 尝试提取日期 - 常见选择器
                        date_selectors = [
                            '.lb-txt-bold', '.date', 'span.date', 'time', 
                            '[datetime]', '.lb-txt-none'
                        ]
                        for selector in date_selectors:
                            date_locator = element.locator(selector)
                            date_count = await date_locator.count()
                            if date_count > 0:
                                date_text = await date_locator.first.text_content()
                                if date_text:
                                    item_data['date'] = date_text.strip()
                                    break
                        
                        # 如果没找到标题，尝试其他选择器
                        if 'title' not in item_data or not item_data['title']:
                            title_selectors = ['h2', 'h3', '.lb-title', '.title']
                            for selector in title_selectors:
                                title_locator = element.locator(selector)
                                count = await title_locator.count()
                                if count > 0:
                                    title_text = await title_locator.first.text_content()
                                    if title_text:
                                        item_data['title'] = title_text.strip()
                                        break
                except Exception as e:
                    logger.debug(f"处理Locator对象时出错: {str(e)}")
            else:
                # 对于ElementHandle对象
                try:
                    href = await element.get_attribute('href')
                    text_content = await element.text_content()
                    
                    if href:
                        item_data['href'] = href
                    if text_content:
                        item_data['text'] = text_content.strip()
                    
                    # 使用query_selector方法
                    link = await element.query_selector('a')
                    if link:
                        # 提取 href
                        href = await link.get_attribute('href')
                        if href:
                            item_data['href'] = href
                        
                        # 提取链接文本作为标题
                        title_text = await link.text_content()
                        if title_text:
                            item_data['title'] = title_text.strip()
                        
                        # 尝试提取日期
                        date_element = await element.query_selector('.lb-txt-bold')
                        if date_element:
                            date_text = await date_element.text_content()
                            if date_text:
                                item_data['date'] = date_text.strip()
                        
                        # 如果没有找到日期，尝试其他日期选择器
                        if 'date' not in item_data:
                            date_selectors = [
                                'span.date', '.date', 'time', 
                                '[datetime]', '.lb-txt-bold', '.lb-txt-none'
                            ]
                            for date_selector in date_selectors:
                                date_element = await element.query_selector(date_selector)
                                if date_element:
                                    date_text = await date_element.text_content()
                                    if date_text:
                                        item_data['date'] = date_text.strip()
                                        break
                        
                        # 如果没有找到标题，尝试其他标题选择器
                        if 'title' not in item_data or not item_data['title']:
                            title_selectors = ['h2', 'h3', '.lb-title', '.title']
                            for title_selector in title_selectors:
                                title_element = await element.query_selector(title_selector)
                                if title_element:
                                    title_text = await title_element.text_content()
                                    if title_text:
                                        item_data['title'] = title_text.strip()
                                        break
                except Exception as e:
                    logger.debug(f"处理ElementHandle对象时出错: {str(e)}")
            
            logger.debug(f"处理列表项结果: {item_data}")
            return item_data
            
        except Exception as e:
            logger.error(f"处理列表项时出错: {str(e)}")
            return {}


# 使用示例
if __name__ == "__main__":
    from playwright.sync_api import sync_playwright
    import asyncio
    
    async def test_xpath_processor():
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()
            
            # 访问AWS新闻页面
            url = "https://aws.amazon.com/cn/about-aws/whats-new/networking_and_content_delivery/?whats-new-content.sort-by=item.additionalFields.postDateTime&whats-new-content.sort-order=desc&awsf.whats-new-products=*all"
            await page.goto(url)
            await page.wait_for_load_state('networkidle')
            
            # 测试提取元素
            xpath = "xpath=/html/body/div[2]/main/div[3]/div[2]/div[2]/div[4]/section/ul/li"
            nested_selectors = {
                "title": "css:div.m-card-title a",
                "date": "css:div.m-card-info",
                "url": "attr:href"
            }
            
            results = await XPathProcessor.extract_elements_by_xpath(page, xpath, nested_selectors)
            
            print(f"找到 {len(results)} 个结果:")
            for i, item in enumerate(results[:3]):  # 只打印前3个
                print(f"\n项目 {i+1}:")
                for key, value in item.items():
                    print(f"  {key}: {value}")
            
            await browser.close()
    
    asyncio.run(test_xpath_processor()) 