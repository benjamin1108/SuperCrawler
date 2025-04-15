# SuperCrawler 超级爬虫

SuperCrawler 是一个强大的可配置网页爬虫工具，能够根据配置文件和 Schema 定义来爬取网页内容并保存为 Markdown 格式。它特别适合爬取博客文章、新闻和其他带有结构化内容的网页。

## 功能特点

- 🚀 支持 JavaScript 渲染 - 使用 Playwright 处理动态加载的内容
- 🔍 通用 Schema 处理器 - 灵活适配各种不同格式的 Schema 配置
- 📝 Markdown 输出 - 自动将爬取内容转换为美观的 Markdown 格式
- 🌐 支持相对 URL - 自动处理相对路径和绝对路径的 URL
- ⏱️ 请求延迟 - 防止频繁请求被网站封锁
- 📄 单文件配置 - 支持在一个YAML文件中定义完整的工作流和Schema
- 🔄 批量任务处理 - 支持自动遍历并执行多个爬虫任务

## 安装依赖

```bash
# 安装 Python 依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器驱动
playwright install

# 或者只安装 Chromium
playwright install chromium
```

## 使用方法

1. **配置文件**：在 `workflows` 目录下创建 YAML 配置文件

   ```yaml
   # 工作流名称
   workflow_name: "博客爬虫"
   
   # 设置爬取的起始 URL
   start_url: "https://example.com/blog"
   
   # 修改输出目录
   output_directory: "output/blog"
   
   # 设置爬取间隔
   crawler_settings:
     request_delay: 2.0
   ```

2. **定义 Schema**：支持多种格式的 Schema 定义

   ### 内联 Schema 格式（单文件工作流）

   ```yaml
   # 起始页Schema
   start_page_schema_inline:
     container: "div.article-list"
     link_selector: "h2.title > a"
     attribute: "href"
   
   # 内容页Schema
   secondary_page_schema_inline:
     title: "h1.article-title"
     author: "span.author-name"
     date: "time.publish-date"
     content: "div.article-content"
   ```

   ### 新的选择器格式

   ```yaml
   start_page_schema_inline:
     selectors: 
       - 
         type: a
         selector: 
           css: "a.article-link"
         fields: 
           url: 
             type: attribute
             selector: .
             attribute: href
           content: 
             type: text
             selector: .
   ```

3. **运行爬虫**：支持两种运行模式

   ```bash
   # 运行特定的工作流文件
   python main.py workflows/blog_crawler.yaml
   
   # 自动运行workflows目录下所有的YAML文件
   python main.py
   ```

## Schema 处理器

SuperCrawler 使用通用 Schema 处理器来适配各种不同格式的 Schema 配置，极大提高了系统的灵活性。

### 支持的 Schema 格式

1. **传统格式**：使用 container, link_selector, attribute 等字段
2. **选择器格式**：使用 selectors 字段及其内部的定义
3. **通用格式**：当无法识别特定格式时的默认处理方法

### Schema 处理器功能

- **URL 提取**：从 HTML 内容中提取符合条件的 URL
- **内容提取**：从文章页面提取结构化内容
- **转换处理**：将 HTML 内容转换为 Markdown 格式
- **多格式兼容**：自动识别并适配不同的 Schema 格式

## 工作流配置示例

### 完整工作流配置

```yaml
workflow_name: "博客爬虫示例"
start_url: "https://example.com/blog"

# 内联Schema定义
start_page_schema_inline:
  container: "div.article-list"
  link_selector: "h2.title > a"
  attribute: "href"

secondary_page_schema_inline:
  title: "h1.article-title"
  author: "span.author-name"
  date: "time.publish-date"
  content: "div.article-content"

# URL过滤规则
url_patterns:
  include: ["/blog/", "/article/"]
  exclude: ["/tag/", "/category/"]
  content: ["/article/[a-z0-9-]+"]

# 爬虫设置
crawler_settings:
  engine: "playwright"
  playwright:
    headless: true
    browser: "chromium"
    timeout: 30000
  request_delay: 2.0
  max_urls: 100
  max_retries: 3

# 输出设置
output_directory: "output/blog_example"
```

## 批量任务处理

SuperCrawler 支持自动遍历 `workflows` 目录下的所有 YAML 文件并执行爬虫任务：

1. 放置多个工作流配置文件在 `workflows` 目录下
2. 直接运行 `python main.py`
3. 系统会顺序执行所有工作流，并生成汇总报告

## 自定义定制

SuperCrawler 设计为灵活且易于扩展。您可以修改源代码以添加更多功能，例如：

- 添加更多爬虫引擎支持 (例如 `requests`)
- 增强错误处理和重试机制
- 添加更多输出格式
- 实现数据清洗和后处理

## 注意事项

- 请遵守网站的 robots.txt 规则
- 避免过于频繁的请求，设置合理的 `request_delay`
- 尊重网站的版权，确保您对爬取的内容有合法的使用权限 