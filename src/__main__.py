#!/usr/bin/env python3
"""
SuperCrawler - 主入口文件
"""
import os
import sys
import logging
import asyncio
import argparse
from pathlib import Path

# 确保src目录在路径中
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from src.core.workflow_engine import WorkflowEngine
# 引入增强集成模块
try:
    from src.utils.integration import apply_patches
except ImportError:
    def apply_patches():
        return False

# 确保logs目录存在
logs_dir = os.path.join(parent_dir, 'logs')
if not os.path.exists(logs_dir):
    os.makedirs(logs_dir)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(logs_dir, "supercrawler.log"), encoding='utf-8')
    ]
)
logger = logging.getLogger("SuperCrawler")

async def run_workflow(workflow_path, debug=False):
    """运行单个工作流"""
    from datetime import datetime
    start_time = datetime.now()
    logger.info(f"开始执行工作流: {workflow_path}")
    
    try:
        # 应用增强补丁
        if apply_patches():
            logger.info("已应用XPath和字段提取增强补丁")
        
        engine = WorkflowEngine(workflow_path, logs_dir=logs_dir)
        result = await engine.run()
        
        # 输出结果摘要
        success_status = "✅ 成功" if result["success"] else "❌ 失败"
        logger.info(f"工作流执行完成: {success_status}")
        logger.info(f"完成步骤: {result['steps_completed']}/{result['total_steps']}")
        logger.info(f"提取数据量: {result['data_extracted']}")
        logger.info(f"执行时间: {result['execution_time']}")
        
        if result.get("output_file"):
            logger.info(f"输出文件: {result['output_file']}")
        
        if result["errors"]:
            logger.error("执行过程中出现错误:")
            for error in result["errors"]:
                logger.error(f"- {error}")
        
        return result["success"]
        
    except Exception as e:
        logger.error(f"执行工作流时出错: {e}", exc_info=True)
        return False
    
async def run_all_workflows(directory, debug=False):
    """运行目录中的所有工作流"""
    workflows = []
    for filename in os.listdir(directory):
        if filename.endswith('.yaml') or filename.endswith('.yml'):
            workflows.append(os.path.join(directory, filename))
    
    if not workflows:
        logger.warning(f"目录 {directory} 中未找到工作流文件")
        return
    
    logger.info(f"找到 {len(workflows)} 个工作流")
    
    # 统计结果
    success_count = 0
    failed_count = 0
    
    for workflow in workflows:
        success = await run_workflow(workflow, debug)
        if success:
            success_count += 1
        else:
            failed_count += 1
    
    # 输出总结
    logger.info("\n========== 工作流执行总结 ==========")
    logger.info(f"总工作流数: {len(workflows)}")
    logger.info(f"成功: {success_count}")
    logger.info(f"失败: {failed_count}")

async def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='SuperCrawler - 灵活的网页爬虫工作流引擎')
    parser.add_argument('workflow', nargs='?', help='工作流文件路径 (.yaml)')
    parser.add_argument('--debug', action='store_true', help='启用调试模式')
    parser.add_argument('--all', action='store_true', help='运行所有工作流')
    args = parser.parse_args()
    
    # 设置调试模式
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("调试模式已启用")
    
    if args.workflow:
        # 执行指定工作流
        workflow_path = args.workflow
        if not os.path.exists(workflow_path):
            logger.error(f"工作流文件不存在: {workflow_path}")
            return
        
        await run_workflow(workflow_path, args.debug)
    else:
        # 优先检查项目根目录下的workflows目录
        root_workflows_dir = os.path.join(parent_dir, 'workflows')
        if os.path.exists(root_workflows_dir) and os.path.isdir(root_workflows_dir):
            logger.info(f"使用项目根目录的工作流: {root_workflows_dir}")
            await run_all_workflows(root_workflows_dir, args.debug)
        else:
            # 回退到src/workflows目录
            src_workflows_dir = os.path.join(os.path.dirname(__file__), 'workflows')
            if os.path.exists(src_workflows_dir):
                logger.info(f"使用src目录下的工作流: {src_workflows_dir}")
                await run_all_workflows(src_workflows_dir, args.debug)
            else:
                logger.error(f"未找到工作流目录")
                return

if __name__ == "__main__":
    asyncio.run(main()) 