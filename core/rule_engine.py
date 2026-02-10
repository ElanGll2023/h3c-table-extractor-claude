"""
Universal Product Specs Extractor - Rule Engine
可累加的配置驱动规则引擎
"""

import yaml
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class ExtractionRule:
    """单个提取规则"""
    name: str
    pattern: str
    rule_type: str  # 'table_detection', 'param_mapping', 'value_extraction'
    action: str     # 'extract', 'skip', 'transform', 'merge'
    params: Dict[str, Any] = field(default_factory=dict)
    priority: int = 100
    enabled: bool = True


@dataclass
class ProductProfile:
    """产品类型配置文件"""
    name: str
    brand: str
    product_type: str  # 'switch', 'router', 'firewall', 'wireless'
    sub_type: str      # 'box', 'chassis', 'datacenter'
    version: str = "1.0"
    parent_profile: Optional[str] = None
    
    # 规则集
    table_detection_rules: List[ExtractionRule] = field(default_factory=list)
    param_mapping_rules: List[ExtractionRule] = field(default_factory=list)
    value_extraction_rules: List[ExtractionRule] = field(default_factory=list)
    post_processing_rules: List[ExtractionRule] = field(default_factory=list)
    
    # 默认参数
    default_fields: List[str] = field(default_factory=list)
    skip_patterns: List[str] = field(default_factory=list)
    
    def merge_with_parent(self, parent: 'ProductProfile'):
        """继承父配置并合并"""
        if not parent:
            return
        
        # 父规则优先级低，子规则覆盖
        self.table_detection_rules = (
            parent.table_detection_rules + 
            [r for r in self.table_detection_rules if r.name not in 
             {pr.name for pr in parent.table_detection_rules}]
        )
        self.param_mapping_rules = (
            parent.param_mapping_rules + 
            [r for r in self.param_mapping_rules if r.name not in 
             {pr.name for pr in parent.param_mapping_rules}]
        )
        # ... 其他规则集同样处理


class RuleEngine:
    """规则引擎 - 核心控制器"""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.profiles: Dict[str, ProductProfile] = {}
        self.global_rules: Dict[str, List[ExtractionRule]] = {}
        self._load_all_configs()
    
    def _load_all_configs(self):
        """加载所有配置文件"""
        # 加载全局规则
        self._load_global_rules()
        
        # 加载产品配置文件
        profile_dir = self.config_dir / "profiles"
        if profile_dir.exists():
            for yaml_file in profile_dir.glob("*.yaml"):
                profile = self._load_profile(yaml_file)
                if profile:
                    self.profiles[profile.name] = profile
    
    def _load_global_rules(self):
        """加载全局规则"""
        rules_dir = self.config_dir / "rules"
        if not rules_dir.exists():
            return
        
        # 加载表格检测规则
        table_rules_file = rules_dir / "table_detection.yaml"
        if table_rules_file.exists():
            with open(table_rules_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                self.global_rules['table_detection'] = [
                    ExtractionRule(**rule) for rule in data.get('rules', [])
                ]
        
        # 加载参数映射规则
        mapping_file = rules_dir / "param_mappings.yaml"
        if mapping_file.exists():
            with open(mapping_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                self.global_rules['param_mapping'] = [
                    ExtractionRule(**rule) for rule in data.get('rules', [])
                ]
    
    def _load_profile(self, yaml_file: Path) -> Optional[ProductProfile]:
        """加载单个配置文件"""
        try:
            with open(yaml_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            profile = ProductProfile(
                name=data.get('name', yaml_file.stem),
                brand=data.get('brand', 'Unknown'),
                product_type=data.get('product_type', 'unknown'),
                sub_type=data.get('sub_type', 'unknown'),
                version=data.get('version', '1.0'),
                parent_profile=data.get('parent_profile'),
                default_fields=data.get('default_fields', []),
                skip_patterns=data.get('skip_patterns', [])
            )
            
            # 加载各类规则
            profile.table_detection_rules = [
                ExtractionRule(**rule) 
                for rule in data.get('table_detection_rules', [])
            ]
            profile.param_mapping_rules = [
                ExtractionRule(**rule) 
                for rule in data.get('param_mapping_rules', [])
            ]
            
            # 如果有父配置，合并
            if profile.parent_profile and profile.parent_profile in self.profiles:
                profile.merge_with_parent(self.profiles[profile.parent_profile])
            
            return profile
            
        except Exception as e:
            print(f"Error loading profile {yaml_file}: {e}")
            return None
    
    def detect_profile(self, url: str, html_sample: str) -> Optional[str]:
        """根据URL和HTML样本检测适用的配置"""
        # URL模式匹配
        for name, profile in self.profiles.items():
            url_patterns = profile.default_fields.get('url_patterns', [])
            for pattern in url_patterns:
                if re.search(pattern, url, re.IGNORECASE):
                    return name
        
        # HTML特征匹配
        # TODO: 实现更智能的检测
        
        return None
    
    def get_profile(self, name: str) -> Optional[ProductProfile]:
        """获取指定配置"""
        return self.profiles.get(name)
    
    def list_profiles(self) -> List[Dict]:
        """列出所有可用配置"""
        return [
            {
                'name': p.name,
                'brand': p.brand,
                'type': p.product_type,
                'sub_type': p.sub_type,
                'version': p.version
            }
            for p in self.profiles.values()
        ]
    
    def add_profile(self, profile: ProductProfile, save: bool = True):
        """添加新配置（累加）"""
        self.profiles[profile.name] = profile
        
        if save:
            self._save_profile(profile)
    
    def _save_profile(self, profile: ProductProfile):
        """保存配置到文件"""
        profile_dir = self.config_dir / "profiles"
        profile_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = profile_dir / f"{profile.name}.yaml"
        
        data = {
            'name': profile.name,
            'brand': profile.brand,
            'product_type': profile.product_type,
            'sub_type': profile.sub_type,
            'version': profile.version,
            'parent_profile': profile.parent_profile,
            'default_fields': profile.default_fields,
            'skip_patterns': profile.skip_patterns,
            'table_detection_rules': [
                {
                    'name': r.name,
                    'pattern': r.pattern,
                    'rule_type': r.rule_type,
                    'action': r.action,
                    'params': r.params,
                    'priority': r.priority
                }
                for r in profile.table_detection_rules
            ],
            'param_mapping_rules': [
                {
                    'name': r.name,
                    'pattern': r.pattern,
                    'rule_type': r.rule_type,
                    'action': r.action,
                    'params': r.params,
                    'priority': r.priority
                }
                for r in profile.param_mapping_rules
            ]
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True, sort_keys=False)
    
    def update_rule(self, profile_name: str, rule_type: str, rule: ExtractionRule):
        """更新指定配置的规则（累加更新）"""
        profile = self.profiles.get(profile_name)
        if not profile:
            raise ValueError(f"Profile {profile_name} not found")
        
        rule_list = getattr(profile, f"{rule_type}_rules", [])
        
        # 检查是否已存在同名规则
        existing_idx = next(
            (i for i, r in enumerate(rule_list) if r.name == rule.name),
            None
        )
        
        if existing_idx is not None:
            # 更新现有规则（保留版本历史）
            rule_list[existing_idx] = rule
        else:
            # 添加新规则
            rule_list.append(rule)
        
        # 保存更新
        self._save_profile(profile)


# 全局规则引擎实例
_default_engine = None

def get_rule_engine(config_dir: str = "config") -> RuleEngine:
    """获取规则引擎单例"""
    global _default_engine
    if _default_engine is None:
        _default_engine = RuleEngine(config_dir)
    return _default_engine
