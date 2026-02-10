"""
Robust Universal Extractor - 增强版通用提取器
集成视觉结构分析、配置驱动、累加规则
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

# 导入核心组件
from .rule_engine import get_rule_engine, ProductProfile
from .visual_analyzer import VisualStructureAnalyzer
from .config_wizard import ConfigurationWizard

# 保持向后兼容 - 导入原始提取器
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))
from direct_extractor import extract_tables_direct


class RobustUniversalExtractor:
    """
    健壮的通用产品规格提取器
    
    特性:
    1. 视觉+结构双重分析
    2. 自动配置检测与建议
    3. 累加式规则管理
    4. 全面的分析报告
    """
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = config_dir
        self.engine = get_rule_engine(config_dir)
        self.visual_analyzer = VisualStructureAnalyzer()
        self.wizard = ConfigurationWizard(config_dir)
        
        # 分析结果
        self.visual_report: Optional[Dict] = None
        self.extracted_data: Dict[str, Dict] = {}
        self.profile: Optional[ProductProfile] = None
        
    def extract_with_analysis(self, html: str, url: str = "", 
                              profile_name: str = None,
                              interactive: bool = False) -> Dict:
        """
        执行完整提取流程（含分析）
        
        Args:
            html: 页面HTML
            url: 页面URL
            profile_name: 指定配置文件，None则自动检测
            interactive: 是否启用交互式配置
            
        Returns:
            {
                'data': 提取结果,
                'analysis': 分析报告,
                'profile_used': 使用的配置,
                'recommendations': 改进建议
            }
        """
        # 1. 视觉结构分析
        print("🔍 正在分析页面结构...")
        self.visual_report = self.visual_analyzer.analyze(html, url)
        
        # 2. 确定配置文件
        if not profile_name:
            # 从URL检测
            url_profile = self._detect_profile_from_url(url)
            # 从结构检测
            structure_profile = self._detect_profile_from_structure(self.visual_report)
            
            # 选择置信度高的
            if structure_profile:
                profile_name = structure_profile
            elif url_profile:
                profile_name = url_profile
            else:
                profile_name = 'H3C-Switch-Box'  # 默认
        
        self.profile = self.engine.get_profile(profile_name)
        if not self.profile:
            print(f"⚠️  配置文件 '{profile_name}' 不存在，使用默认配置")
            profile_name = 'H3C-Switch-Box'
            self.profile = self.engine.get_profile(profile_name)
        
        print(f"✅ 使用配置: {profile_name}")
        
        # 3. 执行提取
        print("📊 正在提取数据...")
        try:
            # 优先使用原始提取器（已验证稳定）
            self.extracted_data = extract_tables_direct(html, url)
        except Exception as e:
            print(f"⚠️  提取出错: {e}")
            self.extracted_data = {}
        
        # 4. 验证与补充
        self._validate_and_enrich()
        
        # 5. 生成建议
        recommendations = self._generate_improvement_suggestions()
        
        # 6. 交互式配置（如需要）
        if interactive and recommendations:
            print("\n" + "="*60)
            print("发现可以改进的地方，启动交互式配置向导...")
            print("="*60)
            # 这里可以调用wizard
        
        return {
            'data': self.extracted_data,
            'analysis': self.visual_report,
            'profile_used': profile_name,
            'recommendations': recommendations
        }
    
    def analyze_only(self, html: str, url: str = "") -> Dict:
        """仅执行分析，不提取"""
        return self.visual_analyzer.analyze(html, url)
    
    def generate_config_template(self, html: str, url: str = "") -> str:
        """为新页面生成配置模板"""
        report = self.visual_analyzer.analyze(html, url)
        
        lines = [
            f"# Auto-generated configuration for: {url}",
            f"# Generated based on visual structure analysis",
            "",
            f"name: \"New-Profile-{url.split('/')[-2] if url else 'Unknown'}\"",
            "brand: \"H3C\"",
            "product_type: \"switch\"",
            "sub_type: \"unknown\"",
            "version: \"1.0\"",
            f"parent_profile: \"{self._detect_profile_from_url(url) or 'H3C-Switch-Box'}\"",
            "",
            "# Analysis Summary:",
            f"# - Content regions found: {report['summary']['content_regions']}",
            f"# - Tables detected: {report['summary']['tables_found']}",
            f"# - Semantic patterns: {report['summary']['patterns_discovered']}",
            "",
        ]
        
        # 表格配置建议
        if report['table_analysis']:
            lines.extend([
                "# Table Detection Rules (from analysis):",
                "table_detection_rules:"
            ])
            
            for table in report['table_analysis']:
                if table['confidence'] > 0.6:
                    lines.extend([
                        f"  # Table {table['index']}: {table['type']} (confidence: {table['confidence']:.2f})",
                        f"  - name: \"table_{table['index']}\"",
                        f"    pattern: \"(?i){self._generate_pattern_from_headers(table['headers'])}\"",
                        "    rule_type: \"table_detection\"",
                        "    action: \"use_extractor\"",
                        "    params:",
                        f"      extractor: \"{table['suggested_extractor']}\"",
                        f"    priority: {int(table['confidence'] * 100)}",
                        ""
                    ])
        
        # 参数映射建议
        all_mappings = []
        for table in report['table_analysis']:
            all_mappings.extend(table.get('suggested_mappings', []))
        
        if all_mappings:
            lines.extend([
                "# Parameter Mapping Rules (from analysis):",
                "param_mapping_rules:"
            ])
            
            seen = set()
            for mapping in all_mappings:
                key = mapping.get('original', '')
                if key and key not in seen:
                    seen.add(key)
                    target = mapping.get('suggested', 'TODO')
                    lines.extend([
                        f"  - name: \"map_{key.replace(' ', '_').lower()}\"",
                        f"    pattern: \"(?i){key}\"",
                        "    rule_type: \"param_mapping\"",
                        "    action: \"map_to\"",
                        "    params:",
                        f"      target: \"{target}\"",
                        "    priority: 100",
                        ""
                    ])
        
        return '\n'.join(lines)
    
    def _detect_profile_from_url(self, url: str) -> Optional[str]:
        """从URL检测适用的配置"""
        url_lower = url.lower()
        
        # 框式交换机
        if any(x in url_lower for x in ['s125', 's105', 's76', 's75', 's95', 's98', 'chassis']):
            return 'H3C-Switch-Chassis'
        
        # 盒式交换机
        if any(x in url_lower for x in ['s5130', 's5590', 's6520', 's5560', 's5500']):
            return 'H3C-Switch-Box'
        
        return None
    
    def _detect_profile_from_structure(self, report: Dict) -> Optional[str]:
        """从结构分析检测适用的配置"""
        # 检查是否有框式特征
        for table in report.get('table_analysis', []):
            headers = table.get('headers', [])
            header_str = ' '.join(headers).lower()
            
            # 框式特征：槽位相关参数
            if any(x in header_str for x in ['slot', 'chassis', 'module', '板', '槽']):
                return 'H3C-Switch-Chassis'
        
        # 检查区域类型
        for region in report.get('content_regions', []):
            if 'chassis' in region.get('type', '').lower():
                return 'H3C-Switch-Chassis'
        
        return None
    
    def _validate_and_enrich(self):
        """验证并丰富提取结果"""
        if not self.extracted_data:
            return
        
        # 对比视觉分析结果
        if self.visual_report:
            # 检查是否遗漏了某些表格
            extracted_models = set(self.extracted_data.keys())
            detected_models = set()
            
            for region in self.visual_report.get('content_regions', []):
                detected_models.update(region.get('model_names', []))
            
            missing_models = detected_models - extracted_models
            if missing_models:
                print(f"⚠️  视觉分析发现但未提取的型号: {missing_models}")
    
    def _generate_improvement_suggestions(self) -> List[Dict]:
        """生成改进建议"""
        suggestions = []
        
        if not self.visual_report:
            return suggestions
        
        # 从分析报告获取建议
        suggestions.extend(self.visual_report.get('recommendations', []))
        
        # 检查数据完整性
        if self.extracted_data:
            for model, data in self.extracted_data.items():
                if not data:
                    suggestions.append({
                        'priority': 'high',
                        'category': 'extraction',
                        'message': f'型号 {model} 提取结果为空',
                        'action': 'check_extraction_rules'
                    })
        
        return suggestions
    
    def _generate_pattern_from_headers(self, headers: List[str]) -> str:
        """从表头生成匹配模式"""
        if not headers:
            return ".*"
        
        # 取前两个有意义的表头词
        keywords = []
        for h in headers[:2]:
            h_clean = re.sub(r'[^\w]', '', h.lower())
            if len(h_clean) > 3:
                keywords.append(h_clean[:15])
        
        if keywords:
            return '.*'.join(keywords)
        return ".*"
    
    def get_detailed_report(self) -> str:
        """获取详细的文本报告"""
        if not self.visual_report:
            return "No analysis performed yet."
        
        lines = [
            "=" * 70,
            "视觉结构分析报告",
            "=" * 70,
            "",
            f"📊 页面概览:",
            f"   视觉区块数: {self.visual_report['summary']['total_blocks']}",
            f"   内容区域数: {self.visual_report['summary']['content_regions']}",
            f"   表格数量: {self.visual_report['summary']['tables_found']}",
            f"   发现的模式: {self.visual_report['summary']['patterns_discovered']}",
            "",
            f"📑 内容区域:",
        ]
        
        for region in self.visual_report['content_regions']:
            lines.append(f"   [{region['type']}] {region['title']}")
            lines.append(f"      区块: {region['block_count']}, 表格: {region['table_count']}")
            if region.get('model_names'):
                lines.append(f"      型号: {', '.join(region['model_names'][:5])}")
            lines.append("")
        
        lines.extend([
            f"📋 表格分析:",
        ])
        
        for table in self.visual_report['table_analysis']:
            lines.append(f"   表格 {table['index']}: {table['type']}")
            lines.append(f"      置信度: {table['confidence']:.2f}")
            lines.append(f"      尺寸: {table['dimensions']}")
            lines.append(f"      建议提取器: {table['suggested_extractor']}")
            if table.get('suggested_mappings'):
                lines.append(f"      参数映射建议: {len(table['suggested_mappings'])}个")
            lines.append("")
        
        if self.visual_report.get('recommendations'):
            lines.extend([
                f"💡 改进建议:",
            ])
            for rec in self.visual_report['recommendations']:
                lines.append(f"   [{rec['priority']}] {rec['message']}")
                lines.append(f"      操作: {rec.get('action', 'N/A')}")
                lines.append("")
        
        lines.append("=" * 70)
        
        return '\n'.join(lines)


# 便捷函数
def extract_robust(html: str, url: str = "", profile: str = None, 
                   interactive: bool = False) -> Dict:
    """便捷提取函数"""
    extractor = RobustUniversalExtractor()
    return extractor.extract_with_analysis(html, url, profile, interactive)


def analyze_page(html: str, url: str = "") -> Dict:
    """便捷分析函数"""
    analyzer = VisualStructureAnalyzer()
    return analyzer.analyze(html, url)
