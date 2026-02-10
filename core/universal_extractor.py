"""
通用产品规格提取器 - 配置驱动版本
支持累加规则，不破坏现有功能
"""

import re
import sys
from typing import Dict, List, Optional, Any
from bs4 import BeautifulSoup, Tag
from pathlib import Path

# 导入规则引擎
sys.path.insert(0, str(Path(__file__).parent))
from rule_engine import get_rule_engine, ProductProfile, ExtractionRule
from page_analyzer import PageAnalyzer, PageAnalysisReport


class UniversalExtractor:
    """通用产品规格提取器"""
    
    def __init__(self, profile_name: str = None, config_dir: str = "config"):
        """
        Args:
            profile_name: 使用的配置文件名称，None则自动检测
            config_dir: 配置文件目录
        """
        self.profile_name = profile_name
        self.config_dir = config_dir
        self.engine = get_rule_engine(config_dir)
        self.profile: Optional[ProductProfile] = None
        self.analyzer = PageAnalyzer()
        
        # 提取结果
        self.extracted_data: Dict[str, Dict] = {}
        self.analysis_report: Optional[PageAnalysisReport] = None
        self.warnings: List[str] = []
    
    def extract(self, html: str, url: str = "", auto_detect: bool = True) -> Dict[str, Dict]:
        """
        提取产品规格
        
        Args:
            html: 页面HTML内容
            url: 页面URL（用于检测配置）
            auto_detect: 是否自动检测配置
            
        Returns:
            提取结果字典 {model_name: {param: value}}
        """
        # 1. 分析页面结构
        self.analysis_report = self.analyzer.analyze(html, url)
        
        # 2. 确定使用哪个配置
        if not self.profile_name and auto_detect:
            self.profile_name = self.analysis_report.suggested_profile
        
        if self.profile_name:
            self.profile = self.engine.get_profile(self.profile_name)
        
        if not self.profile:
            # 使用默认配置
            self.warnings.append(f"No profile found for {url}, using default")
            self.profile = self._create_default_profile()
        
        # 3. 解析HTML
        soup = BeautifulSoup(html, 'lxml')
        tables = soup.find_all('table')
        
        # 4. 提取系列级信息
        series_data = {}
        model_descriptions = self._extract_model_descriptions(soup)
        series_features = self._extract_series_features(soup)
        
        # 5. 处理每个表格
        for i, table in enumerate(tables):
            table_data = self._process_table_with_rules(table, i, url)
            if table_data:
                self._merge_table_data(table_data, series_data)
        
        # 6. 后处理
        self._apply_post_processing()
        
        # 7. 添加通用字段
        for model_name in self.extracted_data:
            # 添加URL
            self.extracted_data[model_name]['链接地址'] = url
            
            # 添加型号描述
            if model_name in model_descriptions:
                self.extracted_data[model_name]['型号描述'] = model_descriptions[model_name]
            
            # 添加系列特性
            if series_features:
                self.extracted_data[model_name]['系列特性'] = series_features
        
        return self.extracted_data
    
    def _process_table_with_rules(self, table: Tag, index: int, url: str) -> Optional[Dict[str, Dict]]:
        """使用规则处理表格"""
        text = table.get_text(strip=True)
        
        # 跳过小表格
        if len(text) < 200:
            return None
        
        # 1. 检测表格类型（使用规则）
        table_type = self._detect_table_type_with_rules(text)
        
        # 2. 解析表格结构
        headers, rows = self._parse_table_structure(table)
        if not headers or not rows:
            return None
        
        # 3. 根据类型选择提取器
        if table_type == 'poe_power':
            return self._extract_poe_table(headers, rows)
        elif table_type == 'software':
            return self._extract_software_table(headers, rows)
        elif table_type == 'performance':
            return self._extract_performance_table(headers, rows)
        elif table_type == 'protocols':
            return self._extract_protocols_table(headers, rows)
        elif self._is_multi_model_table(headers):
            return self._extract_multi_model_table(headers, rows)
        else:
            return self._extract_generic_table(headers, rows)
    
    def _detect_table_type_with_rules(self, text: str) -> str:
        """使用规则检测表格类型"""
        text_lower = text.lower()
        
        # 使用配置文件中的规则
        if self.profile:
            for rule in sorted(self.profile.table_detection_rules, 
                             key=lambda r: r.priority, reverse=True):
                if not rule.enabled:
                    continue
                try:
                    if re.search(rule.pattern, text_lower):
                        return rule.params.get('extractor', 'generic')
                except re.error:
                    continue
        
        # 使用全局规则
        for rule in sorted(self.engine.global_rules.get('table_detection', []),
                         key=lambda r: r.priority, reverse=True):
            if not rule.enabled:
                continue
            try:
                if re.search(rule.pattern, text_lower):
                    return rule.params.get('extractor', 'generic')
            except re.error:
                continue
        
        # 默认检测逻辑
        return self._fallback_table_detection(text)
    
    def _fallback_table_detection(self, text: str) -> str:
        """后备表格检测"""
        text_lower = text.lower()
        
        if 'organization' in text_lower and 'ieee' in text_lower:
            return 'protocols'
        elif 'poe power capacity' in text_lower and 'quantity' in text_lower:
            return 'poe_power'
        elif any(x in text_lower for x in ['mac address entries', 'vlan table']):
            return 'performance'
        elif 'software' in text_lower and ('vlan' in text_lower or 'routing' in text_lower):
            return 'software'
        
        return 'hardware'
    
    def _parse_table_structure(self, table: Tag) -> tuple:
        """解析表格结构"""
        # 查找表头
        headers = []
        thead = table.find('thead')
        if thead:
            header_row = thead.find('tr')
            if header_row:
                headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
        
        if not headers:
            # 尝试第一行作为表头
            first_row = table.find('tr')
            if first_row:
                headers = [cell.get_text(strip=True) for cell in first_row.find_all(['th', 'td'])]
        
        # 解析数据行
        rows = []
        data_rows = table.find_all('tr')[1:] if headers else table.find_all('tr')
        
        for tr in data_rows:
            cells = tr.find_all(['td', 'th'])
            if len(cells) >= 2:
                row_data = {}
                for i, cell in enumerate(cells):
                    if i < len(headers):
                        # 处理rowspan
                        rowspan = cell.get('rowspan')
                        if rowspan:
                            # 简化处理，实际应该缓存rowspan值
                            pass
                        row_data[headers[i]] = cell.get_text(strip=True)
                if row_data:
                    rows.append(row_data)
        
        return headers, rows
    
    def _extract_model_descriptions(self, soup: BeautifulSoup) -> Dict[str, str]:
        """提取型号描述"""
        descriptions = {}
        text_content = soup.get_text()
        
        # 使用配置中的模式
        patterns = [
            r'(S\d{4}[A-Z]*-[\w-]+):\s*([0-9x\s/]+(?:BASE-T|Ethernet|Ports|SFP)[^\n;]+?)(?=\n|S\d{4}|$)',
            r'(S\d{4}[A-Z]*-[\w-]+)\s*[:：]\s*([^\n]+?)(?=\n|S\d{4}|$)',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            for model, desc in matches:
                model = model.strip()
                desc = desc.strip()
                if len(desc) > 10 and len(desc) < 200:
                    if model not in descriptions:
                        descriptions[model] = desc
        
        return descriptions
    
    def _extract_series_features(self, soup: BeautifulSoup) -> str:
        """提取系列特性"""
        features = []
        
        # 使用配置中的skip patterns
        skip_patterns = self.profile.skip_patterns if self.profile else []
        
        headers = soup.find_all(['h2', 'h3'])
        first_table = soup.find('table')
        
        for h in headers:
            text = h.get_text(strip=True)
            if len(text) > 80 or len(text) < 5:
                continue
            
            text_lower = text.lower()
            
            # 跳过过滤模式
            if any(sp in text_lower for sp in skip_patterns):
                continue
            
            if 'continued' in text_lower:
                continue
            
            if text and text not in features:
                features.append(text)
        
        return '; '.join(features) if features else ''
    
    def _is_multi_model_table(self, headers: List[str]) -> bool:
        """判断是否多型号表格"""
        return len(headers) > 2 and any(
            self._is_model_name(h) for h in headers[1:]
        )
    
    def _is_model_name(self, text: str) -> bool:
        """判断是否为型号名称"""
        if not text:
            return False
        patterns = [
            r'^S\d{4}[A-Z]*-[\w-]+',
            r'^[A-Z]{2,}\d{3,}',
        ]
        return any(re.match(p, text) for p in patterns)
    
    def _normalize_param_name(self, param: str) -> Optional[str]:
        """使用规则映射参数名"""
        param_lower = param.lower()
        
        # 使用配置文件规则
        if self.profile:
            for rule in sorted(self.profile.param_mapping_rules,
                             key=lambda r: r.priority, reverse=True):
                if not rule.enabled:
                    continue
                try:
                    if re.search(rule.pattern, param_lower):
                        if rule.action == 'map_to':
                            return rule.params.get('target')
                except re.error:
                    continue
        
        # 使用全局规则
        for rule in sorted(self.engine.global_rules.get('param_mapping', []),
                         key=lambda r: r.priority, reverse=True):
            if not rule.enabled:
                continue
            try:
                if re.search(rule.pattern, param_lower):
                    if rule.action == 'map_to':
                        return rule.params.get('target')
            except re.error:
                continue
        
        return None
    
    def _apply_post_processing(self):
        """应用后处理规则"""
        if not self.profile:
            return
        
        for model_name, specs in self.extracted_data.items():
            # 合并1G端口数到1000Base-T端口数
            if '1G端口数' in specs and '1000Base-T端口数' not in specs:
                specs['1000Base-T端口数'] = specs['1G端口数']
            if '1G端口数' in specs:
                del specs['1G端口数']
            
            # 合并POE功率
            poe_parts = []
            if 'POE总功率_AC' in specs:
                poe_parts.append(f"AC:{specs['POE总功率_AC']}W")
            if 'POE总功率_DC' in specs:
                poe_parts.append(f"DC:{specs['POE总功率_DC']}W")
            if poe_parts and 'POE总功率' not in specs:
                specs['POE总功率'] = '/'.join(poe_parts)
            if 'POE总功率_AC' in specs:
                del specs['POE总功率_AC']
            if 'POE总功率_DC' in specs:
                del specs['POE总功率_DC']
            
            # 分类交换机类型
            specs['交换机类型'] = self._classify_switch_type(model_name, specs)
    
    def _classify_switch_type(self, model_name: str, specs: Dict) -> str:
        """分类交换机类型"""
        chassis_prefixes = ['S125', 'S105', 'S76', 'S75', 'S95', 'S98']
        for prefix in chassis_prefixes:
            if model_name.startswith(prefix):
                return '框式交换机'
        
        chassis_params = ['业务板槽位', '主控板槽位', '接口板槽位']
        for param in specs:
            if any(cp in param for cp in chassis_params):
                return '框式交换机'
        
        return '盒式交换机'
    
    def _merge_table_data(self, table_data: Dict[str, Dict], series_data: Dict):
        """合并表格数据"""
        for model_name, specs in table_data.items():
            if not specs:
                continue
            
            # 系列级数据
            if 'Series' in model_name or 'Performance' in model_name or 'Protocols' in model_name:
                series_data[model_name] = specs
            else:
                if model_name not in self.extracted_data:
                    self.extracted_data[model_name] = {}
                self.extracted_data[model_name].update(specs)
        
        # 合并系列数据到所有型号
        if series_data and self.extracted_data:
            for series_key, series_specs in series_data.items():
                for model_name in self.extracted_data:
                    self.extracted_data[model_name].update(series_specs)
    
    def _create_default_profile(self) -> ProductProfile:
        """创建默认配置"""
        from rule_engine import ProductProfile
        return ProductProfile(
            name="Default",
            brand="Unknown",
            product_type="unknown",
            sub_type="unknown"
        )
    
    # ... 其他提取器方法（保持与之前相同）...
    def _extract_poe_table(self, headers, rows):
        # 保持原有实现
        from .direct_extractor import DirectTableExtractor
        extractor = DirectTableExtractor()
        return extractor._extract_poe_table(headers, rows)
    
    def _extract_software_table(self, headers, rows):
        from .direct_extractor import DirectTableExtractor
        extractor = DirectTableExtractor()
        return extractor._extract_software_table(headers, rows)
    
    def _extract_performance_table(self, headers, rows):
        from .direct_extractor import DirectTableExtractor
        extractor = DirectTableExtractor()
        return extractor._extract_performance_table(headers, rows)
    
    def _extract_protocols_table(self, headers, rows):
        from .direct_extractor import DirectTableExtractor
        extractor = DirectTableExtractor()
        return extractor._extract_protocols_table(headers, rows)
    
    def _extract_multi_model_table(self, headers, rows):
        from .direct_extractor import DirectTableExtractor
        extractor = DirectTableExtractor()
        return extractor._extract_multi_model_table(headers, rows)
    
    def _extract_generic_table(self, headers, rows):
        from .direct_extractor import DirectTableExtractor
        extractor = DirectTableExtractor()
        return extractor._extract_generic_table(headers, rows)
    
    def get_analysis_report(self) -> Optional[PageAnalysisReport]:
        """获取分析报告"""
        return self.analysis_report
    
    def generate_profile_template(self) -> str:
        """生成配置模板"""
        if self.analysis_report:
            return self.analyzer.generate_config_template(self.analysis_report)
        return ""


# 便捷函数
def extract_specs(html: str, url: str = "", profile: str = None) -> Dict[str, Dict]:
    """便捷提取函数"""
    extractor = UniversalExtractor(profile_name=profile)
    return extractor.extract(html, url)
