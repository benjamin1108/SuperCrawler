#!/usr/bin/env python3
"""
SuperCrawler 命令行入口
"""
import sys
import os
import asyncio

if __name__ == "__main__":
    # 确保当前目录在系统路径中
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.append(current_dir)
    
    # 转换参数 - 如果提供了workflows目录下的文件名，转换为完整路径
    args = sys.argv[1:]
    if len(args) >= 1 and not os.path.exists(args[0]):
        # 检查是否是workflows目录下的文件
        workflows_path = os.path.join(current_dir, 'workflows', args[0])
        if os.path.exists(workflows_path):
            args[0] = workflows_path
        else:
            # 尝试自动添加.yaml扩展名
            workflows_yaml = os.path.join(current_dir, 'workflows', args[0] + '.yaml')
            if os.path.exists(workflows_yaml):
                args[0] = workflows_yaml
    
    # 更新系统参数
    sys.argv[1:] = args
    
    # 导入主模块
    from src.__main__ import main
    
    # 启动爬虫
    asyncio.run(main()) 