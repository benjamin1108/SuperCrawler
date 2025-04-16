import logging
from typing import Dict, List, Any, Optional, Union
from bs4 import BeautifulSoup
import re
from datetime import datetime

logger = logging.getLogger(__name__)

class FieldExtractor:
    """
    从大范围元素中提取特定字段
    支持提取链接、标题、日期等常见信息
    """
    
    def __init__(self):
        # 初始化可能的字段提取器
        self.extractors = {
            "url": self._extract_url,
            "title": self._extract_title,
            "date": self._extract_date,
            "content": self._extract_content,
            "summary": self._extract_summary,
            "image": self._extract_image,
            "author": self._extract_author,
            "category": self._extract_category,
            "tag": self._extract_tags
        }
    
    def extract_fields(self, html_content: str, field_mapping: Dict[str, str] = None) -> Dict[str, Any]:
        """
        从HTML内容中提取指定字段
        
        参数:
            html_content: HTML内容字符串
            field_mapping: 字段映射配置，格式为 {"字段名": "选择器或规则"}
                          如果为None，则尝试自动提取所有支持的字段
        
        返回:
            包含提取字段的字典
        """
        if not html_content:
            logger.warning("提供的HTML内容为空")
            return {}
        
        # 解析HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 如果没有提供字段映射，使用默认的自动提取
        if not field_mapping:
            return self._auto_extract_fields(soup)
        
        # 提取指定字段
        result = {}
        for field_name, extraction_rule in field_mapping.items():
            try:
                if field_name in self.extractors:
                    # 使用预定义的提取器
                    value = self.extractors[field_name](soup, extraction_rule)
                else:
                    # 使用通用选择器提取
                    value = self._extract_by_selector(soup, extraction_rule)
                
                if value:
                    result[field_name] = value
            except Exception as e:
                logger.warning(f"提取字段 '{field_name}' 时出错: {str(e)}")
        
        return result
    
    def _auto_extract_fields(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """自动提取所有可能的字段"""
        result = {}
        
        # 尝试提取链接
        links = soup.find_all('a')
        if links:
            for link in links:
                href = link.get('href')
                if href and not href.startswith('#') and not href.startswith('javascript:'):
                    result['url'] = href
                    result['title'] = link.get_text().strip()
                    break
        
        # 尝试提取标题
        for heading in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            headings = soup.find_all(heading)
            if headings:
                result['title'] = headings[0].get_text().strip()
                break
        
        # 尝试提取日期
        date_elements = soup.find_all(['time', 'span', 'div'], class_=lambda c: c and any(date_term in c.lower() for date_term in ['date', 'time', 'published', 'modified']))
        if date_elements:
            result['date'] = date_elements[0].get_text().strip()
        else:
            # 查找包含日期格式的文本
            text_with_date = soup.find(string=re.compile(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4}|\d{1,2}[-/]\w{3,9}[-/]\d{4}'))
            if text_with_date:
                result['date'] = text_with_date.strip()
        
        # 尝试提取内容
        content_elements = soup.find_all(['div', 'article', 'section'], class_=lambda c: c and any(content_term in c.lower() for content_term in ['content', 'body', 'text', 'article']))
        if content_elements:
            result['content'] = content_elements[0].get_text().strip()
        
        return result
    
    def _extract_by_selector(self, soup: BeautifulSoup, selector: str) -> Any:
        """通过选择器提取内容"""
        if not selector:
            return None
        
        # 根据选择器类型处理
        if selector.startswith('css:'):
            # CSS选择器
            css_selector = selector[4:]
            elements = soup.select(css_selector)
            return elements[0].get_text().strip() if elements else None
        
        elif selector.startswith('xpath:'):
            # XPath在BeautifulSoup中不直接支持，可以使用lxml
            # 这里简化处理，仅使用BeautifulSoup的选择器功能
            logger.warning("XPath选择器在当前版本不直接支持，尝试转换为CSS选择器")
            xpath = selector[6:]
            # 简单转换几种常见的XPath模式
            if xpath.startswith('//'):
                tag = xpath[2:].split('[')[0].split('/')[0]
                elements = soup.find_all(tag)
                return elements[0].get_text().strip() if elements else None
            else:
                return None
        
        elif selector.startswith('regex:'):
            # 正则表达式
            pattern = selector[6:]
            text = soup.get_text()
            match = re.search(pattern, text)
            return match.group(0) if match else None
        
        else:
            # 默认当作标签名处理
            elements = soup.find_all(selector)
            return elements[0].get_text().strip() if elements else None
    
    def _extract_url(self, soup: BeautifulSoup, rule: str = None) -> str:
        """提取URL"""
        if rule:
            # 使用指定规则
            links = soup.select(rule) if rule.startswith('css:') else soup.find_all('a', href=True)
            return links[0]['href'] if links else None
        else:
            # 自动查找
            links = soup.find_all('a', href=True)
            for link in links:
                href = link.get('href')
                if href and not href.startswith('#') and not href.startswith('javascript:'):
                    return href
        return None
    
    def _extract_title(self, soup: BeautifulSoup, rule: str = None) -> str:
        """提取标题"""
        if rule:
            # 使用指定规则
            elements = soup.select(rule) if rule.startswith('css:') else soup.find_all(rule)
            return elements[0].get_text().strip() if elements else None
        else:
            # 尝试从标题标签中提取
            for heading in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                headings = soup.find_all(heading)
                if headings:
                    return headings[0].get_text().strip()
            
            # 尝试从链接文本中提取
            links = soup.find_all('a')
            if links:
                for link in links:
                    text = link.get_text().strip()
                    if text and len(text) > 10:  # 假设标题一般较长
                        return text
        
        return None
    
    def _extract_date(self, soup: BeautifulSoup, rule: str = None) -> str:
        """提取日期"""
        if rule:
            # 使用指定规则
            elements = soup.select(rule) if rule.startswith('css:') else soup.find_all(rule)
            if elements:
                date_text = elements[0].get_text().strip()
                # 尝试解析和格式化日期
                return self._clean_date(date_text)
            return None
        
        # 查找包含日期的常见元素
        date_elements = soup.find_all(['time', 'span', 'div'], class_=lambda c: c and any(date_term in c.lower() for date_term in ['date', 'time', 'published', 'modified']))
        if date_elements:
            return self._clean_date(date_elements[0].get_text().strip())
        
        # 查找包含日期格式的文本
        date_pattern = r'\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4}|\d{1,2}[-/]\w{3,9}[-/]\d{4}'
        text_with_date = soup.find(string=re.compile(date_pattern))
        if text_with_date:
            # 提取日期部分
            match = re.search(date_pattern, text_with_date)
            if match:
                return self._clean_date(match.group(0))
        
        return None
    
    def _clean_date(self, date_text: str) -> str:
        """清理并标准化日期格式"""
        if not date_text:
            return None
        
        # 去除多余空白和标点
        date_text = re.sub(r'\s+', ' ', date_text).strip()
        
        # 尝试解析常见日期格式
        date_formats = [
            '%Y-%m-%d', '%Y/%m/%d', '%d-%m-%Y', '%d/%m/%Y',
            '%B %d, %Y', '%b %d, %Y', '%d %B %Y', '%d %b %Y',
            '%Y年%m月%d日', '%m月%d日,%Y'
        ]
        
        for date_format in date_formats:
            try:
                dt = datetime.strptime(date_text, date_format)
                return dt.strftime('%Y-%m-%d')  # 返回标准化格式
            except ValueError:
                continue
        
        # 如果无法解析，返回原始文本
        return date_text
    
    def _extract_content(self, soup: BeautifulSoup, rule: str = None) -> str:
        """提取内容"""
        if rule:
            # 使用指定规则
            elements = soup.select(rule) if rule.startswith('css:') else soup.find_all(rule)
            return elements[0].get_text().strip() if elements else None
        
        # 尝试从常见内容容器中提取
        content_elements = soup.find_all(['div', 'article', 'section'], class_=lambda c: c and any(content_term in c.lower() for content_term in ['content', 'body', 'text', 'article']))
        if content_elements:
            return content_elements[0].get_text().strip()
        
        # 回退到主体内容
        body = soup.find('body')
        if body:
            # 排除页眉、页脚、导航等元素
            for tag in body.find_all(['header', 'footer', 'nav']):
                tag.extract()
            return body.get_text().strip()
        
        return None
    
    def _extract_summary(self, soup: BeautifulSoup, rule: str = None) -> str:
        """提取摘要"""
        if rule:
            # 使用指定规则
            elements = soup.select(rule) if rule.startswith('css:') else soup.find_all(rule)
            return elements[0].get_text().strip() if elements else None
        
        # 查找meta标签中的描述
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            return meta_desc.get('content').strip()
        
        # 查找常见摘要元素
        summary_elements = soup.find_all(['div', 'p'], class_=lambda c: c and any(summary_term in c.lower() for summary_term in ['summary', 'excerpt', 'description', 'intro']))
        if summary_elements:
            return summary_elements[0].get_text().strip()
        
        # 提取第一段
        first_p = soup.find('p')
        if first_p:
            text = first_p.get_text().strip()
            if len(text) > 10:  # 有实质内容
                return text
        
        return None
    
    def _extract_image(self, soup: BeautifulSoup, rule: str = None) -> str:
        """提取图像URL"""
        if rule:
            # 使用指定规则
            elements = soup.select(rule) if rule.startswith('css:') else soup.find_all(rule)
            if elements and elements[0].name == 'img':
                return elements[0].get('src')
            elif elements:
                # 如果选择器匹配到的不是img标签，查找其中的img
                img = elements[0].find('img')
                return img.get('src') if img else None
            return None
        
        # 查找所有图像
        images = soup.find_all('img')
        if images:
            # 优先选择较大图片（通常是主要内容）
            for img in images:
                if img.get('width') and img.get('height'):
                    try:
                        width = int(img['width'])
                        height = int(img['height'])
                        if width > 100 and height > 100:  # 较大图片
                            return img.get('src')
                    except ValueError:
                        pass
            
            # 如果没有找到较大图片，返回第一个
            return images[0].get('src')
        
        return None
    
    def _extract_author(self, soup: BeautifulSoup, rule: str = None) -> str:
        """提取作者"""
        if rule:
            # 使用指定规则
            elements = soup.select(rule) if rule.startswith('css:') else soup.find_all(rule)
            return elements[0].get_text().strip() if elements else None
        
        # 查找常见作者元素
        author_elements = soup.find_all(['span', 'div', 'a'], class_=lambda c: c and any(author_term in c.lower() for author_term in ['author', 'byline', 'writer']))
        if author_elements:
            return author_elements[0].get_text().strip()
        
        # 查找meta标签
        meta_author = soup.find('meta', attrs={'name': 'author'})
        if meta_author and meta_author.get('content'):
            return meta_author.get('content').strip()
        
        return None
    
    def _extract_category(self, soup: BeautifulSoup, rule: str = None) -> str:
        """提取分类"""
        if rule:
            # 使用指定规则
            elements = soup.select(rule) if rule.startswith('css:') else soup.find_all(rule)
            return elements[0].get_text().strip() if elements else None
        
        # 查找常见分类元素
        category_elements = soup.find_all(['span', 'div', 'a'], class_=lambda c: c and any(cat_term in c.lower() for cat_term in ['category', 'cat', 'topic']))
        if category_elements:
            return category_elements[0].get_text().strip()
        
        return None
    
    def _extract_tags(self, soup: BeautifulSoup, rule: str = None) -> List[str]:
        """提取标签"""
        if rule:
            # 使用指定规则
            elements = soup.select(rule) if rule.startswith('css:') else soup.find_all(rule)
            return [el.get_text().strip() for el in elements]
        
        # 查找常见标签元素
        tag_elements = soup.find_all(['a', 'span'], class_=lambda c: c and any(tag_term in c.lower() for tag_term in ['tag', 'keyword', 'label']))
        if tag_elements:
            return [el.get_text().strip() for el in tag_elements]
        
        return []


# 使用示例
if __name__ == "__main__":
    # 测试HTML内容
    test_html = """
    <div class="article">
        <h1>这是一个测试标题</h1>
        <div class="meta">
            <span class="date">2025-04-16</span>
            <span class="author">作者名</span>
        </div>
        <div class="content">
            <p>这是文章内容的第一段。</p>
            <p>这是文章内容的第二段。</p>
        </div>
        <div class="tags">
            <a href="/tag/1">标签1</a>
            <a href="/tag/2">标签2</a>
        </div>
    </div>
    """
    
    extractor = FieldExtractor()
    
    # 自动提取所有字段
    results = extractor.extract_fields(test_html)
    print("自动提取结果:")
    for field, value in results.items():
        print(f"{field}: {value}")
    
    # 使用规则提取
    field_mapping = {
        "title": "css:h1",
        "date": "css:.date",
        "author": "css:.author",
        "content": "css:.content",
        "tags": "css:.tags a"
    }
    
    custom_results = extractor.extract_fields(test_html, field_mapping)
    print("\n自定义规则提取结果:")
    for field, value in custom_results.items():
        print(f"{field}: {value}") 