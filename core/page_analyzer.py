"""
页面结构分析器 - 自动分析新产品页面，生成规则建议
"""

import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from bs4 import BeautifulSoup


@dataclass
class TableAnalysis:
    """表格分析结果"""
    index: int
    table_type: str
    headers: List[str]
    row_count: int
    has_rowspan: bool
    has_colspan: bool
    sample_data: List[Dict]
    suggested_extractor: str
    confidence: float


@dataclass
class ParameterDiscovery:
    """参数发现结果"""
    original_name: str
    frequency: int
    sample_values: List[str]
    suggested_mapping: Optional[str]
    suggested_category: str
    value_type: str  # 'number', 'string', 'enum'


@dataclass
class PageAnalysisReport:
    """页面分析报告"""
    url: str
    detected_tables: List[TableAnalysis]
    discovered_params: List[ParameterDiscovery]
    suggested_profile: Optional[str]
    suggested_rules: List[Dict]
    missing_patterns: List[str]
    confidence: float


class PageAnalyzer:
    """页面结构分析器"""
    
    # 已知表格类型特征
    TABLE_PATTERNS = {
        'protocols': {
            'keywords': ['organization', 'ieee', 'standard', 'protocol', 'compliance'],
            'headers': ['organization', 'standards'],
            'extractor': 'protocols'
        },
        'poe_power': {
            'keywords': ['poe', 'power capacity', '802.3af', '802.3at', 'quantity'],
            'headers': ['model', 'power', 'quantity'],
            'extractor': 'poe_power'
        },
        'software': {
            'keywords': ['software', 'feature', 'vlan', 'routing', 'multicast'],
            'headers': ['feature', 'description', 'specification'],
            'extractor': 'software'
        },
        'performance': {
            'keywords': ['entries', 'mac address', 'vlan table', 'routing', 'performance'],
            'headers': ['entries', 'table', 'capacity'],
            'extractor': 'performance'
        },
        'hardware_multi': {
            'keywords': ['port', 'switching capacity', 'feature', 'model'],
            'headers': ['feature', 'port', 'model'],
            'extractor': 'multi_model_hardware'
        },
        'hardware_single': {
            'keywords': ['specification', 'attribute', 'value'],
            'headers': ['attribute', 'value', 'specification'],
            'extractor': 'single_model_hardware'
        }
    }
    
    # 已知参数分类
    PARAM_CATEGORIES = {
        'performance': ['switching capacity', 'forwarding', 'mac', 'vlan', 'routing', 'arp'],
        'port': ['port', 'sfp', 'qsfp', 'base-t', 'ethernet', 'combo'],
        'physical': ['dimension', 'weight', 'temperature', 'humidity'],
        'power': ['power', 'poe', 'supply', 'consumption'],
        'management': ['console', 'usb', 'management', 'port'],
        'hardware': ['cpu', 'memory', 'flash', 'sdram']
    }
    
    def __init__(self):
        self.discovered_params: Dict[str, ParameterDiscovery] = {}
    
    def analyze(self, html: str, url: str) -> PageAnalysisReport:
        """分析页面结构"""
        soup = BeautifulSoup(html, 'lxml')
        tables = soup.find_all('table')
        
        # 分析表格
        table_analyses = []
        for i, table in enumerate(tables):
            analysis = self._analyze_table(table, i)
            if analysis:
                table_analyses.append(analysis)
        
        # 发现参数
        self._discover_parameters(soup, table_analyses)
        
        # 推荐配置
        suggested_profile = self._suggest_profile(url, table_analyses)
        
        # 生成规则建议
        suggested_rules = self._generate_rule_suggestions(table_analyses)
        
        # 计算置信度
        confidence = self._calculate_confidence(table_analyses, suggested_profile)
        
        return PageAnalysisReport(
            url=url,
            detected_tables=table_analyses,
            discovered_params=list(self.discovered_params.values()),
            suggested_profile=suggested_profile,
            suggested_rules=suggested_rules,
            missing_patterns=[],
            confidence=confidence
        )
    
    def _analyze_table(self, table, index: int) -> Optional[TableAnalysis]:
        """分析单个表格"""
        text = table.get_text(strip=True)
        if len(text) < 200:  # 跳过小表格
            return None
        
        # 解析表头
        headers = []
        header_row = table.find('thead')
        if header_row:
            headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
        else:
            first_row = table.find('tr')
            if first_row:
                headers = [cell.get_text(strip=True) for cell in first_row.find_all(['th', 'td'])]
        
        # 检测表格类型
        table_type, extractor, confidence = self._detect_table_type(text, headers)
        
        # 检测合并单元格
        has_rowspan = bool(table.find(attrs={'rowspan': True}))
        has_colspan = bool(table.find(attrs={'colspan': True}))
        
        # 统计行数
        rows = table.find_all('tr')
        row_count = len(rows) - 1  # 减去表头
        
        # 采样数据
        sample_data = []
        for row in rows[1:4]:  # 取前3行数据
            cells = row.find_all(['td', 'th'])
            row_data = {}
            for i, cell in enumerate(cells):
                if i < len(headers):
                    row_data[headers[i]] = cell.get_text(strip=True)[:100]
            if row_data:
                sample_data.append(row_data)
        
        return TableAnalysis(
            index=index,
            table_type=table_type,
            headers=headers,
            row_count=row_count,
            has_rowspan=has_rowspan,
            has_colspan=has_colspan,
            sample_data=sample_data,
            suggested_extractor=extractor,
            confidence=confidence
        )
    
    def _detect_table_type(self, text: str, headers: List[str]) -> tuple:
        """检测表格类型"""
        text_lower = text.lower()
        header_str = ' '.join(h.lower() for h in headers)
        
        scores = {}
        for table_type, pattern in self.TABLE_PATTERNS.items():
            score = 0
            # 关键词匹配
            for kw in pattern['keywords']:
                if kw in text_lower:
                    score += 2
            # 表头匹配
            for h in pattern['headers']:
                if h in header_str:
                    score += 3
            scores[table_type] = score
        
        if scores:
            best_type = max(scores, key=scores.get)
            best_score = scores[best_type]
            confidence = min(best_score / 10, 1.0)  # 归一化
            extractor = self.TABLE_PATTERNS[best_type]['extractor']
            return best_type, extractor, confidence
        
        return 'unknown', 'generic', 0.3
    
    def _discover_parameters(self, soup: BeautifulSoup, tables: List[TableAnalysis]):
        """发现页面中的参数"""
        for table_analysis in tables:
            if table_analysis.table_type == 'hardware_multi':
                # 从硬件表中提取参数名
                for sample in table_analysis.sample_data:
                    feature = sample.get(table_analysis.headers[0], '')
                    if feature:
                        self._add_discovered_param(feature, sample)
    
    def _add_discovered_param(self, name: str, sample_row: Dict):
        """添加发现的参数"""
        name_normalized = name.lower().strip()
        
        if name_normalized in self.discovered_params:
            self.discovered_params[name_normalized].frequency += 1
        else:
            # 推测分类和类型
            category = self._guess_category(name_normalized)
            value_type = self._guess_value_type(name_normalized, sample_row)
            suggested_mapping = self._suggest_mapping(name_normalized)
            
            self.discovered_params[name_normalized] = ParameterDiscovery(
                original_name=name,
                frequency=1,
                sample_values=[],
                suggested_mapping=suggested_mapping,
                suggested_category=category,
                value_type=value_type
            )
    
    def _guess_category(self, param_name: str) -> str:
        """推测参数分类"""
        for category, keywords in self.PARAM_CATEGORIES.items():
            for kw in keywords:
                if kw in param_name:
                    return category
        return 'other'
    
    def _guess_value_type(self, param_name: str, sample: Dict) -> str:
        """推测值类型"""
        # 根据值的内容判断
        for key, value in sample.items():
            if key != param_name and value:
                if re.match(r'^\d+$', value):
                    return 'number'
                elif re.match(r'^\d+\s*[KMG]?(bps|Hz)?$', value, re.I):
                    return 'number_with_unit'
                elif ';' in value or ',' in value:
                    return 'list'
        return 'string'
    
    def _suggest_mapping(self, param_name: str) -> Optional[str]:
        """建议中文映射"""
        # 常见映射
        mappings = {
            'port switching capacity': '交换容量',
            'forwarding rate': '包转发率',
            'mac address entries': 'MAC地址表',
            'vlan table': 'VLAN表项',
            'dimensions': '尺寸',
            'weight': '重量',
            'power supply slots': '电源槽位数',
            'fan number': '风扇数量',
        }
        
        for en, cn in mappings.items():
            if en in param_name:
                return cn
        return None
    
    def _suggest_profile(self, url: str, tables: List[TableAnalysis]) -> Optional[str]:
        """推荐配置文件"""
        url_lower = url.lower()
        
        # URL模式匹配
        if any(x in url_lower for x in ['s125', 's105', 's76', 'chassis']):
            return 'H3C-Switch-Chassis'
        elif any(x in url_lower for x in ['s5130', 's5590', 's6520', 's5560']):
            return 'H3C-Switch-Box'
        
        # 根据表格结构判断
        has_chassis_params = any(
            t.table_type == 'hardware_multi' and 
            any('slot' in h.lower() for h in t.headers)
            for t in tables
        )
        if has_chassis_params:
            return 'H3C-Switch-Chassis'
        
        return 'H3C-Switch-Box'  # 默认
    
    def _generate_rule_suggestions(self, tables: List[TableAnalysis]) -> List[Dict]:
        """生成规则建议"""
        suggestions = []
        
        for table in tables:
            if table.confidence < 0.5:
                suggestions.append({
                    'type': 'table_detection',
                    'priority': 'medium',
                    'message': f'Table {table.index} type uncertain',
                    'current_guess': table.table_type,
                    'sample_headers': table.headers[:3],
                    'action': 'review_and_confirm'
                })
        
        # 未映射的参数建议
        for param in self.discovered_params.values():
            if not param.suggested_mapping:
                suggestions.append({
                    'type': 'param_mapping',
                    'priority': 'high',
                    'message': f'New parameter discovered: {param.original_name}',
                    'category': param.suggested_category,
                    'sample_values': param.sample_values[:3],
                    'action': 'create_mapping_rule'
                })
        
        return suggestions
    
    def _calculate_confidence(self, tables: List[TableAnalysis], profile: str) -> float:
        """计算整体置信度"""
        if not tables:
            return 0.0
        
        avg_table_confidence = sum(t.confidence for t in tables) / len(tables)
        profile_confidence = 0.8 if profile else 0.4
        
        return (avg_table_confidence + profile_confidence) / 2
    
    def generate_config_template(self, report: PageAnalysisReport) -> str:
        """根据分析报告生成配置模板"""
        lines = [
            f"# Auto-generated profile for {report.url}",
            f"name: \"Custom-Profile-{report.url.split('/')[-2]}\"",
            "brand: \"H3C\"",
            f"product_type: \"switch\"",
            f"sub_type: \"unknown\"",
            "version: \"1.0\"",
            f"parent_profile: \"{report.suggested_profile or 'H3C-Switch-Box'}\"",
            "",
            "# Discovered parameters needing mapping:",
        ]
        
        for param in report.discovered_params:
            if not param.suggested_mapping:
                lines.append(f"# - {param.original_name} ({param.suggested_category})")
        
        lines.extend([
            "",
            "# Suggested table detection rules:",
        ])
        
        for table in report.detected_tables:
            if table.confidence < 0.8:
                lines.append(f"# Table {table.index}: {table.table_type} (confidence: {table.confidence:.2f})")
                lines.append(f"#   Headers: {table.headers}")
        
        return '\n'.join(lines)
