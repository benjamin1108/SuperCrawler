#!/usr/bin/env python3
"""
检查SuperCrawler项目包是否正确
"""
import os
import sys
import subprocess
import tempfile
import shutil

def check_installation():
    """检查项目是否可以被正确安装"""
    print("检查SuperCrawler项目包...")
    
    # 检查基本文件是否存在
    required_files = [
        'setup.py',
        'requirements.txt',
        'README.md',
        'src/__main__.py',
        'src/core/workflow_engine.py',
    ]
    
    for file in required_files:
        if not os.path.exists(file):
            print(f"错误: 缺少必需文件 {file}")
            return False
    
    # 检查package_data是否包含工作流定义文件
    if not os.path.exists('src/workflows/aws_whatsnew.yaml'):
        print("警告: 工作流定义文件可能不会被正确打包")
    
    # 检查import路径是否正确
    try:
        # 获取当前项目的绝对路径
        project_path = os.path.abspath(os.getcwd())
        
        # 创建一个临时目录
        with tempfile.TemporaryDirectory() as temp_dir:
            # 切换到临时目录
            os.chdir(temp_dir)
            
            # 创建一个简单的测试脚本
            test_script = f"""
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, '{project_path}')

try:
    from src.__main__ import main
    print("成功导入main函数")
    
    from src.core.workflow_engine import WorkflowEngine
    print("成功导入WorkflowEngine类")
    
    from src.extractors.xpath_processor import XPathProcessor
    print("成功导入XPathProcessor类")
    
    from src.utils.integration import apply_patches
    print("成功导入apply_patches函数")
    
    print("所有导入测试通过")
    sys.exit(0)
except ImportError as e:
    print(f"导入错误: {{e}}")
    sys.exit(1)
"""
            with open('test_import.py', 'w') as f:
                f.write(test_script)
            
            # 运行测试脚本
            print("\n运行导入测试...")
            result = subprocess.run(
                [sys.executable, 'test_import.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            print(result.stdout)
            if result.returncode != 0:
                print(f"错误: {result.stderr}")
                return False
    
    except Exception as e:
        print(f"测试过程中出错: {e}")
        return False
    
    print("\n所有检查通过！")
    return True

def check_workflow_files():
    """检查工作流定义文件是否正确"""
    print("\n检查工作流定义文件...")
    
    try:
        workflows_dir = 'src/workflows'
        if not os.path.exists(workflows_dir):
            print(f"错误: 工作流目录不存在 {workflows_dir}")
            return False
        
        workflow_files = [f for f in os.listdir(workflows_dir) if f.endswith('.yaml')]
        if not workflow_files:
            print("警告: 没有找到工作流定义文件")
            return False
        
        print(f"找到 {len(workflow_files)} 个工作流定义文件:")
        for wf in workflow_files:
            print(f"  - {wf}")
        
        return True
    
    except Exception as e:
        print(f"检查工作流文件时出错: {e}")
        return False

def check_output_dir():
    """检查输出目录是否在.gitignore中排除"""
    print("\n检查输出目录配置...")
    
    try:
        # 检查输出目录
        output_dir = 'output'
        if os.path.exists(output_dir) and os.path.isdir(output_dir):
            print(f"输出目录存在: {output_dir}")
            
            # 检查.gitignore中是否有输出目录
            gitignore_file = '.gitignore'
            if os.path.exists(gitignore_file):
                with open(gitignore_file, 'r') as f:
                    content = f.read()
                    if 'output/' in content:
                        print("输出目录已在.gitignore中排除")
                    else:
                        print("警告: 输出目录未在.gitignore中排除")
                        return False
            else:
                print("警告: 没有找到.gitignore文件")
                return False
        else:
            print(f"输出目录不存在: {output_dir}")
        
        return True
    
    except Exception as e:
        print(f"检查输出目录时出错: {e}")
        return False

def main():
    """主函数"""
    # 保存当前工作目录
    original_dir = os.getcwd()
    
    try:
        # 确保我们在项目根目录
        if not os.path.exists('src') or not os.path.exists('setup.py'):
            print("错误: 此脚本必须在项目根目录下运行")
            return False
        
        # 检查工作流文件
        workflow_check = check_workflow_files()
        
        # 检查输出目录
        output_check = check_output_dir()
        
        # 检查项目安装
        installation_check = check_installation()
        
        if workflow_check and output_check and installation_check:
            print("\n项目结构检查通过！项目可以正确安装和使用。")
            return True
        else:
            print("\n项目检查失败，请修复上述问题。")
            return False
    
    finally:
        # 恢复原始工作目录
        os.chdir(original_dir)

if __name__ == "__main__":
    sys.exit(0 if main() else 1) 