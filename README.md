                    _____                                             _       
                   / ____|                                           | |      
  ___ _   _ _ __ | |     _ __ __ ___      _| | ___ _ __ 
 / __| | | | '_ \| |    | '__/ _` \ \ /\ / / |/ _ \ '__|
 \__ \ |_| | |_) | |____| | | (_| |\ V  V /| |  __/ |   
 |___/\__,_| .__/ \_____|_|  \__,_| \_/\_/ |_|\___|_|   
           | |                                           
           |_|                                           
```

# SuperCrawler - 灵活的网页爬虫工作流引擎

SuperCrawler 是一个基于 Python 和 Playwright 的网页爬虫工作流引擎，可以通过 YAML 配置文件定义爬取流程，无需编写代码即可实现复杂的网页数据采集任务。

## 特性

- 基于 YAML 的声明式工作流定义
- 使用 Playwright 实现全自动化浏览器控制
- 支持 XPath 和 CSS 选择器提取内容
- 支持分页处理、条件判断和循环
- 支持数据后处理和格式化输出 (Markdown/JSON)
- 自动生成元素选择器，减少手动操作
- 详细的日志记录，便于调试和监控

## 目录结构

```
supercrawler/
├── src/                    # 源代码
│   ├── core/               # 核心组件
│   │   ├── workflow_engine.py     # 工作流引擎
│   │   ├── workflow_manager.py    # 工作流管理器
│   │   └── crawler.py             # 爬虫实现
│   ├── extractors/         # 数据提取器
│   │   ├── xpath_processor.py     # XPath处理器
│   │   ├── field_extractor.py     # 字段提取器
│   │   └── workflow_links_extractor.py   # 链接提取器
│   ├── utils/              # 工具类
│   │   ├── element_generalizer.py # 元素选择器生成器
│   │   ├── schema_processor.py    # Schema处理器
│   │   └── integration.py         # 集成工具
│   ├── workflows/          # 预定义工作流
│   │   └── aws_whatsnew.yaml      # AWS新闻爬虫
│   ├── __init__.py         # 包初始化
│   └── __main__.py         # 主入口
├── tests/                  # 测试代码
├── supercrawler.py         # 命令行入口
├── setup.py                # 安装配置
├── requirements.txt        # 依赖列表
└── README.md               # 项目说明
```

## 安装方法

1. 克隆仓库

```bash
git clone https://github.com/yourusername/supercrawler.git
cd supercrawler
```

2. 创建虚拟环境

```bash
python -m venv venv
source venv/bin/activate  # 在Windows上: venv\Scripts\activate
```

3. 安装依赖

```bash
pip install -e .
```

4. 安装Playwright浏览器

```bash
playwright install
```

## 使用方法

### 运行单个工作流

```bash
python supercrawler.py workflows/aws_whatsnew.yaml
```

或者安装后直接使用命令行工具:

```bash
supercrawler workflows/aws_whatsnew.yaml
```

### 调试模式

```bash
python supercrawler.py workflows/aws_whatsnew.yaml --debug
```

### 运行所有工作流

```bash
python supercrawler.py --all
```

## 工作流定义示例

以下是一个简单的工作流配置示例，用于爬取网站新闻列表:

```yaml
workflow_name: "新闻爬虫"
description: "爬取新闻列表并保存内容"
version: "1.0"

# 配置
config:
  headless: false    # 是否使用无头模式
  timeout: 30000     # 超时时间 (毫秒)
  output_directory: "output/news"  # 输出目录
  debug: true        # 调试模式

# 起始页面
start:
  url: "https://example.com/news"

# 工作流
flow:
  # 爬取新闻列表页面
  - step: "news_list"
    next: "process_items"
    actions:
      # 等待页面加载
      - action: "wait"
        timeout: 5000
      
      # 提取新闻列表
      - action: "extract"
        target: "links"
        element:
          sample: "xpath=//div[@class='news-list']/div[@class='news-item']"
        output: "news_items"
  
  # 处理每条新闻
  - step: "process_items"
    next: "finish"
    for_each: "${news_items}"
    actions:
      # 访问详情页
      - action: "visit"
        url: "${current_item.href}"
      
      # 提取详情内容
      - action: "extract"
        target: "content"
        elements:
          - name: "title"
            sample: "xpath=//h1"
          - name: "content"
            sample: "xpath=//div[@class='article-content']"
        output: "article_data"
      
      # 保存为Markdown文件
      - action: "save"
        data: {
          "title": "${article_data.title}",
          "content": "${article_data.content}",
          "url": "${current_item.href}"
        }
        format: "markdown"
  
  # 完成步骤
  - step: "finish"
    actions:
      - action: "wait"
        timeout: 1000
```

## 工作流配置

SuperCrawler现在支持两种位置的工作流配置文件：

1. **项目根目录下的`workflows/`文件夹**（推荐）：
   - 可以直接在此处添加新的工作流文件，无需修改源代码
   - 运行方式：`python supercrawler.py 工作流名称`
   - 详细说明请查看[workflows/README.md](workflows/README.md)

2. **源码目录下的`src/workflows/`文件夹**：
   - 这是系统的默认工作流目录，包含了预置的工作流示例
   - 若根目录下不存在同名工作流，系统会自动查找此目录

我们建议在`workflows/`目录下开发和管理您的工作流，保持源代码目录的整洁。

## 贡献

欢迎通过提交 Issue 或 Pull Request 的方式参与项目贡献。

## 许可证

本项目采用 MIT 许可证，详情请参阅 LICENSE 文件。 