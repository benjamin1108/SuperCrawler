"""
工作流引擎 - 执行通过YAML定义的爬虫工作流
"""
import os
import yaml
import json
import logging
import asyncio
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
from pathlib import Path

from playwright.async_api import async_playwright, Browser, Page
from src.utils.element_generalizer import ElementGeneralizer

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("workflow_engine.log", encoding='utf-8')
    ]
)
logger = logging.getLogger("WorkflowEngine")

class WorkflowEngine:
    """通用爬虫工作流引擎"""
    
    def __init__(self, workflow_path: str, logs_dir: str = None):
        """
        初始化工作流引擎
        
        参数:
            workflow_path: 工作流YAML文件路径
            logs_dir: 日志文件目录，默认为当前目录
        """
        self.workflow_path = workflow_path
        self.workflow = None
        self.browser = None
        self.context = None
        self.page = None
        self.current_state = {}
        self.output_data = []
        
        # 配置日志目录
        self.logs_dir = logs_dir if logs_dir else "."
        if not os.path.exists(self.logs_dir):
            os.makedirs(self.logs_dir)
            
        # 配置单独的文件日志处理器
        workflow_log_path = os.path.join(self.logs_dir, "workflow_engine.log")
        file_handler = logging.FileHandler(workflow_log_path, encoding='utf-8')
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(file_handler)
        
        self.element_generalizer = ElementGeneralizer(logs_dir=self.logs_dir)
        logger.info(f"初始化工作流引擎，工作流路径: {workflow_path}")
        
    async def load_workflow(self) -> bool:
        """
        加载工作流定义
        
        返回:
            是否成功加载
        """
        try:
            with open(self.workflow_path, 'r', encoding='utf-8') as f:
                self.workflow = yaml.safe_load(f)
            
            # 验证工作流基本结构
            if not self._validate_workflow():
                logger.error("工作流验证失败")
                return False
            
            logger.info(f"成功加载工作流: {self.workflow.get('workflow_name', 'Unnamed')}")
            return True
            
        except Exception as e:
            logger.error(f"加载工作流出错: {e}", exc_info=True)
            return False
    
    def _validate_workflow(self) -> bool:
        """
        验证工作流定义是否有效
        
        返回:
            是否验证通过
        """
        # 检查必要的字段
        required_fields = ['workflow_name', 'start', 'flow']
        for field in required_fields:
            if field not in self.workflow:
                logger.error(f"工作流缺少必要字段: {field}")
                return False
        
        # 检查start配置
        if not isinstance(self.workflow['start'], dict) or 'url' not in self.workflow['start']:
            logger.error("工作流start配置无效，必须包含url字段")
            return False
        
        # 检查flow配置
        if not isinstance(self.workflow['flow'], list) or not self.workflow['flow']:
            logger.error("工作流flow配置无效，必须是非空列表")
            return False
        
        # 检查flow中的每个步骤
        for step in self.workflow['flow']:
            if not isinstance(step, dict) or 'step' not in step or 'actions' not in step:
                logger.error(f"工作流步骤配置无效: {step}")
                return False
        
        return True
    
    async def run(self) -> Dict[str, Any]:
        """
        运行工作流
        
        返回:
            运行结果
        """
        start_time = datetime.now()
        result = {
            "success": False,
            "steps_completed": 0,
            "total_steps": 0,
            "data_extracted": 0,
            "errors": [],
            "execution_time": "0:00:00"  # 默认执行时间
        }
        
        try:
            # 加载工作流
            if not self.workflow and not await self.load_workflow():
                result["errors"].append("加载工作流失败")
                result["execution_time"] = str(datetime.now() - start_time)
                return result
            
            # 初始化浏览器
            await self._init_browser()
            
            # 提取总步骤数
            result["total_steps"] = len(self.workflow['flow'])
            
            # 执行起始步骤 - 访问起始URL
            start_url = self.workflow['start']['url']
            await self.page.goto(start_url)
            logger.info(f"已访问起始URL: {start_url}")
            
            # 等待页面加载完成
            await self.page.wait_for_load_state('networkidle')
            
            # 执行工作流步骤
            current_step_name = self.workflow['flow'][0]['step']
            steps_executed = 0
            
            while current_step_name and current_step_name != "finish":
                # 查找当前步骤
                current_step = None
                for step in self.workflow['flow']:
                    if step['step'] == current_step_name:
                        current_step = step
                        break
                
                if not current_step:
                    logger.error(f"找不到步骤: {current_step_name}")
                    result["errors"].append(f"找不到步骤: {current_step_name}")
                    break
                
                # 执行步骤
                logger.info(f"开始执行步骤: {current_step_name}")
                step_result = await self._execute_step(current_step)
                steps_executed += 1
                
                if not step_result["success"]:
                    logger.error(f"步骤执行失败: {current_step_name}, 错误: {step_result.get('error')}")
                    result["errors"].append(f"步骤 {current_step_name} 执行失败: {step_result.get('error')}")
                    break
                
                # 更新下一步骤
                current_step_name = step_result.get("next_step")
            
            # 更新结果
            result["steps_completed"] = steps_executed
            result["data_extracted"] = len(self.output_data)
            result["success"] = steps_executed > 0 and not result["errors"]
            result["execution_time"] = str(datetime.now() - start_time)
            
            # 保存输出数据
            if self.output_data:
                output_dir = self.workflow.get('output_directory', 'output')
                os.makedirs(output_dir, exist_ok=True)
                output_file = os.path.join(output_dir, f"{self.workflow['workflow_name'].lower().replace(' ', '_')}.json")
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(self.output_data, f, ensure_ascii=False, indent=2)
                
                logger.info(f"已保存输出数据到: {output_file}")
                result["output_file"] = output_file
            
        except Exception as e:
            logger.error(f"工作流执行出错: {e}", exc_info=True)
            result["errors"].append(f"执行错误: {str(e)}")
        
        finally:
            # 关闭浏览器
            await self._close_browser()
        
        return result
    
    async def _init_browser(self):
        """初始化浏览器"""
        logger.info("初始化浏览器")
        try:
            config = self.workflow.get('config', {})
            headless = config.get('headless', True)
            user_agent = config.get('user_agent')
            
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(headless=headless)
            
            browser_context_options = {}
            if user_agent:
                browser_context_options['user_agent'] = user_agent
            
            self.context = await self.browser.new_context(**browser_context_options)
            self.page = await self.context.new_page()
            
            # 设置页面超时
            timeout = config.get('timeout', 30000)
            self.page.set_default_timeout(timeout)
            
            logger.info(f"浏览器初始化完成，headless: {headless}, timeout: {timeout}ms")
            
        except Exception as e:
            logger.error(f"初始化浏览器失败: {e}", exc_info=True)
            raise
    
    async def _close_browser(self):
        """关闭浏览器"""
        logger.info("关闭浏览器")
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
        except Exception as e:
            logger.error(f"关闭浏览器时出错: {e}")
    
    async def _execute_step(self, step: Dict) -> Dict[str, Any]:
        """
        执行工作流步骤
        
        参数:
            step: 步骤定义
            
        返回:
            执行结果
        """
        result = {
            "success": False,
            "step": step['step'],
            "next_step": step.get('next')
        }
        
        try:
            # 检查条件
            if 'condition' in step:
                condition = step['condition']
                # 替换条件中的变量
                condition_value = self._resolve_variables(condition)
                if not condition_value:
                    logger.info(f"步骤条件不满足，跳过: {step['step']}")
                    result["success"] = True
                    return result
            
            # 处理循环
            if 'for_each' in step:
                items_key = step['for_each']
                items = self._resolve_variables(items_key)
                
                if not items or not isinstance(items, list):
                    logger.warning(f"for_each项目不存在或不是列表: {items_key}")
                    result["error"] = f"for_each项目无效: {items_key}"
                    return result
                
                logger.info(f"处理循环: 找到 {len(items)} 个项目")
                
                # 执行每个项目的操作
                for idx, item in enumerate(items):
                    logger.info(f"处理for_each项目 {idx+1}/{len(items)}")
                    # 设置当前项目在状态中
                    self.current_state["current_item"] = item
                    
                    # 输出调试信息
                    if isinstance(item, dict):
                        logger.info(f"当前项目属性: {', '.join(item.keys())}")
                    
                    # 执行项目的操作
                    for action in step['actions']:
                        action_result = await self._execute_action(action)
                        if not action_result["success"]:
                            logger.error(f"执行for_each项目操作失败: {action_result.get('error')}")
                            result["error"] = f"for_each项目操作失败: {action_result.get('error')}"
                            return result
                
                result["success"] = True
                return result
            
            # 执行普通操作
            for action in step['actions']:
                action_result = await self._execute_action(action)
                if not action_result["success"]:
                    logger.error(f"执行操作失败: {action_result.get('error')}")
                    result["error"] = f"操作失败: {action_result.get('error')}"
                    return result
            
            # 处理分页
            if 'pagination' in step:
                pagination = step['pagination']
                max_pages = pagination.get('max_pages', 1)
                current_page = 1
                
                while current_page < max_pages:
                    # 尝试找到下一页按钮
                    next_button_selector = pagination.get('next_button')
                    if not next_button_selector:
                        break
                    
                    # 检查下一页按钮是否存在
                    next_button = await self.page.query_selector(next_button_selector)
                    if not next_button:
                        logger.info("找不到下一页按钮，分页结束")
                        break
                    
                    # 点击下一页
                    logger.info(f"点击下一页按钮，当前页: {current_page}")
                    await next_button.click()
                    await self.page.wait_for_load_state('networkidle')
                    
                    # 执行页面操作
                    for action in step['actions']:
                        action_result = await self._execute_action(action)
                        if not action_result["success"]:
                            logger.warning(f"分页操作失败: {action_result.get('error')}")
                            break
                    
                    current_page += 1
            
            result["success"] = True
            
        except Exception as e:
            logger.error(f"执行步骤出错: {e}", exc_info=True)
            result["error"] = str(e)
        
        return result
    
    async def _execute_action(self, action: Dict) -> Dict[str, Any]:
        """
        执行操作
        
        参数:
            action: 操作定义
            
        返回:
            执行结果
        """
        result = {
            "success": False,
            "action": action.get('action')
        }
        
        try:
            action_type = action.get('action')
            
            if not action_type:
                result["error"] = "操作类型未定义"
                return result
            
            # 打印调试信息
            logger.info(f"执行操作: {action_type}")
            
            # 根据操作类型执行不同的操作
            if action_type == "visit":
                # 访问URL
                url = self._resolve_variables(action.get('url'))
                logger.debug(f"解析的URL: {url}")
                
                if not url:
                    # 尝试从current_item中获取href
                    current_item = self.current_state.get("current_item", {})
                    if isinstance(current_item, dict) and 'href' in current_item:
                        url = current_item['href']
                        logger.info(f"从current_item中获取URL: {url}")
                
                if not url:
                    result["error"] = "URL未定义"
                    return result
                
                logger.info(f"访问URL: {url}")
                await self.page.goto(url)
                await self.page.wait_for_load_state('networkidle')
                
                result["success"] = True
                
            elif action_type == "extract":
                # 提取内容
                target = action.get('target')
                if not target:
                    result["error"] = "提取目标未定义"
                    return result
                
                # 根据目标类型进行不同的提取
                if target == "links":
                    # 提取链接
                    extract_result = await self._extract_links(action)
                    result.update(extract_result)
                    
                elif target == "content":
                    # 提取内容
                    extract_result = await self._extract_content(action)
                    result.update(extract_result)
                
                else:
                    result["error"] = f"未知的提取目标: {target}"
                
            elif action_type == "save":
                # 保存数据
                raw_data = action.get('data')
                logger.info(f"原始数据模板: {raw_data}")
                
                # 打印当前状态变量，帮助调试
                logger.info(f"当前状态变量: {list(self.current_state.keys())}")
                if 'article_data' in self.current_state:
                    logger.info(f"article_data内容: {self.current_state['article_data']}")
                
                data = self._resolve_variables(raw_data)
                logger.info(f"解析后的数据: {data}")
                
                if not data:
                    result["error"] = "保存数据为空"
                    return result
                
                # 是否需要保存为文件
                format_type = action.get('format')
                if format_type:
                    raw_filename = action.get('filename', f"output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format_type}")
                    logger.info(f"原始文件名: {raw_filename}")
                    
                    # 解析文件名中的变量
                    filename = self._resolve_variables(raw_filename)
                    logger.info(f"解析后的文件名: {filename}")
                    
                    # 如果文件名解析失败，尝试手动替换常见变量
                    if '${' in filename:
                        logger.warning(f"文件名中仍有未解析的变量: {filename}")
                        
                        # 尝试手动解析常见变量
                        if isinstance(data, dict):
                            for key, value in data.items():
                                if isinstance(value, str):
                                    var_pattern = f"${{article_data.{key}}}"
                                    if var_pattern in filename:
                                        filename = filename.replace(var_pattern, value)
                                        logger.info(f"手动替换变量 {var_pattern} 为 {value}")
                                        
                            # 替换其他常见变量
                            var_pattern = "${article_data.date}"
                            if var_pattern in filename:
                                current_date = datetime.now().strftime("%Y%m%d")
                                filename = filename.replace(var_pattern, current_date)
                                logger.info(f"替换日期变量为当前日期: {current_date}")
                    
                    # 获取输出目录
                    output_dir = self.workflow.get('config', {}).get('output_directory', 'output')
                    os.makedirs(output_dir, exist_ok=True)
                    
                    # 完整文件路径
                    file_path = os.path.join(output_dir, filename)
                    
                    # 根据格式类型保存
                    if format_type.lower() == 'markdown' or format_type.lower() == 'md':
                        # 构建Markdown内容
                        title = data.get('title', '无标题')
                        date = data.get('date', '无日期')
                        url = data.get('url', '')
                        content = data.get('content', '')
                        
                        md_content = f"# {title}\n\n"
                        md_content += f"日期: {date}\n\n"
                        md_content += f"URL: {url}\n\n"
                        md_content += f"{content}\n"
                        
                        # 保存到文件
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(md_content)
                        
                        logger.info(f"已保存Markdown文件: {file_path}")
                    else:
                        # 默认保存为JSON
                        with open(file_path, 'w', encoding='utf-8') as f:
                            json.dump(data, f, ensure_ascii=False, indent=2)
                        
                        logger.info(f"已保存数据文件: {file_path}")
                
                # 将数据添加到输出列表
                if isinstance(data, list):
                    self.output_data.extend(data)
                else:
                    self.output_data.append(data)
                
                logger.info(f"已保存数据，当前数据量: {len(self.output_data)}")
                result["success"] = True
                
            elif action_type == "click":
                # 点击元素
                selector = action.get('element')
                if not selector:
                    result["error"] = "点击元素未定义"
                    return result
                
                # 解析变量
                selector = self._resolve_variables(selector)
                
                logger.info(f"点击元素: {selector}")
                element = await self.page.query_selector(selector)
                if not element:
                    result["error"] = f"找不到点击元素: {selector}"
                    return result
                
                await element.click()
                await self.page.wait_for_load_state('networkidle')
                
                result["success"] = True
                
            elif action_type == "wait":
                # 等待
                timeout = action.get('timeout', 1000)
                logger.info(f"等待 {timeout} 毫秒")
                await asyncio.sleep(timeout / 1000)
                result["success"] = True
                
            elif action_type == "for_each":
                # 内部for_each
                items_key = action.get('items')
                if not items_key:
                    result["error"] = "for_each项目未定义"
                    return result
                
                items = self._resolve_variables(items_key)
                if not items or not isinstance(items, list):
                    result["error"] = f"for_each项目无效: {items_key}"
                    return result
                
                # 执行每个项目的操作
                for idx, item in enumerate(items):
                    logger.info(f"处理嵌套for_each项目 {idx+1}/{len(items)}")
                    # 设置当前项目在状态中
                    self.current_state["current_item"] = item
                    
                    # 执行项目的操作
                    for sub_action in action.get('actions', []):
                        action_result = await self._execute_action(sub_action)
                        if not action_result["success"]:
                            logger.error(f"执行嵌套for_each项目操作失败: {action_result.get('error')}")
                            return action_result
                
                result["success"] = True
                
            else:
                result["error"] = f"未知的操作类型: {action_type}"
                
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"执行操作出错: {e}")
            logger.error(f"错误堆栈: {error_trace}")
            result["error"] = str(e)
        
        return result
    
    async def _extract_links(self, action: Dict) -> Dict[str, Any]:
        """
        提取链接
        
        参数:
            action: 提取操作定义
            
        返回:
            提取结果
        """
        result = {
            "success": False
        }
        
        try:
            element_def = action.get('element', {})
            if not element_def:
                result["error"] = "链接元素定义未提供"
                return result
            
            # 获取样例选择器
            sample_selector = element_def.get('sample')
            if not sample_selector:
                result["error"] = "样例选择器未提供"
                return result
            
            # 是否需要泛化
            should_generalize = element_def.get('generalize', True)
            
            # 获取HTML内容
            html_content = await self.page.content()
            
            # 如果需要泛化，使用泛化器
            if should_generalize:
                logger.info(f"使用泛化器处理样例选择器: {sample_selector}")
                generalize_result = self.element_generalizer.generalize_selector(html_content, sample_selector)
                
                if generalize_result["success"]:
                    # 使用泛化后的选择器
                    selector = generalize_result["generalized"]
                    logger.info(f"成功泛化选择器: {sample_selector} -> {selector}")
                else:
                    # 泛化失败，使用原始选择器
                    selector = sample_selector
                    logger.warning(f"选择器泛化失败，使用原始选择器: {selector}")
            else:
                # 不需要泛化，直接使用原始选择器
                selector = sample_selector
            
            # 使用选择器查找元素
            is_xpath = self.element_generalizer._is_xpath(selector)
            
            items = []
            base_url = self.page.url
            
            if is_xpath:
                # 直接使用Playwright的locator API
                elements = await self.page.locator(selector).all()
                for element in elements:
                    href = await element.get_attribute('href')
                    text = await element.text_content()
                    
                    if href:
                        # 构建完整URL
                        from urllib.parse import urljoin
                        full_url = urljoin(base_url, href)
                        
                        items.append({
                            'href': full_url,
                            'text': text.strip() if text else ''
                        })
            else:
                # 使用CSS选择器
                elements = await self.page.query_selector_all(selector)
                for element in elements:
                    href = await element.get_attribute('href')
                    text = await element.text_content()
                    
                    if href:
                        # 构建完整URL
                        from urllib.parse import urljoin
                        full_url = urljoin(base_url, href)
                        
                        items.append({
                            'href': full_url,
                            'text': text.strip() if text else ''
                        })
            
            # 保存提取的URLs
            output_name = action.get('output')
            if output_name:
                self.current_state[output_name] = items
                logger.info(f"已提取 {len(items)} 个链接，保存到状态变量: {output_name}")
            
            result["success"] = True
            result["extracted_count"] = len(items)
            
        except Exception as e:
            logger.error(f"提取链接出错: {e}", exc_info=True)
            result["error"] = str(e)
        
        return result
    
    async def _extract_content(self, action: Dict) -> Dict[str, Any]:
        """提取内容"""
        result = {"success": False}
        
        try:
            # 获取元素定义
            elements_def = action.get('elements', [])
            
            # 打印调试信息
            logger.info(f"提取内容开始, elements类型: {type(elements_def)}")
            logger.info(f"元素定义: {elements_def}")
            
            # 初始化提取数据
            extracted_data = {}
            
            # 处理不同格式的元素定义（兼容列表和字典两种格式）
            if isinstance(elements_def, list):
                # 处理列表格式
                for element_def in elements_def:
                    if not isinstance(element_def, dict):
                        logger.warning(f"元素定义不完整: {element_def}，跳过")
                        continue
                    
                    element_name = element_def.get('name')
                    sample_selector = element_def.get('sample')
                    
                    if not element_name or not sample_selector:
                        logger.warning(f"元素定义缺少name或sample: {element_def}")
                        continue
                    
                    # 是否需要泛化
                    should_generalize = element_def.get('generalize', False)
                    
                    # 提取元素内容
                    content = await self._extract_single_element(sample_selector, should_generalize)
                    extracted_data[element_name] = content
            
            elif isinstance(elements_def, dict):
                # 处理字典格式
                for name, definition in elements_def.items():
                    if not isinstance(definition, dict):
                        logger.warning(f"元素 {name} 定义不完整，跳过")
                        continue
                    
                    selector = definition.get('selector') or definition.get('sample')
                    selector_type = definition.get('type', 'css')
                    attribute = definition.get('attribute', 'text')
                    
                    if not selector:
                        logger.warning(f"元素 {name} 没有定义选择器，跳过")
                        continue
                    
                    # 提取元素内容
                    content = await self._extract_with_selector(name, selector, selector_type, attribute)
                    extracted_data[name] = content
            else:
                logger.error(f"不支持的elements类型: {type(elements_def)}")
                result["error"] = f"不支持的elements类型: {type(elements_def)}"
                return result
            
            # 添加页面URL和时间戳
            extracted_data['url'] = self.page.url
            extracted_data['timestamp'] = datetime.now().isoformat()
            
            # 将提取的数据保存到指定的输出变量
            output_var = action.get('output', 'extracted_data')
            self.current_state[output_var] = extracted_data
            
            logger.info(f"提取内容完成，结果: {extracted_data}")
            
            result["success"] = True
            result["data"] = extracted_data
        
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            logger.error(f"提取内容时出错: {str(e)}")
            logger.error(f"错误堆栈: {error_trace}")
            
            # 打印当前action结构，帮助调试
            import pprint
            logger.error(f"当前action结构:")
            logger.error(pprint.pformat(action))
            
            result["error"] = f"提取内容时出错: {str(e)}"
        
        return result
    
    async def _extract_single_element(self, selector: str, should_generalize: bool = False) -> str:
        """
        提取单个元素的内容
        
        参数:
            selector: 选择器
            should_generalize: 是否需要泛化
            
        返回:
            元素内容
        """
        try:
            # 获取HTML内容
            html_content = await self.page.content()
            
            # 如果需要泛化，使用泛化器
            if should_generalize:
                logger.info(f"使用泛化器处理选择器: {selector}")
                generalize_result = self.element_generalizer.generalize_selector(html_content, selector)
                
                if generalize_result["success"]:
                    # 使用泛化后的选择器
                    selector = generalize_result["generalized"]
                    logger.info(f"成功泛化选择器: {selector}")
                else:
                    # 泛化失败，使用原始选择器
                    logger.warning(f"选择器泛化失败，使用原始选择器: {selector}")
            
            # 使用选择器查找元素
            is_xpath = self.element_generalizer._is_xpath(selector)
            content = ""
            
            if is_xpath:
                # 使用XPath选择器
                element = await self.page.query_selector(f"xpath={selector}")
            else:
                # 使用CSS选择器
                element = await self.page.query_selector(selector)
                
            if element:
                content = await element.text_content()
                if content:
                    content = content.strip()
                    logger.info(f"成功提取内容: {content[:50]}...")
                else:
                    logger.warning(f"元素内容为空: {selector}")
            else:
                logger.warning(f"未找到匹配元素: {selector}")
            
            return content
        
        except Exception as e:
            logger.error(f"提取单个元素时出错: {e}")
            return ""
    
    async def _extract_with_selector(self, name: str, selector: str, selector_type: str, attribute: str) -> str:
        """
        根据选择器类型和属性提取元素内容
        
        参数:
            name: 元素名称
            selector: 选择器
            selector_type: 选择器类型 (xpath/css)
            attribute: 要提取的属性
            
        返回:
            提取的内容
        """
        try:
            logger.info(f"提取元素 {name}，选择器: {selector}，类型: {selector_type}")
            
            content = None
            if selector_type.lower() == 'xpath':
                # 使用XPath
                try:
                    # 使用JavaScript执行XPath查询
                    js_script = f"""() => {{
                        try {{
                            var element = document.evaluate("{selector}", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                            if (element) {{
                                if ('{attribute}' === 'text') {{
                                    return element.textContent.trim();
                                }} else if ('{attribute}' === 'html') {{
                                    return element.innerHTML.trim();
                                }} else if ('{attribute}' === 'outerhtml') {{
                                    return element.outerHTML.trim();
                                }} else {{
                                    return element.getAttribute('{attribute}');
                                }}
                            }}
                            return null;
                        }} catch(e) {{
                            console.error('XPath执行失败:', e);
                            return null;
                        }}
                    }}"""
                    content = await self.page.evaluate(js_script)
                except Exception as js_error:
                    logger.error(f"JavaScript执行XPath出错: {js_error}")
                    
                    # 回退到直接使用Playwright的XPath
                    element = await self.page.query_selector(f"xpath={selector}")
                    if element:
                        if attribute.lower() == 'text':
                            content = await element.text_content()
                        elif attribute.lower() == 'html':
                            content = await element.inner_html()
                        elif attribute.lower() == 'outerhtml':
                            content = await element.outer_html()
                        else:
                            content = await element.get_attribute(attribute)
            else:
                # 使用CSS选择器
                element = await self.page.query_selector(selector)
                if element:
                    if attribute.lower() == 'text':
                        content = await element.text_content()
                    elif attribute.lower() == 'html':
                        content = await element.inner_html()
                    elif attribute.lower() == 'outerhtml':
                        content = await element.outer_html()
                    else:
                        content = await element.get_attribute(attribute)
            
            if content:
                if isinstance(content, str):
                    content = content.strip()
                logger.info(f"成功提取元素 {name}: {str(content)[:50]}...")
            else:
                logger.warning(f"没有找到元素 {name}，选择器: {selector}")
            
            return content
            
        except Exception as e:
            logger.error(f"使用选择器提取 {name} 时出错: {str(e)}")
            return None
    
    def _resolve_variables(self, value):
        """
        解析变量引用，将${var}替换为状态中的值
        
        参数:
            value: 可能包含变量引用的值
            
        返回:
            解析后的值
        """
        if not value:
            return value
        
        logger.debug(f"解析变量: {value}, 类型: {type(value)}")
        
        if isinstance(value, str):
            # 如果是形如${var}的完整变量引用
            if value.startswith('${') and value.endswith('}'):
                var_path = value[2:-1]
                logger.debug(f"解析完整变量引用: {var_path}")
                
                # 处理嵌套变量, 如 article_data.title
                if '.' in var_path:
                    parts = var_path.split('.')
                    root_var = parts[0]
                    root_value = self.current_state.get(root_var)
                    
                    if not root_value or not isinstance(root_value, dict):
                        logger.warning(f"变量 {root_var} 不存在或不是字典: {root_value}")
                        return value
                    
                    current = root_value
                    for part in parts[1:]:
                        if isinstance(current, dict) and part in current:
                            current = current[part]
                        else:
                            logger.warning(f"无法解析嵌套变量 {var_path} 的部分 {part}")
                            return value
                    
                    logger.debug(f"成功解析嵌套变量 {var_path} 为 {current}")
                    return current
                else:
                    # 简单变量
                    return self.current_state.get(var_path)
            
            # 替换字符串中的所有${var}变量引用
            import re
            def replace_var(match):
                var_path = match.group(1)
                logger.debug(f"替换内联变量: {var_path}")
                
                # 处理嵌套变量
                if '.' in var_path:
                    parts = var_path.split('.')
                    root_var = parts[0]
                    root_value = self.current_state.get(root_var)
                    
                    if not root_value or not isinstance(root_value, dict):
                        logger.warning(f"变量 {root_var} 不存在或不是字典: {root_value}")
                        return match.group(0)
                    
                    try:
                        current = root_value
                        for part in parts[1:]:
                            if isinstance(current, dict) and part in current:
                                current = current[part]
                            else:
                                logger.warning(f"无法解析嵌套变量 {var_path} 的部分 {part}")
                                return match.group(0)
                        
                        logger.debug(f"成功解析嵌套变量 {var_path} 为 {current}")
                        return str(current) if current is not None else match.group(0)
                    except Exception as e:
                        logger.error(f"解析嵌套变量 {var_path} 出错: {e}")
                        return match.group(0)
                else:
                    # 简单变量
                    var_value = self.current_state.get(var_path)
                    return str(var_value) if var_value is not None else match.group(0)
            
            return re.sub(r'\${([^}]+)}', replace_var, value)
        
        elif isinstance(value, dict):
            # 递归处理字典
            return {k: self._resolve_variables(v) for k, v in value.items()}
        
        elif isinstance(value, list):
            # 递归处理列表
            return [self._resolve_variables(item) for item in value]
        
        # 其他类型直接返回
        return value
        
async def main():
    """主函数"""
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python workflow_engine.py <工作流文件路径>")
        return
    
    workflow_path = sys.argv[1]
    if not os.path.exists(workflow_path):
        print(f"工作流文件不存在: {workflow_path}")
        return
    
    engine = WorkflowEngine(workflow_path)
    result = await engine.run()
    
    print("\n工作流执行结果:")
    print(f"成功: {result['success']}")
    print(f"完成步骤: {result['steps_completed']}/{result['total_steps']}")
    print(f"提取数据量: {result['data_extracted']}")
    
    if result.get('output_file'):
        print(f"输出文件: {result['output_file']}")
    
    if result['errors']:
        print("\n错误:")
        for error in result['errors']:
            print(f"- {error}")

if __name__ == "__main__":
    asyncio.run(main()) 