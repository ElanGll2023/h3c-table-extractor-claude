"""
交互式规则配置向导
引导用户分析和配置新产品页面
"""

import json
from typing import Dict, List, Optional
from pathlib import Path


class ConfigurationWizard:
    """配置向导 - 交互式创建规则"""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.current_profile = None
        self.discovered_issues = []
    
    def start_analysis(self, url: str, html: str) -> Dict:
        """开始分析流程"""
        from core.page_analyzer import PageAnalyzer
        from core.rule_engine import get_rule_engine
        
        # 分析页面
        analyzer = PageAnalyzer()
        report = analyzer.analyze(html, url)
        
        # 生成分析报告
        analysis_result = {
            "url": url,
            "suggested_profile": report.suggested_profile,
            "confidence": report.confidence,
            "tables_found": len(report.detected_tables),
            "parameters_found": len(report.discovered_params),
            "issues": []
        }
        
        # 检查问题
        for table in report.detected_tables:
            if table.confidence < 0.6:
                analysis_result["issues"].append({
                    "type": "low_confidence_table",
                    "table_index": table.index,
                    "current_type": table.table_type,
                    "message": f"Table {table.index} type detection uncertain ({table.confidence:.2f})"
                })
        
        # 未映射参数
        for param in report.discovered_params:
            if not param.suggested_mapping:
                analysis_result["issues"].append({
                    "type": "unmapped_parameter",
                    "param_name": param.original_name,
                    "category": param.suggested_category,
                    "message": f"New parameter: {param.original_name}"
                })
        
        self.discovered_issues = analysis_result["issues"]
        return analysis_result
    
    def interactive_configure(self, analysis_result: Dict) -> str:
        """
        交互式配置流程
        返回生成的配置YAML字符串
        """
        print("=" * 60)
        print("产品规格提取器 - 配置向导")
        print("=" * 60)
        print()
        
        # 1. 确认产品类型
        print(f"📋 分析结果:")
        print(f"   URL: {analysis_result['url']}")
        print(f"   建议配置: {analysis_result['suggested_profile']}")
        print(f"   置信度: {analysis_result['confidence']:.2f}")
        print(f"   发现表格: {analysis_result['tables_found']}")
        print(f"   发现参数: {analysis_result['parameters_found']}")
        print()
        
        # 2. 处理发现的问题
        if analysis_result["issues"]:
            print(f"⚠️  发现 {len(analysis_result['issues'])} 个问题需要确认:")
            print()
            
            new_rules = {
                "table_rules": [],
                "param_mappings": []
            }
            
            for i, issue in enumerate(analysis_result["issues"], 1):
                print(f"问题 {i}/{len(analysis_result['issues'])}:")
                
                if issue["type"] == "unmapped_parameter":
                    rule = self._handle_unmapped_param(issue)
                    if rule:
                        new_rules["param_mappings"].append(rule)
                        
                elif issue["type"] == "low_confidence_table":
                    rule = self._handle_uncertain_table(issue)
                    if rule:
                        new_rules["table_rules"].append(rule)
                
                print()
        
        # 3. 生成配置文件
        profile_name = input("\n配置文件名称 (如: H3C-Switch-S5570): ").strip()
        parent = analysis_result["suggested_profile"] or "H3C-Switch-Box"
        
        config = self._generate_profile_yaml(profile_name, parent, new_rules)
        
        print("\n" + "=" * 60)
        print("✅ 配置生成完成!")
        print("=" * 60)
        print("\n生成的配置内容:")
        print("-" * 60)
        print(config)
        print("-" * 60)
        
        # 保存配置
        save = input("\n保存配置到文件? (y/n): ").strip().lower()
        if save == 'y':
            self._save_config(profile_name, config)
            print(f"✅ 配置已保存到: config/profiles/{profile_name}.yaml")
        
        return config
    
    def _handle_unmapped_param(self, issue: Dict) -> Optional[Dict]:
        """处理未映射参数"""
        print(f"  参数: {issue['param_name']}")
        print(f"  分类: {issue['category']}")
        print()
        
        action = input("  操作 [k]eep(保留)/[s]kip(跳过)/[r]ename(重命名): ").strip().lower()
        
        if action == 's':
            return None
        
        if action == 'r':
            chinese_name = input("  中文参数名: ").strip()
            return {
                "name": f"mapping_{issue['param_name']}",
                "pattern": issue['param_name'],
                "action": "map_to",
                "target": chinese_name,
                "category": issue['category']
            }
        
        # keep - 使用自动建议的映射
        return {
            "name": f"mapping_{issue['param_name']}",
            "pattern": issue['param_name'],
            "action": "map_to",
            "target": None,  # 保持原样
            "category": issue['category']
        }
    
    def _handle_uncertain_table(self, issue: Dict) -> Optional[Dict]:
        """处理不确定的表格"""
        print(f"  表格 {issue['table_index']}: 类型检测不确定")
        print(f"  当前猜测: {issue['current_type']}")
        print()
        
        print("  表格类型选项:")
        print("    1. hardware_multi - 多型号硬件表")
        print("    2. hardware_single - 单型号硬件表")
        print("    3. software - 软件特性表")
        print("    4. performance - 性能参数表")
        print("    5. poe_power - POE功率表")
        print("    6. protocols - 协议支持表")
        print("    s. skip - 跳过此表")
        
        choice = input("  选择: ").strip()
        
        type_map = {
            '1': 'hardware_multi',
            '2': 'hardware_single',
            '3': 'software',
            '4': 'performance',
            '5': 'poe_power',
            '6': 'protocols'
        }
        
        if choice == 's' or choice not in type_map:
            return None
        
        return {
            "name": f"table_{issue['table_index']}",
            "pattern": f"(?i)table_{issue['table_index']}",  # 简化示例
            "type": type_map[choice],
            "confidence": "manual"
        }
    
    def _generate_profile_yaml(self, name: str, parent: str, rules: Dict) -> str:
        """生成配置文件YAML"""
        lines = [
            f"# Auto-generated profile: {name}",
            f"name: \"{name}\"",
            "brand: \"H3C\"",
            "product_type: \"switch\"",
            "sub_type: \"box\"",
            "version: \"1.0\"",
            f"parent_profile: \"{parent}\"",
            "",
            "# Inherited rules from parent will be merged automatically",
            "",
            "# Additional table detection rules:",
        ]
        
        if rules.get("table_rules"):
            lines.append("table_detection_rules:")
            for rule in rules["table_rules"]:
                lines.append(f"  - name: \"{rule['name']}\"")
                lines.append(f"    pattern: \"{rule['pattern']}\"")
                lines.append(f"    rule_type: \"table_detection\"")
                lines.append(f"    action: \"use_extractor\"")
                lines.append(f"    params:")
                lines.append(f"      extractor: \"{rule['type']}\"")
                lines.append(f"    priority: 90")
                lines.append("")
        
        if rules.get("param_mappings"):
            lines.append("# Additional parameter mapping rules:")
            lines.append("param_mapping_rules:")
            for rule in rules["param_mappings"]:
                if rule["target"]:
                    lines.append(f"  - name: \"{rule['name']}\"")
                    lines.append(f"    pattern: \"{rule['pattern']}\"")
                    lines.append(f"    rule_type: \"param_mapping\"")
                    lines.append(f"    action: \"map_to\"")
                    lines.append(f"    params:")
                    lines.append(f"      target: \"{rule['target']}\"")
                    lines.append(f"    priority: 100")
                    lines.append("")
        
        return '\n'.join(lines)
    
    def _save_config(self, name: str, config: str):
        """保存配置文件"""
        profile_dir = self.config_dir / "profiles"
        profile_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = profile_dir / f"{name}.yaml"
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(config)


# 命令行入口
def main():
    """命令行向导入口"""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent))
    
    from crawler.html_fetcher import HTMLFetcher
    
    print("通用产品规格提取器 - 配置向导")
    print("=" * 60)
    
    url = input("请输入产品页面URL: ").strip()
    
    print(f"\n正在获取页面: {url}")
    fetcher = HTMLFetcher(delay=1.5)
    html = fetcher.fetch(url)
    
    print("✅ 页面获取成功，开始分析...\n")
    
    wizard = ConfigurationWizard()
    analysis = wizard.start_analysis(url, html)
    
    # 显示分析结果
    print(json.dumps(analysis, indent=2, ensure_ascii=False))
    
    # 开始交互式配置
    proceed = input("\n开始交互式配置? (y/n): ").strip().lower()
    if proceed == 'y':
        wizard.interactive_configure(analysis)


if __name__ == "__main__":
    main()
