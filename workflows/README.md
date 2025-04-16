# SuperCrawler 工作流目录

这个目录包含SuperCrawler的各种工作流配置文件。您可以直接在这里添加新的工作流文件，无需修改项目的源代码目录。

## 现有工作流

- `aws_whatsnew.yaml` - AWS What's New 爬虫，用于抓取AWS的产品更新信息
- `azure_tech_blog.yaml` - Azure 技术博客爬虫，用于抓取Azure的技术博客内容
- `gcp_whats_new.yaml` - Google Cloud Platform 新功能爬虫，用于抓取GCP的更新信息
- `test_local.yaml` - 本地测试工作流，用于测试和演示

## 如何使用

您可以通过以下方式运行工作流：

1. 指定完整路径：
   ```
   python supercrawler.py workflows/aws_whatsnew.yaml
   ```

2. 仅指定工作流名称（无需扩展名）：
   ```
   python supercrawler.py aws_whatsnew
   ```

3. 运行所有工作流：
   ```
   python supercrawler.py
   ```

## 创建新工作流

要创建新的工作流，只需在此目录中添加新的YAML文件，按照现有工作流的格式定义您的爬取规则：

1. 复制一个现有的工作流文件作为模板
2. 修改配置参数、URL和提取规则
3. 保存为新的YAML文件
4. 直接运行您的新工作流：`python supercrawler.py 您的工作流名称` 