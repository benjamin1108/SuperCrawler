import logging
import os
import sys
from typing import Dict, List, Any, Optional, Tuple
import inspect

# 添加当前目录到系统路径，确保可以导入其他模块
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(os.path.dirname(current_dir))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from src.extractors.xpath_processor import XPathProcessor
from src.extractors.field_extractor import FieldExtractor
from src.extractors.workflow_links_extractor import WorkflowLinksExtractor

logger = logging.getLogger(__name__)

# 补丁函数需要接受相同的参数
async def extract_links_enhanced(self, action: Dict) -> Dict[str, Any]:
    """
    增强的链接提取函数，可以直接替换工作流引擎中的_extract_links方法
    
    参数:
        self: WorkflowEngine实例
        action: 动作配置
    """
    try:
        # 从action中解析参数
        element_config = action.get('element', {})
        if isinstance(element_config, str):
            # 兼容旧格式
            selector = element_config
        else:
            selector = element_config.get('sample', '')
        
        should_generalize = element_config.get('generalize', False)
        
        # 使用WorkflowLinksExtractor提取链接
        items = await WorkflowLinksExtractor.extract_links(self.page, selector, should_generalize)
        
        # 保存提取的URLs
        output_name = action.get('output')
        if output_name:
            self.current_state[output_name] = items
            logger.info(f"已提取 {len(items)} 个链接，保存到状态变量: {output_name}")
        
        # 构造返回格式与原函数相同
        return {
            "success": True,
            "extracted_count": len(items)
        }
    
    except Exception as e:
        logger.error(f"提取链接时出错: {e}", exc_info=True)
        return {
            "success": False,
            "error": str(e)
        }

async def process_workflow_element(element, field_config=None):
    """
    处理工作流元素，提取配置的字段
    
    参数:
        element: Playwright元素句柄
        field_config: 字段配置，格式为 {"字段名": "选择器或规则"}
        
    返回:
        包含提取字段的字典
    """
    try:
        # 获取元素的HTML内容
        html_content = await element.evaluate("el => el.outerHTML")
        
        # 使用字段提取器
        extractor = FieldExtractor()
        return extractor.extract_fields(html_content, field_config)
    
    except Exception as e:
        logger.error(f"处理工作流元素时出错: {str(e)}")
        return {}

def apply_patches():
    """
    应用补丁到工作流引擎
    
    这个函数可以在主函数中调用，以动态修改工作流引擎的行为
    """
    try:
        # 动态导入工作流引擎
        from src.core.workflow_engine import WorkflowEngine
        
        # 保存原始方法的引用
        original_extract_links = WorkflowEngine._extract_links
        
        # 替换为增强的方法
        WorkflowEngine._extract_links = extract_links_enhanced
        
        logger.info("成功应用增强补丁到工作流引擎")
        return True
    
    except Exception as e:
        logger.error(f"应用补丁失败: {str(e)}")
        return False

async def test_integration():
    """测试集成功能"""
    from playwright.async_api import async_playwright
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        # 访问测试页面
        url = "https://aws.amazon.com/cn/about-aws/whats-new/networking_and_content_delivery/?whats-new-content.sort-by=item.additionalFields.postDateTime&whats-new-content.sort-order=desc&awsf.whats-new-products=*all"
        await page.goto(url)
        await page.wait_for_load_state('networkidle')
        
        # 测试链接提取 - 直接使用WorkflowLinksExtractor
        selector = "xpath=/html/body/div[2]/main/div[3]/div[2]/div[2]/div[4]/section/ul/li"
        links = await WorkflowLinksExtractor.extract_links(page, selector)
        
        print(f"提取到 {len(links)} 个链接:")
        for i, link in enumerate(links[:3]):  # 只显示前3个
            print(f"链接 {i+1}: {link['text']} -> {link['href']}")
        
        # 测试字段提取
        if links:
            # 访问第一个链接
            first_link = links[0]['href']
            await page.goto(first_link)
            await page.wait_for_load_state('networkidle')
            
            # 提取文章内容
            content_selector = "xpath=/html/body/div[2]/main/div/div/div/div/div/main"
            content_element = await page.query_selector(content_selector)
            
            if content_element:
                field_config = {
                    "title": "h1",
                    "date": "regex:\\d{4}-\\d{2}-\\d{2}",
                    "content": "main"
                }
                
                fields = await process_workflow_element(content_element, field_config)
                
                print("\n提取的字段:")
                for field, value in fields.items():
                    if field == "content" and value:
                        # 截断过长的内容
                        value = value[:200] + "..." if len(value) > 200 else value
                    print(f"{field}: {value}")
        
        await browser.close()

if __name__ == "__main__":
    import asyncio
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 运行测试
    asyncio.run(test_integration()) 