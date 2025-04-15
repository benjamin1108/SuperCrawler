#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
单文件工作流爬虫示例程序
使用内联Schema配置运行爬虫
"""

import os
import sys
import argparse
import asyncio
from pathlib import Path

from workflow_manager import WorkflowManager
from crawler import Crawler

async def run_crawler(workflow_file):
    """使用指定的工作流文件运行爬虫"""
    # 初始化工作流管理器
    manager = WorkflowManager("workflows")
    
    # 加载指定的工作流
    workflow_path = Path(workflow_file)
    if not workflow_path.exists():
        print(f"错误: 工作流文件 '{workflow_file}' 不存在")
        return False
    
    # 加载工作流
    print(f"正在加载工作流: {workflow_path}")
    workflow = manager.load_workflow(workflow_path)
    
    if not workflow:
        print("错误: 工作流加载失败")
        return False
    
    print(f"工作流 '{workflow['_name']}' 已加载")
    print(f"起始URL: {workflow['start_url']}")
    print(f"输出目录: {workflow['output_directory']}")
    
    # 获取爬虫设置
    crawler_settings = workflow.get("crawler_settings", {})
    delay = crawler_settings.get("request_delay", 2.0)
    max_urls = crawler_settings.get("max_urls", 100)
    max_retries = crawler_settings.get("max_retries", 3)
    timeout = crawler_settings.get("timeout", 30)
    
    # 初始化爬虫
    crawler = Crawler(
        workflow, 
        output_dir=workflow["output_directory"],
        delay=delay,
        max_retries=max_retries,
        timeout=timeout
    )
    
    # 启动爬虫
    print(f"启动爬虫，最大爬取URL数: {max_urls}")
    processed, failed = crawler.start(max_urls=max_urls)
    
    print("\n爬取完成")
    print(f"成功处理: {processed} 个URL")
    print(f"失败处理: {failed} 个URL")
    print(f"输出目录: {workflow['output_directory']}")
    
    return True

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="使用单文件工作流配置运行爬虫")
    parser.add_argument("workflow", help="工作流配置文件路径")
    args = parser.parse_args()
    
    if not os.path.exists(args.workflow):
        print(f"错误: 工作流文件 '{args.workflow}' 不存在")
        return 1
    
    try:
        asyncio.run(run_crawler(args.workflow))
        return 0
    except KeyboardInterrupt:
        print("\n爬虫已中断")
        return 1
    except Exception as e:
        print(f"错误: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 