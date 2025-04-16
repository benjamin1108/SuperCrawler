#!/usr/bin/env python3
"""
清理项目脚本 - 删除冗余和无用的文件
"""
import os
import shutil
import sys

# 已经移动到src目录下的源文件（现在根目录下的可以删除）
source_files_to_remove = [
    'crawler.py',
    'element_generalizer.py',
    'extractor.py',
    'field_extractor.py',
    'integration.py',
    'main.py',
    'run_crawler.py',
    'schema_processor.py',
    'workflow_engine.py',
    'workflow_links_extractor.py',
    'workflow_manager.py',
    'xpath_processor.py',
]

# 测试和临时文件（移到tests目录或删除）
test_files_to_move = [
    'test_selectors.py',
    'test_xpath.py',
    'test_page.html',
    'detail1.html',
]

# 输出和日志文件（删除）
log_files_to_remove = [
    'element_generalizer.log',
    'supercrawler.log',
    'workflow_engine.log',
    'schema_processor.log',
]

# 临时配置和分析文件（删除或移动）
config_files_to_handle = [
    'aws_page_analysis.json',
    'analyze_page.py',
    'workflow_schema.yaml',
]

# 不再需要的目录
directories_to_remove = [
    'schemas',        # 已被workflows目录替代
    '__pycache__',    # Python缓存文件
    'js_scripts',     # 如果已经集成到主代码中
]

def cleanup():
    """执行清理操作"""
    # 确保我们在项目根目录下
    if not os.path.exists('src') or not os.path.exists('setup.py'):
        print("错误：此脚本必须在项目根目录下运行")
        sys.exit(1)
    
    # 创建备份目录（以防万一）
    backup_dir = '_backup_files'
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    # 处理源文件
    for file in source_files_to_remove:
        if os.path.exists(file):
            print(f"移动到备份: {file}")
            shutil.copy2(file, os.path.join(backup_dir, file))
            os.remove(file)
    
    # 处理测试文件
    if not os.path.exists('tests/resources'):
        os.makedirs('tests/resources')
    
    for file in test_files_to_move:
        if os.path.exists(file):
            print(f"移动到测试目录: {file}")
            shutil.copy2(file, os.path.join('tests', file))
            os.remove(file)
    
    # 处理日志文件
    for file in log_files_to_remove:
        if os.path.exists(file):
            print(f"删除日志文件: {file}")
            os.remove(file)
    
    # 处理配置文件
    config_backup = os.path.join(backup_dir, 'configs')
    if not os.path.exists(config_backup):
        os.makedirs(config_backup)
    
    for file in config_files_to_handle:
        if os.path.exists(file):
            print(f"移动配置文件: {file}")
            shutil.copy2(file, os.path.join(config_backup, file))
            os.remove(file)
    
    # 处理不再需要的目录
    for directory in directories_to_remove:
        if os.path.exists(directory) and os.path.isdir(directory):
            print(f"处理目录: {directory}")
            
            # 创建相应的备份目录
            backup_subdir = os.path.join(backup_dir, directory)
            if not os.path.exists(backup_subdir):
                os.makedirs(backup_subdir)
            
            # 复制目录内容到备份
            for item in os.listdir(directory):
                src_path = os.path.join(directory, item)
                dst_path = os.path.join(backup_subdir, item)
                
                if os.path.isfile(src_path):
                    shutil.copy2(src_path, dst_path)
                elif os.path.isdir(src_path):
                    shutil.copytree(src_path, dst_path)
            
            # 删除原目录
            shutil.rmtree(directory)
            print(f"已移除目录: {directory}")
    
    # 处理根目录下的workflows目录
    if os.path.exists('workflows') and os.path.isdir('workflows'):
        print("处理根目录workflows...")
        
        # 确保目标目录存在
        if not os.path.exists('src/workflows'):
            os.makedirs('src/workflows')
        
        # 移动所有工作流定义文件到src/workflows
        for item in os.listdir('workflows'):
            src_path = os.path.join('workflows', item)
            dst_path = os.path.join('src/workflows', item)
            
            if os.path.isfile(src_path):
                # 检查目标文件是否已存在
                if os.path.exists(dst_path):
                    print(f"文件已存在于目标目录: {item}，比较内容...")
                    # 如果文件内容相同，则跳过
                    with open(src_path, 'rb') as f1, open(dst_path, 'rb') as f2:
                        if f1.read() == f2.read():
                            print(f"文件内容相同，跳过: {item}")
                            # 备份原文件
                            workflows_backup = os.path.join(backup_dir, 'workflows')
                            if not os.path.exists(workflows_backup):
                                os.makedirs(workflows_backup)
                            shutil.copy2(src_path, os.path.join(workflows_backup, item))
                            continue
                        else:
                            print(f"文件内容不同，重命名为: {item}.old")
                            # 备份目标文件
                            os.rename(dst_path, f"{dst_path}.old")
                
                # 复制文件到目标目录
                print(f"移动工作流文件: {item}")
                shutil.copy2(src_path, dst_path)
        
        # 创建备份
        workflows_backup = os.path.join(backup_dir, 'workflows')
        if not os.path.exists(workflows_backup):
            os.makedirs(workflows_backup)
        
        # 复制整个目录到备份
        for item in os.listdir('workflows'):
            src_path = os.path.join('workflows', item)
            dst_path = os.path.join(workflows_backup, item)
            
            if os.path.isfile(src_path):
                shutil.copy2(src_path, dst_path)
        
        # 删除原目录
        shutil.rmtree('workflows')
        print("已移除根目录workflows")
    
    # 确保.gitignore包含常见的排除项
    ensure_gitignore()
    
    print("\n清理完成！")
    print(f"备份文件已保存到 {backup_dir} 目录")

def ensure_gitignore():
    """确保.gitignore文件包含必要的排除项"""
    gitignore_entries = [
        # Python
        "__pycache__/",
        "*.py[cod]",
        "*$py.class",
        "*.so",
        ".Python",
        "env/",
        "build/",
        "develop-eggs/",
        "dist/",
        "downloads/",
        "eggs/",
        ".eggs/",
        "lib/",
        "lib64/",
        "parts/",
        "sdist/",
        "var/",
        "*.egg-info/",
        ".installed.cfg",
        "*.egg",
        
        # 虚拟环境
        "venv/",
        "ENV/",
        
        # 日志和输出
        "*.log",
        "output/",
        "_backup_files/",
        
        # IDE
        ".idea/",
        ".vscode/",
        "*.swp",
        "*.swo",
    ]
    
    # 读取现有的.gitignore
    existing_entries = []
    if os.path.exists('.gitignore'):
        with open('.gitignore', 'r') as f:
            existing_entries = [line.strip() for line in f.readlines()]
    
    # 添加缺失的条目
    new_entries = []
    for entry in gitignore_entries:
        if entry not in existing_entries:
            new_entries.append(entry)
    
    # 如果有新条目，更新.gitignore
    if new_entries:
        print("更新.gitignore文件...")
        with open('.gitignore', 'a') as f:
            f.write("\n# 自动添加的条目\n")
            for entry in new_entries:
                f.write(f"{entry}\n")

if __name__ == "__main__":
    choice = input("此脚本将清理项目中不必要的文件。继续？(y/n): ")
    if choice.lower() == 'y':
        cleanup()
    else:
        print("操作已取消") 