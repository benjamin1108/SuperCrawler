#!/usr/bin/env python3
"""
元素泛化器 - 从单个样例元素推断出可以匹配所有相似元素的选择器
"""
import os
import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from bs4 import BeautifulSoup
import lxml.etree
import lxml.html

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ElementGeneralizer")

class ElementGeneralizer:
    """从单个元素样例推断通用选择器的工具"""
    
    def __init__(self, logs_dir: str = None):
        """
        初始化元素泛化器
        
        参数:
            logs_dir: 日志文件目录，默认为当前目录
        """
        # 配置日志目录
        self.logs_dir = logs_dir if logs_dir else "."
        if not os.path.exists(self.logs_dir):
            os.makedirs(self.logs_dir)
            
        # 配置文件日志处理器
        log_path = os.path.join(self.logs_dir, "element_generalizer.log")
        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(file_handler)
        
        logger.info("初始化元素泛化器")
    
    def generalize_selector(self, html_content: str, sample_selector: str) -> Dict[str, Any]:
        """
        从样例选择器生成通用选择器
        
        参数:
            html_content: HTML内容
            sample_selector: 样例选择器(CSS或XPath)
            
        返回:
            包含泛化选择器的字典
        """
        logger.info(f"开始从样例选择器泛化: {sample_selector}")
        
        try:
            # 判断选择器类型
            is_xpath = self._is_xpath(sample_selector)
            
            if is_xpath:
                return self._generalize_xpath(html_content, sample_selector)
            else:
                return self._generalize_css(html_content, sample_selector)
                
        except Exception as e:
            logger.error(f"选择器泛化过程出错: {e}", exc_info=True)
            # 返回原始选择器作为备选
            return {
                "original": sample_selector,
                "generalized": sample_selector,
                "is_xpath": is_xpath,
                "success": False,
                "error": str(e)
            }
    
    def _is_xpath(self, selector: str) -> bool:
        """判断是否为XPath选择器"""
        # 简单判断是否为XPath
        return selector.startswith('/') or selector.startswith('(') or selector.startswith('./') or selector.startswith('//') 
    
    def _generalize_xpath(self, html_content: str, xpath: str) -> Dict[str, Any]:
        """
        从样例XPath生成通用XPath
        
        参数:
            html_content: HTML内容
            xpath: 样例XPath
            
        返回:
            包含泛化XPath的字典
        """
        logger.info(f"开始泛化XPath: {xpath}")
        result = {
            "original": xpath,
            "is_xpath": True,
            "success": False
        }
        
        try:
            # 解析HTML
            parser = lxml.etree.HTMLParser()
            dom = lxml.etree.fromstring(html_content, parser)
            
            # 检查原始XPath是否有效
            original_elements = dom.xpath(xpath)
            if not original_elements:
                logger.warning(f"原始XPath未能找到元素: {xpath}")
                result["error"] = "原始XPath未能找到元素"
                return result
            
            # 开始处理有效的XPath
            original_element = original_elements[0]
            
            # 尝试不同的泛化策略
            generalized_xpaths = []
            
            # 1. 尝试生成基于标签和类的XPath
            if hasattr(original_element, 'tag') and hasattr(original_element, 'attrib'):
                tag = original_element.tag
                class_attr = original_element.attrib.get('class', '')
                
                if class_attr:
                    # 从类属性中提取主要类名
                    class_names = class_attr.split()
                    for class_name in class_names:
                        # 尝试使用单个类名
                        gen_xpath = f"//{tag}[contains(@class, '{class_name}')]"
                        elements = dom.xpath(gen_xpath)
                        if elements and len(elements) > 1:  # 找到多个元素
                            generalized_xpaths.append({
                                "xpath": gen_xpath,
                                "elements_count": len(elements),
                                "confidence": 0.9
                            })
            
            # 2. 尝试基于父元素和标签类型的XPath
            if hasattr(original_element, 'getparent') and original_element.getparent() is not None:
                parent = original_element.getparent()
                if hasattr(parent, 'tag'):
                    parent_tag = parent.tag
                    gen_xpath = f"//{parent_tag}//{original_element.tag}"
                    elements = dom.xpath(gen_xpath)
                    if elements and len(elements) > 1:
                        generalized_xpaths.append({
                            "xpath": gen_xpath,
                            "elements_count": len(elements),
                            "confidence": 0.7
                        })
            
            # 3. 处理绝对XPath，转换为相对XPath
            if xpath.startswith('/html/'):
                parts = xpath.split('/')
                last_meaningful_index = 0
                
                # 找到最后一个有意义的部分索引
                for i, part in enumerate(parts):
                    if part and '[' in part:  # 带有索引的部分通常更具体
                        last_meaningful_index = i
                
                # 生成一个更通用的相对XPath
                if last_meaningful_index > 0:
                    relative_parts = parts[last_meaningful_index:]
                    # 移除索引，如[1]、[2]等
                    cleaned_parts = []
                    for part in relative_parts:
                        if part:
                            # 移除索引
                            index_match = re.match(r'([^[]+)(\[\d+\])?', part)
                            if index_match:
                                cleaned_parts.append(index_match.group(1))
                            else:
                                cleaned_parts.append(part)
                    
                    gen_xpath = '//' + '/'.join(filter(None, cleaned_parts))
                    elements = dom.xpath(gen_xpath)
                    if elements and len(elements) > 1:
                        generalized_xpaths.append({
                            "xpath": gen_xpath,
                            "elements_count": len(elements),
                            "confidence": 0.8
                        })
            
            # 4. 处理包含id的情况，查找类似的元素
            id_pattern = re.compile(r'@id=[\'"]([^\'"]+)[\'"]')
            id_match = id_pattern.search(xpath)
            if id_match:
                id_value = id_match.group(1)
                # 查找id的模式，例如item-1, item-2
                match = re.match(r'(.+?)[-_](\d+)$', id_value)
                if match:
                    prefix = match.group(1)
                    gen_xpath = f"//*[starts-with(@id, '{prefix}')]"
                    elements = dom.xpath(gen_xpath)
                    if elements and len(elements) > 1:
                        generalized_xpaths.append({
                            "xpath": gen_xpath,
                            "elements_count": len(elements),
                            "confidence": 0.85
                        })
            
            # 选择最佳泛化XPath
            if generalized_xpaths:
                # 排序：首先按元素数量(较多优先)，然后按置信度(较高优先)
                generalized_xpaths.sort(key=lambda x: (x["elements_count"], x["confidence"]), reverse=True)
                best_xpath = generalized_xpaths[0]["xpath"]
                
                result["generalized"] = best_xpath
                result["alternatives"] = generalized_xpaths
                result["success"] = True
                result["elements_count"] = generalized_xpaths[0]["elements_count"]
                logger.info(f"成功泛化XPath: {xpath} -> {best_xpath}")
            else:
                # 如果没有找到合适的泛化XPath，返回原始XPath
                result["generalized"] = xpath
                result["success"] = False
                result["error"] = "未能找到合适的泛化XPath"
                logger.warning(f"未能泛化XPath: {xpath}")
            
        except Exception as e:
            logger.error(f"XPath泛化过程出错: {e}", exc_info=True)
            result["error"] = str(e)
            result["generalized"] = xpath  # 回退到原始XPath
        
        return result
    
    def _generalize_css(self, html_content: str, css_selector: str) -> Dict[str, Any]:
        """
        从样例CSS选择器生成通用CSS选择器
        
        参数:
            html_content: HTML内容
            css_selector: 样例CSS选择器
            
        返回:
            包含泛化CSS选择器的字典
        """
        logger.info(f"开始泛化CSS选择器: {css_selector}")
        result = {
            "original": css_selector,
            "is_xpath": False,
            "success": False
        }
        
        try:
            # 解析HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 检查原始选择器是否有效
            original_elements = soup.select(css_selector)
            if not original_elements:
                logger.warning(f"原始CSS选择器未能找到元素: {css_selector}")
                result["error"] = "原始CSS选择器未能找到元素"
                return result
            
            # 获取第一个匹配元素
            original_element = original_elements[0]
            
            # 尝试不同的泛化策略
            generalized_selectors = []
            
            # 1. 尝试基于标签和类生成选择器
            if hasattr(original_element, 'name'):
                tag_name = original_element.name
                
                # 如果有类属性
                if original_element.has_attr('class'):
                    class_names = original_element['class']
                    
                    # 尝试使用单个类名
                    for class_name in class_names:
                        gen_selector = f"{tag_name}.{class_name}"
                        elements = soup.select(gen_selector)
                        if elements and len(elements) > 1:
                            generalized_selectors.append({
                                "selector": gen_selector,
                                "elements_count": len(elements),
                                "confidence": 0.9
                            })
                    
                    # 尝试只使用类名(不含标签)
                    for class_name in class_names:
                        gen_selector = f".{class_name}"
                        elements = soup.select(gen_selector)
                        if elements and len(elements) > 1:
                            generalized_selectors.append({
                                "selector": gen_selector,
                                "elements_count": len(elements),
                                "confidence": 0.8
                            })
                
                # 尝试只使用标签
                gen_selector = tag_name
                elements = soup.select(gen_selector)
                if elements and len(elements) > 1:
                    generalized_selectors.append({
                        "selector": gen_selector,
                        "elements_count": len(elements),
                        "confidence": 0.6
                    })
            
            # 2. 尝试提取属性选择器部分并泛化
            attr_pattern = re.compile(r'\[([^\]]+)\]')
            attr_matches = attr_pattern.findall(css_selector)
            if attr_matches:
                for attr_expr in attr_matches:
                    # 处理id属性
                    if attr_expr.startswith('id=') or attr_expr.startswith('id^=') or attr_expr.startswith('id*='):
                        parts = attr_expr.split('=', 1)
                        if len(parts) == 2:
                            attr_name = parts[0]
                            attr_value = parts[1].strip('"\'')
                            
                            # 检查是否是模式化的ID，如item-1, item-2等
                            id_pattern = re.compile(r'(.+?)[-_](\d+)$')
                            id_match = id_pattern.match(attr_value)
                            if id_match:
                                prefix = id_match.group(1)
                                gen_selector = f"[{attr_name}^=\"{prefix}\"]"
                                elements = soup.select(gen_selector)
                                if elements and len(elements) > 1:
                                    generalized_selectors.append({
                                        "selector": gen_selector,
                                        "elements_count": len(elements),
                                        "confidence": 0.85
                                    })
            
            # 3. 处理嵌套选择器，尝试提取关键部分
            if ' > ' in css_selector or ' ' in css_selector:
                parts = re.split(r'\s+>\s+|\s+', css_selector)
                if parts:
                    # 试图保留最后一个有意义的部分
                    last_part = parts[-1]
                    
                    # 如果最后一部分包含类或ID
                    if '.' in last_part or '#' in last_part or '[' in last_part:
                        gen_selector = last_part
                        elements = soup.select(gen_selector)
                        if elements and len(elements) > 1:
                            generalized_selectors.append({
                                "selector": gen_selector,
                                "elements_count": len(elements),
                                "confidence": 0.75
                            })
            
            # 4. 处理伪类和伪元素
            pseudo_pattern = re.compile(r':([\w-]+)')
            pseudo_matches = pseudo_pattern.findall(css_selector)
            if pseudo_matches:
                # 移除所有伪类和伪元素
                clean_selector = pseudo_pattern.sub('', css_selector)
                if clean_selector != css_selector:
                    elements = soup.select(clean_selector)
                    if elements and len(elements) > 1:
                        generalized_selectors.append({
                            "selector": clean_selector,
                            "elements_count": len(elements),
                            "confidence": 0.7
                        })
            
            # 选择最佳泛化选择器
            if generalized_selectors:
                # 排序：首先按元素数量(较多优先)，然后按置信度(较高优先)
                generalized_selectors.sort(key=lambda x: (x["elements_count"], x["confidence"]), reverse=True)
                best_selector = generalized_selectors[0]["selector"]
                
                result["generalized"] = best_selector
                result["alternatives"] = generalized_selectors
                result["success"] = True
                result["elements_count"] = generalized_selectors[0]["elements_count"]
                logger.info(f"成功泛化CSS选择器: {css_selector} -> {best_selector}")
            else:
                # 如果没有找到合适的泛化选择器，返回原始选择器
                result["generalized"] = css_selector
                result["success"] = False
                result["error"] = "未能找到合适的泛化CSS选择器"
                logger.warning(f"未能泛化CSS选择器: {css_selector}")
        
        except Exception as e:
            logger.error(f"CSS选择器泛化过程出错: {e}", exc_info=True)
            result["error"] = str(e)
            result["generalized"] = css_selector  # 回退到原始选择器
        
        return result
    
    def analyze_element(self, html_content: str, selector: str) -> Dict[str, Any]:
        """
        分析元素特征以辅助泛化
        
        参数:
            html_content: HTML内容
            selector: 选择器(CSS或XPath)
            
        返回:
            元素特征信息
        """
        logger.info(f"开始分析元素特征: {selector}")
        result = {
            "selector": selector,
            "success": False
        }
        
        try:
            # 判断选择器类型
            is_xpath = self._is_xpath(selector)
            
            # 解析HTML
            if is_xpath:
                parser = lxml.etree.HTMLParser()
                dom = lxml.etree.fromstring(html_content, parser)
                elements = dom.xpath(selector)
                
                if not elements:
                    logger.warning(f"XPath未能找到元素: {selector}")
                    result["error"] = "选择器未能找到元素"
                    return result
                
                element = elements[0]
                
                # 获取元素特征
                tag = element.tag
                attributes = dict(element.attrib)
                parent_tag = element.getparent().tag if element.getparent() is not None else None
                siblings_count = len(element.getparent()) if element.getparent() is not None else 0
                
                result["element_info"] = {
                    "tag": tag,
                    "attributes": attributes,
                    "parent_tag": parent_tag,
                    "siblings_count": siblings_count
                }
                result["success"] = True
                
            else:  # CSS选择器
                soup = BeautifulSoup(html_content, 'html.parser')
                elements = soup.select(selector)
                
                if not elements:
                    logger.warning(f"CSS选择器未能找到元素: {selector}")
                    result["error"] = "选择器未能找到元素"
                    return result
                
                element = elements[0]
                
                # 获取元素特征
                tag = element.name
                attributes = element.attrs
                parent_tag = element.parent.name if element.parent else None
                siblings_count = len(list(element.parent.children)) if element.parent else 0
                
                result["element_info"] = {
                    "tag": tag,
                    "attributes": attributes,
                    "parent_tag": parent_tag,
                    "siblings_count": siblings_count
                }
                result["success"] = True
        
        except Exception as e:
            logger.error(f"元素分析过程出错: {e}", exc_info=True)
            result["error"] = str(e)
        
        return result
    
    def find_common_pattern(self, elements_info: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        从多个元素信息中找出共同模式
        
        参数:
            elements_info: 元素信息列表
            
        返回:
            共同模式信息
        """
        logger.info(f"开始查找共同模式，分析 {len(elements_info)} 个元素")
        result = {
            "success": False
        }
        
        if not elements_info:
            result["error"] = "无元素信息可分析"
            return result
        
        try:
            # 提取标签统计
            tags = {}
            attributes = {}
            parent_tags = {}
            
            for info in elements_info:
                element_info = info.get("element_info", {})
                
                # 统计标签
                tag = element_info.get("tag")
                if tag:
                    tags[tag] = tags.get(tag, 0) + 1
                
                # 统计属性
                attrs = element_info.get("attributes", {})
                for attr_name, attr_value in attrs.items():
                    if attr_name not in attributes:
                        attributes[attr_name] = {}
                    
                    # 对于class属性，分别处理每个类名
                    if attr_name == "class" and isinstance(attr_value, list):
                        for class_name in attr_value:
                            key = f"class:{class_name}"
                            attributes.setdefault(key, 0)
                            attributes[key] += 1
                    else:
                        attributes.setdefault(attr_name, 0)
                        attributes[attr_name] += 1
                
                # 统计父标签
                parent_tag = element_info.get("parent_tag")
                if parent_tag:
                    parent_tags[parent_tag] = parent_tags.get(parent_tag, 0) + 1
            
            # 查找最常见的标签
            common_tag = max(tags.items(), key=lambda x: x[1])[0] if tags else None
            
            # 查找最常见的属性
            common_attributes = []
            for attr, count in attributes.items():
                if count / len(elements_info) >= 0.8:  # 80%的元素具有此属性
                    common_attributes.append(attr)
            
            # 查找最常见的父标签
            common_parent_tag = max(parent_tags.items(), key=lambda x: x[1])[0] if parent_tags else None
            
            # 构建结果
            result["common_pattern"] = {
                "tag": common_tag,
                "attributes": common_attributes,
                "parent_tag": common_parent_tag
            }
            result["success"] = True
            
        except Exception as e:
            logger.error(f"查找共同模式过程出错: {e}", exc_info=True)
            result["error"] = str(e)
        
        return result 