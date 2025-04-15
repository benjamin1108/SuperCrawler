import os
import json
import yaml
from pathlib import Path
import logging
from typing import List, Dict, Any, Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("crawler.log", encoding='utf-8')
    ]
)
logger = logging.getLogger("WorkflowManager")

class WorkflowManager:
    """
    工作流管理器，负责加载、验证和管理爬虫工作流
    """
    def __init__(self, workflows_dir: str = "workflows"):
        self.workflows_dir = workflows_dir
        self.workflows = {}
        self.schemas = {}
        if not Path(workflows_dir).exists():
            logger.warning(f"工作流目录 {workflows_dir} 不存在，正在创建...")
            Path(workflows_dir).mkdir(parents=True, exist_ok=True)
    
    def load_workflows(self) -> Dict[str, Dict]:
        """加载所有工作流配置"""
        logger.info(f"开始加载工作流配置，目录: {self.workflows_dir}")
        if not os.path.exists(self.workflows_dir):
            logger.error(f"工作流目录不存在: {self.workflows_dir}")
            return {}
        
        workflow_files = [f for f in os.listdir(self.workflows_dir) 
                          if f.endswith('.yaml') or f.endswith('.yml')]
        
        logger.info(f"找到 {len(workflow_files)} 个工作流配置文件")
        
        for wf_file in workflow_files:
            try:
                workflow_path = os.path.join(self.workflows_dir, wf_file)
                with open(workflow_path, 'r', encoding='utf-8') as f:
                    workflow_config = yaml.safe_load(f)
                
                # 验证工作流配置
                if not self._validate_workflow(workflow_config):
                    logger.warning(f"工作流配置 {wf_file} 无效，已跳过")
                    continue
                
                workflow_id = workflow_config.get('id', os.path.splitext(wf_file)[0])
                self.workflows[workflow_id] = workflow_config
                logger.info(f"已加载工作流: {workflow_id}")
            except Exception as e:
                logger.error(f"加载工作流 {wf_file} 时出错: {e}")
        
        logger.info(f"成功加载 {len(self.workflows)} 个工作流")
        return self.workflows
    
    def load_schemas(self) -> Dict[str, Dict]:
        """加载所有提取模式"""
        logger.info("开始加载提取模式")
        schemas_dir = os.path.join(self.workflows_dir, "schemas")
        
        if not os.path.exists(schemas_dir):
            logger.error(f"提取模式目录不存在: {schemas_dir}")
            return {}
        
        schema_files = [f for f in os.listdir(schemas_dir) 
                        if f.endswith('.yaml') or f.endswith('.yml') or f.endswith('.json')]
        
        logger.info(f"找到 {len(schema_files)} 个提取模式文件")
        
        for schema_file in schema_files:
            try:
                schema_path = os.path.join(schemas_dir, schema_file)
                if schema_file.endswith('.json'):
                    with open(schema_path, 'r', encoding='utf-8') as f:
                        schema = json.load(f)
                else:
                    with open(schema_path, 'r', encoding='utf-8') as f:
                        schema = yaml.safe_load(f)
                
                schema_id = schema.get('id', os.path.splitext(schema_file)[0])
                self.schemas[schema_id] = schema
                logger.info(f"已加载提取模式: {schema_id}")
            except Exception as e:
                logger.error(f"加载提取模式 {schema_file} 时出错: {e}")
        
        logger.info(f"成功加载 {len(self.schemas)} 个提取模式")
        return self.schemas
    
    def get_workflow(self, workflow_id: str) -> Optional[Dict]:
        """获取指定ID的工作流配置"""
        if not self.workflows:
            self.load_workflows()
        
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            logger.warning(f"工作流 {workflow_id} 不存在")
        
        return workflow
    
    def get_schema(self, schema_id: str) -> Optional[Dict]:
        """获取指定ID的提取模式"""
        if not self.schemas:
            self.load_schemas()
        
        schema = self.schemas.get(schema_id)
        if not schema:
            logger.warning(f"提取模式 {schema_id} 不存在")
        
        return schema
    
    def get_workflow_ids(self) -> List[str]:
        """获取所有工作流ID"""
        if not self.workflows:
            self.load_workflows()
        
        return list(self.workflows.keys())
    
    def _validate_workflow(self, workflow: Dict) -> bool:
        """验证工作流配置有效性"""
        required_fields = ['name', 'start_url']
        
        for field in required_fields:
            if field not in workflow:
                logger.error(f"工作流缺少必需字段: {field}")
                return False
        
        # 检查是否存在Schema信息
        has_schema = (
            ('start_page_schema' in workflow and 'secondary_page_schema' in workflow) or
            ('start_page_schema_inline' in workflow and 'secondary_page_schema_inline' in workflow)
        )
        
        if not has_schema:
            logger.error("工作流缺少Schema定义：需要提供外部Schema文件路径或内联Schema定义")
            return False
        
        return True
    
    def create_workflow(self, workflow_config: Dict, workflow_id: str = None) -> bool:
        """创建新的工作流配置"""
        if not workflow_id:
            if 'id' in workflow_config:
                workflow_id = workflow_config['id']
            else:
                # 使用名称作为ID，替换空格为下划线
                workflow_id = workflow_config.get('name', '').lower().replace(' ', '_')
        
        if not workflow_id:
            logger.error("无法创建工作流：未提供ID且无法从配置生成ID")
            return False
        
        # 验证工作流
        if not self._validate_workflow(workflow_config):
            logger.error(f"无法创建工作流 {workflow_id}：配置无效")
            return False
        
        # 确保配置中包含ID
        workflow_config['id'] = workflow_id
        
        # 确保目录存在
        os.makedirs(self.workflows_dir, exist_ok=True)
        
        # 保存工作流
        try:
            workflow_path = os.path.join(self.workflows_dir, f"{workflow_id}.yaml")
            with open(workflow_path, 'w', encoding='utf-8') as f:
                yaml.dump(workflow_config, f, default_flow_style=False, allow_unicode=True)
            
            # 更新缓存
            self.workflows[workflow_id] = workflow_config
            logger.info(f"成功创建工作流: {workflow_id}")
            return True
        except Exception as e:
            logger.error(f"创建工作流 {workflow_id} 时出错: {e}")
            return False
    
    def load_all_workflows(self):
        """加载所有工作流配置文件"""
        logger.info(f"正在加载工作流目录 {self.workflows_dir} 中的所有工作流...")
        
        # 获取所有YAML文件
        workflow_files = list(Path(self.workflows_dir).glob("*.yaml")) + list(Path(self.workflows_dir).glob("*.yml"))
        
        if not workflow_files:
            logger.warning("未找到任何工作流配置文件")
            return []
        
        logger.info(f"找到 {len(workflow_files)} 个工作流配置文件")
        
        # 加载每个工作流
        workflows = []
        for workflow_file in workflow_files:
            try:
                workflow = self.load_workflow(workflow_file)
                if workflow:
                    workflows.append(workflow)
            except Exception as e:
                logger.error(f"加载工作流 {workflow_file} 时出错: {e}")
        
        self.workflows = workflows
        logger.info(f"成功加载 {len(workflows)} 个工作流")
        return workflows
    
    def load_workflow(self, workflow_path):
        """加载单个工作流配置文件"""
        logger.info(f"正在加载工作流: {workflow_path}")
        
        try:
            with open(workflow_path, 'r', encoding='utf-8') as f:
                workflow = yaml.safe_load(f)
            
            # 验证工作流配置
            if not self._validate_workflow(workflow):
                logger.error(f"工作流 {workflow_path} 配置无效")
                return None
            
            # 添加工作流路径
            workflow['_path'] = workflow_path
            workflow['_name'] = workflow.get('workflow_name', Path(workflow_path).stem)
            
            # 处理内联Schema
            if 'start_page_schema_inline' in workflow:
                logger.info(f"发现内联起始页Schema")
                workflow['start_page_schema'] = workflow['start_page_schema_inline']
            
            if 'secondary_page_schema_inline' in workflow:
                logger.info(f"发现内联二级页Schema")
                workflow['secondary_page_schema'] = workflow['secondary_page_schema_inline']
            
            # 处理外部Schema文件路径（如果使用的是外部Schema）
            workflow_dir = Path(workflow_path).parent
            
            # 只有当Schema是字符串路径时才需要处理
            if isinstance(workflow.get('start_page_schema'), str):
                start_schema_path = workflow_dir / workflow['start_page_schema']
                
                # 验证Schema文件是否存在
                if not start_schema_path.exists():
                    logger.error(f"起始页Schema {start_schema_path} 不存在")
                    return None
                
                # 更新路径
                workflow['start_page_schema'] = str(start_schema_path)
            
            if isinstance(workflow.get('secondary_page_schema'), str):
                secondary_schema_path = workflow_dir / workflow['secondary_page_schema']
                
                # 验证Schema文件是否存在
                if not secondary_schema_path.exists():
                    logger.error(f"二级页Schema {secondary_schema_path} 不存在")
                    return None
                
                # 更新路径
                workflow['secondary_page_schema'] = str(secondary_schema_path)
            
            # 确保输出目录是绝对路径
            output_dir = workflow['output_directory']
            if not os.path.isabs(output_dir):
                workflow['output_directory'] = str(Path(workflow_dir) / output_dir)
            
            logger.info(f"工作流 {workflow['_name']} 加载成功")
            return workflow
        
        except Exception as e:
            logger.error(f"加载工作流 {workflow_path} 时出错: {e}")
            return None
    
    def _validate_workflow(self, workflow):
        """验证工作流配置是否有效"""
        required_fields = ['start_url', 'output_directory']
        
        for field in required_fields:
            if field not in workflow:
                logger.error(f"工作流缺少必要字段: {field}")
                return False
        
        # 检查是否提供了Schema信息（外部文件或内联）
        has_schema = (
            ('start_page_schema' in workflow or 'start_page_schema_inline' in workflow) and
            ('secondary_page_schema' in workflow or 'secondary_page_schema_inline' in workflow)
        )
        
        if not has_schema:
            logger.error("工作流缺少Schema定义：需要提供外部Schema文件路径或内联Schema定义")
            return False
        
        return True
    
    def get_workflow_by_name(self, name):
        """根据名称获取工作流"""
        for workflow in self.workflows:
            if workflow['_name'] == name:
                return workflow
        return None
    
    def create_example_workflow(self, name="example"):
        """创建示例工作流配置（使用内联Schema）"""
        example_workflow = {
            "workflow_name": name,
            "start_url": "https://example.com/blog",
            "output_directory": f"output/{name}",
            
            # 内联Schema定义
            "start_page_schema_inline": {
                "description": f"用于在{name}起始页查找二级页面链接的Schema",
                "container": "article.post-summary",
                "link_selector": "h2 > a",
                "attribute": "href"
            },
            
            "secondary_page_schema_inline": {
                "description": f"用于提取{name}二级页面内容的Schema",
                "title": "h1.title",
                "author": "span.author",
                "date": "time.date",
                "content": "div.content",
                "date_attribute": "datetime",
                "remove": [".advertisement", ".related-posts"],
                "custom_fields": {
                    "category": ".post-category",
                    "tags": ".post-tags"
                }
            },
            
            "crawler_settings": {
                "engine": "playwright",
                "playwright": {
                    "headless": True,
                    "browser": "chromium",
                    "timeout": 30000
                },
                "request_delay": 1
            }
        }
        
        # 创建工作流目录
        os.makedirs(self.workflows_dir, exist_ok=True)
        
        # 创建输出目录
        output_dir = Path(f"output/{name}")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建工作流配置文件
        workflow_path = os.path.join(self.workflows_dir, f"{name}.yaml")
        with open(workflow_path, 'w', encoding='utf-8') as f:
            yaml.dump(example_workflow, f, default_flow_style=False, allow_unicode=True)
        
        logger.info(f"已创建示例工作流: {workflow_path}")
        return workflow_path

# 用于测试
if __name__ == "__main__":
    manager = WorkflowManager()
    
    # 创建示例工作流
    if not list(Path("workflows").glob("*.yaml")):
        manager.create_example_workflow()
    
    # 加载所有工作流
    workflows = manager.load_all_workflows()
    
    # 打印工作流信息
    for workflow in workflows:
        print(f"工作流: {workflow['_name']}")
        print(f"  起始URL: {workflow['start_url']}")
        print(f"  输出目录: {workflow['output_directory']}") 