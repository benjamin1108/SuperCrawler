# main.py
import asyncio
import json
import os
import time
import argparse
import sys
from pathlib import Path
from urllib.parse import urljoin, urlparse

import yaml
from bs4 import BeautifulSoup
from markdownify import markdownify as md
from playwright.async_api import async_playwright

# --- 配置加载 ---
def load_config(config_path="config.yaml"):
    """加载 YAML 配置文件"""
    print(f"正在加载配置文件: {config_path}")
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            print("配置文件加载成功。")
            
            # 处理Schema路径
            config_dir = Path(config_path).parent
            
            # 检查是否存在内联Schema
            if 'start_page_schema_inline' in config:
                print("使用内联起始页Schema")
                config['start_page_schema'] = config['start_page_schema_inline']
            elif 'start_page_schema' in config:
                # 将外部schema文件路径转换为绝对路径
                config['start_page_schema'] = config_dir / config['start_page_schema']
            
            if 'secondary_page_schema_inline' in config:
                print("使用内联二级页Schema")
                config['secondary_page_schema'] = config['secondary_page_schema_inline']
            elif 'secondary_page_schema' in config:
                # 将外部schema文件路径转换为绝对路径
                config['secondary_page_schema'] = config_dir / config['secondary_page_schema']
            
            config['output_directory'] = Path(config['output_directory']) # 使用 Path 对象
            return config
    except FileNotFoundError:
        print(f"错误：配置文件 {config_path} 未找到。")
        return None
    except Exception as e:
        print(f"错误：加载配置文件 {config_path} 时出错: {e}")
        return None

def load_schema(schema_path_or_data):
    """加载Schema（支持文件路径或直接传入数据）"""
    # 检查是否已经是字典数据
    if isinstance(schema_path_or_data, dict):
        print("使用内联Schema数据")
        return schema_path_or_data
    
    # 否则作为文件路径处理
    print(f"正在加载 Schema 文件: {schema_path_or_data}")
    try:
        with open(schema_path_or_data, 'r', encoding='utf-8') as f:
            schema = json.load(f)
            print(f"Schema 文件 '{Path(schema_path_or_data).name}' 加载成功。")
            return schema
    except FileNotFoundError:
        print(f"错误：Schema 文件 {schema_path_or_data} 未找到。")
        return None
    except json.JSONDecodeError:
        print(f"错误：Schema 文件 {schema_path_or_data} 格式无效。")
        return None
    except Exception as e:
        print(f"错误：加载 Schema 文件 {schema_path_or_data} 时出错: {e}")
        return None

def parse_custom_schema(schema):
    """
    解析用户自定义 Schema 格式
    
    schema 格式示例：
    {
      "url": "https://example.com/blog",
      "timestamp": "2025-04-15T14:17:07.618Z",
      "elements": [
        {
          "tagName": "div",
          "xpath": "/path/to/element",
          "cssSelector": "div.some-class",
          "textContent": "Some text",
          "attributes": [
            {
              "name": "class",
              "value": "some-class"
            }
          ]
        }
      ]
    }
    """
    if not schema or not isinstance(schema, dict):
        print("错误：Schema 格式无效，必须是一个字典对象。")
        return None
    
    # 提取基本信息
    start_url = schema.get('url')
    elements = schema.get('elements', [])
    
    if not start_url:
        print("错误：Schema 中缺少 'url' 字段。")
        return None
    
    if not elements:
        print("警告：Schema 中没有 'elements' 字段或者为空列表。")
    
    # 构建简化的 Schema 对象
    simplified_schema = {
        'start_url': start_url,
        'selectors': []
    }
    
    # 提取选择器信息
    for element in elements:
        selector_info = {
            'css_selector': element.get('cssSelector'),
            'xpath': element.get('xpath'),
            'tag_name': element.get('tagName')
        }
        
        # 添加到选择器列表
        simplified_schema['selectors'].append(selector_info)
    
    return simplified_schema

async def extract_urls_from_page(page, custom_schema, base_url=None):
    """
    使用自定义 Schema 从页面提取 URL
    
    此函数使用 CSS 选择器或 XPath 来定位元素，然后从这些元素提取所有链接
    """
    print("使用自定义 Schema 提取 URL...")
    
    if not custom_schema or not isinstance(custom_schema, dict):
        print("错误：无效的自定义 Schema")
        return []
    
    # 使用传入的 base_url，如果未提供则使用 Schema 中的 URL
    if not base_url and 'start_url' in custom_schema:
        base_url = custom_schema['start_url']
    
    if not base_url:
        print("错误：未提供基础 URL")
        return []
    
    # 提取所有选择器
    selectors = custom_schema.get('selectors', [])
    if not selectors:
        print("错误：Schema 中没有有效的选择器信息")
        return []
    
    # 查找所有匹配元素
    urls = set()  # 使用集合去重
    
    for selector_info in selectors:
        # 尝试使用 CSS 选择器
        css_selector = selector_info.get('css_selector')
        xpath = selector_info.get('xpath')
        
        elements = []
        
        # 现在尝试使用更通用的选择器，而不是自定义Schema中的特定选择器
        try:
            # 尝试找到所有文章卡片或者博客列表项
            print("尝试查找常见的博客文章卡片元素...")
            article_selectors = [
                'article', '.article', '.post', '.blog-post', '.card', 
                '.msx-card', '.blog-card', '.news-item', '.entry',
                'div[class*="card"]', 'div[class*="article"]', 'div[class*="post"]'
            ]
            
            for selector in article_selectors:
                elements = await page.query_selector_all(selector)
                if elements and len(elements) > 0:
                    print(f"使用选择器 '{selector}' 找到 {len(elements)} 个元素")
                    break
            
            # 如果没有找到任何文章元素，则查找所有链接
            if not elements or len(elements) == 0:
                print("未找到文章元素，直接查找所有链接...")
                elements = await page.query_selector_all('a')
                print(f"找到 {len(elements)} 个链接元素")
                
                # 直接从链接元素中提取URL
                for link in elements:
                    href = await link.get_attribute('href')
                    if href:
                        absolute_url = urljoin(base_url, href)
                        # 过滤掉外部链接和非博客链接
                        if (urlparse(absolute_url).netloc == urlparse(base_url).netloc and
                            ('/blog/' in absolute_url or '/article/' in absolute_url or '/post/' in absolute_url)):
                            urls.add(absolute_url)
                            print(f"找到符合条件的链接: {absolute_url}")
            else:
                # 从文章元素中查找链接
                for article in elements:
                    links = await article.query_selector_all('a')
                    for link in links:
                        href = await link.get_attribute('href')
                        if href:
                            absolute_url = urljoin(base_url, href)
                            # 过滤掉外部链接
                            if urlparse(absolute_url).netloc == urlparse(base_url).netloc:
                                urls.add(absolute_url)
                                print(f"从文章元素中提取链接: {absolute_url}")
        except Exception as e:
            print(f"查找元素时出错: {e}")
    
    # 如果仍未找到任何链接，尝试更宽松的方法
    if not urls:
        print("未找到任何链接，尝试更宽松的方法...")
        try:
            # 直接使用JavaScript在页面中查找所有链接
            all_urls = await page.evaluate('''() => {
                const links = Array.from(document.querySelectorAll('a[href]'));
                return links.map(link => link.href);
            }''')
            
            base_domain = urlparse(base_url).netloc
            
            for url in all_urls:
                if url and isinstance(url, str):
                    # 过滤链接，只保留来自同一域名且可能是博客文章的链接
                    if (urlparse(url).netloc == base_domain and 
                        ('/blog/' in url or '/article/' in url or '/networking/' in url)):
                        urls.add(url)
                        print(f"使用JavaScript查找到链接: {url}")
        except Exception as e:
            print(f"使用JavaScript提取链接时出错: {e}")
    
    extracted_urls = list(urls)
    print(f"成功提取 {len(extracted_urls)} 个 URL")
    return extracted_urls

# --- 爬虫核心逻辑 ---
async def fetch_page_content(page, url, timeout):
    """使用 Playwright 加载页面并返回 HTML 内容"""
    print(f"正在访问页面: {url}")
    try:
        await page.goto(url, timeout=timeout)
        # 等待页面加载完成，可以根据需要添加更复杂的等待逻辑
        # await page.wait_for_load_state('networkidle')
        content = await page.content()
        print(f"页面加载成功: {url}")
        return content
    except Exception as e:
        print(f"错误：访问页面 {url} 时出错: {e}")
        return None

def extract_secondary_urls(html_content, schema, base_url):
    """根据起始页 Schema 提取二级 URL 列表"""
    print("正在提取二级 URL...")
    urls = set() # 使用集合去重
    if not html_content or not schema:
        return []

    soup = BeautifulSoup(html_content, 'html.parser')
    container_selector = schema.get('container_selector')
    link_selector = schema.get('link_selector')
    url_attribute = schema.get('url_attribute', 'href')

    if not link_selector:
        print("错误：起始页 Schema 中缺少 'link_selector'。")
        return []

    elements_to_search = soup
    if container_selector:
        elements_to_search = soup.select(container_selector)
        if not elements_to_search:
            print(f"警告：在起始页未找到容器元素 '{container_selector}'。将在整个页面搜索链接。")
            elements_to_search = soup # 如果找不到容器，则在整个文档中搜索

    links = []
    if isinstance(elements_to_search, list): # If container_selector found multiple containers
         for container in elements_to_search:
              links.extend(container.select(link_selector))
    else: # If searching the whole soup object or only one container found
        links = elements_to_search.select(link_selector)


    print(f"找到 {len(links)} 个可能的链接元素。")

    for link in links:
        url = link.get(url_attribute)
        if url:
            # 将相对 URL 转换为绝对 URL
            absolute_url = urljoin(base_url, url)
            # 基础的主机名检查，避免爬取外部链接 (可选，可根据需要调整)
            if urlparse(absolute_url).netloc == urlparse(base_url).netloc:
                urls.add(absolute_url)
            else:
                 print(f"忽略外部链接: {absolute_url}")

    extracted_urls = list(urls)
    print(f"成功提取 {len(extracted_urls)} 个二级 URL。")
    return extracted_urls


async def extract_element_by_schema(page, schema):
    """
    根据自定义schema从页面提取元素
    将结果保存到中间文件以便调试
    """
    print("\n===== 根据SCHEMA提取元素开始 =====")
    results = []
    
    if not schema or not isinstance(schema, dict):
        print("错误：Schema格式无效")
        return results
    
    elements = schema.get('elements', [])
    if not elements:
        print("错误：Schema中没有elements字段")
        return results
    
    for idx, element_def in enumerate(elements):
        print(f"处理第 {idx+1}/{len(elements)} 个元素定义")
        
        # 获取选择器信息
        css_selector = element_def.get('cssSelector')
        xpath = element_def.get('xpath')
        tag_name = element_def.get('tagName')
        
        print(f"  - CSS选择器: {css_selector}")
        print(f"  - XPath: {xpath}")
        print(f"  - 标签名: {tag_name}")
        
        # 尝试使用不同的选择器定位元素
        target_elements = []
        
        if css_selector:
            print(f"  尝试使用CSS选择器: {css_selector}")
            try:
                found_elements = await page.query_selector_all(css_selector)
                print(f"  CSS选择器找到 {len(found_elements)} 个元素")
                target_elements.extend(found_elements)
            except Exception as e:
                print(f"  CSS选择器查找出错: {e}")
        
        if xpath and not target_elements:
            print(f"  尝试使用XPath: {xpath}")
            try:
                found_elements = await page.query_selector_all(f"xpath={xpath}")
                print(f"  XPath找到 {len(found_elements)} 个元素")
                target_elements.extend(found_elements)
            except Exception as e:
                print(f"  XPath查找出错: {e}")
        
        if tag_name and not target_elements:
            print(f"  尝试使用标签名: {tag_name}")
            try:
                found_elements = await page.query_selector_all(tag_name)
                print(f"  标签名找到 {len(found_elements)} 个元素")
                target_elements.extend(found_elements)
            except Exception as e:
                print(f"  标签名查找出错: {e}")
        
        # 提取元素信息
        for i, el in enumerate(target_elements):
            try:
                html = await page.evaluate('(el) => el.outerHTML', el)
                text = await el.text_content()
                element_info = {
                    'index': i,
                    'html': html,
                    'text': text,
                    'selector': css_selector or xpath or tag_name
                }
                results.append(element_info)
                print(f"  提取到元素 #{i+1}, 文本长度: {len(text)}, HTML长度: {len(html)}")
            except Exception as e:
                print(f"  提取元素 #{i+1} 信息出错: {e}")
    
    # 将结果保存到中间文件
    try:
        debug_dir = Path("debug")
        debug_dir.mkdir(exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        debug_file = debug_dir / f"extracted_elements_{timestamp}.json"
        
        with open(debug_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        print(f"已保存中间调试文件: {debug_file}")
    except Exception as e:
        print(f"保存调试文件出错: {e}")
    
    print("===== 根据SCHEMA提取元素结束 =====\n")
    return results


def generate_filename(url, title=None, created_at=None):
    """生成唯一的文件名，确保文件名有效"""
    # 尝试从URL提取有意义的部分
    path_parts = urlparse(url).path.strip('/').split('/')
    filename_base = path_parts[-1] if path_parts else 'article'
    
    # 如果有标题，使用标题
    if title and not title == "未知标题":
        # 只取标题的前30个字符，避免文件名过长
        title_part = title[:30].strip()
        # 替换不适合文件名的字符
        title_part = re.sub(r'[\\/*?:"<>|]', '', title_part)
        filename_base = title_part
    
    # 清理文件名基础部分，确保不包含非法字符
    filename_base = re.sub(r'[^\w\-]', '_', filename_base)
    
    # 添加时间戳确保唯一性
    if created_at:
        # 处理可能的ISO日期格式，提取日期部分
        try:
            # 如果是ISO格式，转换为简单格式
            if 'T' in created_at:
                created_at = created_at.split('T')[0].replace('-', '')
            # 清理任何非数字、字母或下划线字符
            created_at = re.sub(r'[^\w]', '', created_at)
        except:
            # 如果转换失败，使用当前时间戳
            created_at = time.strftime("%Y%m%d_%H%M%S")
    else:
        # 使用当前时间戳
        created_at = time.strftime("%Y%m%d_%H%M%S")
    
    return f"{filename_base}_{created_at}.md"


async def extract_article_data_enhanced(page, url, schema):
    """增强版文章数据提取，使用SchemaProcessor处理不同格式的schema"""
    print("\n===== 开始提取文章数据 =====")
    print(f"URL: {url}")
    
    # 获取页面HTML
    html_content = await page.content()
    
    # 初始化Schema处理器
    processor = SchemaProcessor(url)
    
    # 提取内容
    data = processor.extract_content(html_content, schema)
    
    # 确保基本字段存在
    if 'title' not in data:
        title_text = await page.title()
        data['title'] = title_text or "未知标题"
    
    # 添加URL和提取时间
    data['url'] = url
    data['extracted_at'] = time.strftime("%Y-%m-%d %H:%M:%S")
    
    print(f"标题: {data.get('title')}")
    if 'author' in data:
        print(f"作者: {data.get('author')}")
    if 'date' in data:
        print(f"日期: {data.get('date')}")
    
    print("===== 提取文章数据结束 =====\n")
    return data


def save_to_markdown_enhanced(data, output_dir, url):
    """增强版Markdown保存，使用唯一文件名"""
    if not data or 'content_markdown' not in data:
        print("错误：没有内容可保存")
        return None
    
    # 创建输出目录
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 生成唯一文件名
    title = data.get('title', 'untitled')
    date = data.get('date')
    filename = generate_filename(url, title, date)
    filepath = output_dir / filename
    
    print(f"准备保存Markdown文件: {filepath}")
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            # 写入元数据 (YAML Front Matter)
            f.write("---\n")
            f.write(f"title: {data.get('title', 'N/A')}\n")
            if data.get('author'):
                f.write(f"author: {data['author']}\n")
            if data.get('date'):
                f.write(f"date: {data['date']}\n")
            f.write(f"source_url: {url}\n")
            f.write(f"extracted_at: {data.get('extracted_at', time.strftime('%Y-%m-%d %H:%M:%S'))}\n")
            f.write("---\n\n")
            
            # 写入Markdown内容
            f.write(f"# {data.get('title', 'N/A')}\n\n")
            
            # 添加元数据行
            metadata_parts = []
            if data.get('author'):
                metadata_parts.append(f"**作者:** {data['author']}")
            if data.get('date'):
                metadata_parts.append(f"**发布日期:** {data['date']}")
            
            if metadata_parts:
                f.write(f"{' | '.join(metadata_parts)}\n\n")
            
            # 写入正文内容
            f.write(data['content_markdown'])
        
        print(f"Markdown文件保存成功: {filepath}")
        return filepath
    except Exception as e:
        print(f"错误：保存Markdown文件失败: {e}")
        return None


async def extract_urls_enhanced(page, schema, base_url=None):
    """
    增强版URL提取函数，使用SchemaProcessor处理不同格式的schema
    
    参数:
        page: Playwright页面对象
        schema: Schema配置
        base_url: 基础URL (可选)
    
    返回:
        提取的URL列表
    """
    # 如果未提供base_url，尝试从页面获取
    if not base_url:
        base_url = page.url
    
    print(f"使用增强提取器提取URL，基础URL: {base_url}")
    
    # 获取页面HTML内容
    html_content = await page.content()
    
    # 初始化Schema处理器
    processor = SchemaProcessor(base_url)
    
    # 提取URLs
    urls = processor.extract_urls(html_content, schema)
    
    print(f"成功提取 {len(urls)} 个URL")
    return urls

async def crawl_with_config(config_path):
    """使用指定配置文件运行爬虫"""
    # 1. 加载配置和 Schema
    print(f"\n===== 启动爬虫任务 {Path(config_path).stem} =====")
    print(f"当前时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    config = load_config(config_path)
    if not config:
        print(f"错误：无法加载配置文件 {config_path}")
        return False
    
    # 检查是否使用自定义 Schema 格式
    use_custom_schema = config.get('use_custom_schema', False)
    
    # 加载常规 Schema
    print(f"使用自定义Schema: {use_custom_schema}")
    start_schema = load_schema(config['start_page_schema']) if not use_custom_schema else None
    secondary_schema = load_schema(config['secondary_page_schema'])
    
    # 如果指定使用自定义 Schema 但常规 Schema 加载失败，尝试解析自定义 Schema
    if use_custom_schema and not start_schema:
        custom_schema_path = config.get('custom_schema_path', config['start_page_schema'])
        try:
            print(f"尝试加载自定义Schema: {custom_schema_path}")
            with open(custom_schema_path, 'r', encoding='utf-8') as f:
                custom_schema_data = json.load(f)
                start_schema = parse_custom_schema(custom_schema_data)
                if not start_schema:
                    print("错误：无法解析自定义 Schema")
                    return False
        except Exception as e:
            print(f"错误：加载自定义 Schema 文件失败: {e}")
            return False
    
    if not start_schema or not secondary_schema:
        print("错误：无法加载必要的 Schema 文件")
        return False
    
    output_dir = config['output_directory']
    start_url = config.get('start_url', start_schema.get('start_url')) if use_custom_schema else config['start_url']
    crawler_settings = config.get('crawler_settings', {})
    playwright_settings = crawler_settings.get('playwright', {})
    request_delay = crawler_settings.get('request_delay', 1)
    
    print(f"起始URL: {start_url}")
    print(f"输出目录: {output_dir}")
    print(f"爬取延迟: {request_delay}秒")

    # 2. 初始化 Playwright
    print("\n===== 初始化浏览器 =====")
    async with async_playwright() as p:
        browser_type = getattr(p, playwright_settings.get('browser', 'chromium'))
        browser = await browser_type.launch(headless=playwright_settings.get('headless', True))
        context = await browser.new_context(user_agent=playwright_settings.get('user_agent'))
        page = await context.new_page()
        print("Playwright 初始化完成")
        
        # 3. 访问起始页并提取二级URL
        print(f"\n===== 访问起始页 =====")
        print(f"URL: {start_url}")
        await page.goto(start_url, timeout=playwright_settings.get('timeout', 30000))
        print("页面加载完成")
        
        # 使用增强版URL提取函数，处理不同格式的schema
        print("使用增强版URL提取器...")
        secondary_urls = await extract_urls_enhanced(page, start_schema, start_url)
        
        if not secondary_urls:
            print("错误：未从起始页提取到任何二级URL，程序终止")
            await browser.close()
            return False
        
        # 过滤URL
        filtered_urls = []
        for url in secondary_urls:
            # 过滤掉分类页面
            if '/content-type/' in url or '/category/' in url:
                print(f"跳过分类页面: {url}")
                continue
            filtered_urls.append(url)
        
        if not filtered_urls:
            # 如果过滤后没有URL，使用原始URL列表
            print("警告：过滤后没有URL剩余，将使用原始URL列表")
            filtered_urls = secondary_urls
        
        print(f"\n===== 开始爬取 {len(filtered_urls)} 个二级页面 =====")
        
        # 4. 遍历并爬取二级页面
        successful_extracts = 0
        for i, url in enumerate(filtered_urls):
            print(f"\n[{i+1}/{len(filtered_urls)}] 处理页面: {url}")
            
            try:
                await page.goto(url, timeout=playwright_settings.get('timeout', 30000))
                print("页面加载完成")
                
                # 使用增强版文章提取
                article_data = await extract_article_data_enhanced(page, url, secondary_schema)
                
                if article_data and 'content_markdown' in article_data:
                    saved_file = save_to_markdown_enhanced(article_data, Path(output_dir), url)
                    if saved_file:
                        successful_extracts += 1
                else:
                    print(f"警告：未能提取文章内容，跳过保存")
            except Exception as e:
                print(f"错误：处理页面时出错: {e}")
            
            # 添加请求延迟
            if i < len(filtered_urls) - 1:
                print(f"等待 {request_delay} 秒...")
                await asyncio.sleep(request_delay)
        
        # 5. 关闭浏览器并汇总结果
        await browser.close()
        print(f"\n===== 爬取完成 =====")
        print(f"总计爬取: {len(filtered_urls)} 个页面")
        print(f"成功提取并保存: {successful_extracts} 篇文章")
        print(f"完成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        
    return True

async def main():
    """主函数，处理命令行参数并运行爬虫任务"""
    parser = argparse.ArgumentParser(description="SuperCrawler爬虫工具")
    parser.add_argument("workflow", nargs="?", help="指定要运行的工作流YAML文件路径（可选）")
    args = parser.parse_args()
    
    # 统计运行结果
    total_tasks = 0
    successful_tasks = 0
    
    if args.workflow:
        # 运行指定的工作流文件
        workflow_path = Path(args.workflow)
        if not workflow_path.exists():
            print(f"错误：工作流文件 {args.workflow} 不存在")
            return
        
        print(f"运行指定的工作流: {workflow_path}")
        total_tasks += 1
        success = await crawl_with_config(workflow_path)
        if success:
            successful_tasks += 1
    else:
        # 运行workflows目录下所有YAML文件
        workflows_dir = Path("workflows")
        if not workflows_dir.exists():
            print(f"错误：工作流目录 {workflows_dir} 不存在")
            return
        
        print(f"扫描工作流目录: {workflows_dir}")
        workflow_files = list(workflows_dir.glob("*.yaml")) + list(workflows_dir.glob("*.yml"))
        
        if not workflow_files:
            print("未找到任何工作流YAML文件")
            return
        
        print(f"找到 {len(workflow_files)} 个工作流文件:")
        for i, wf in enumerate(workflow_files):
            print(f"  {i+1}. {wf.name}")
        
        for workflow_path in workflow_files:
            total_tasks += 1
            print(f"\n{'='*50}")
            print(f"开始执行工作流: {workflow_path.name}")
            success = await crawl_with_config(workflow_path)
            if success:
                successful_tasks += 1
    
    # 输出总体统计信息
    print(f"\n{'='*50}")
    print(f"所有任务执行完成!")
    print(f"总计任务数: {total_tasks}")
    print(f"成功任务数: {successful_tasks}")
    print(f"失败任务数: {total_tasks - successful_tasks}")
    print(f"总体完成率: {successful_tasks/total_tasks*100:.1f}%")
    print(f"总体完成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")


# 确保导入所需的库
import re
from schema_processor import SchemaProcessor

if __name__ == "__main__":
    asyncio.run(main())