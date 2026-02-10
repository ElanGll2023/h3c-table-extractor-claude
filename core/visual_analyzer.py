"""
Visual Structure Analyzer - 视觉结构分析器
从DOM结构、CSS样式、视觉层级等多维度分析页面
"""

import re
import json
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from bs4 import BeautifulSoup, Tag
from collections import defaultdict


@dataclass
class VisualBlock:
    """视觉区块"""
    block_type: str  # 'header', 'section', 'table', 'list', 'text'
    tag_name: str
    css_classes: List[str]
    text_content: str
    element_id: Optional[str]
    depth: int  # DOM深度
    sibling_index: int
    
    # 视觉特征
    font_size: Optional[str] = None
    font_weight: Optional[str] = None
    color: Optional[str] = None
    background_color: Optional[str] = None
    
    # 语义特征
    is_heading: bool = False
    heading_level: int = 0
    is_list: bool = False
    is_table: bool = False
    
    # 内容统计
    char_count: int = 0
    word_count: int = 0
    number_count: int = 0
    model_mentions: List[str] = field(default_factory=list)
    param_mentions: List[str] = field(default_factory=list)


@dataclass
class ContentRegion:
    """内容区域 - 语义上的内容区块"""
    region_id: str
    region_type: str  # 'specifications', 'features', 'overview', 'models', 'unknown'
    title: Optional[str]
    heading_element: Optional[Tag]
    start_depth: int
    end_depth: int
    blocks: List[VisualBlock]
    
    # 统计信息
    table_count: int = 0
    list_count: int = 0
    text_block_count: int = 0
    model_names: Set[str] = field(default_factory=set)
    param_keywords: Set[str] = field(default_factory=set)


@dataclass
class TableStructure:
    """表格结构分析"""
    table_index: int
    table_type: str  # 检测到的类型
    type_confidence: float
    
    # 结构特征
    row_count: int
    col_count: int
    has_header: bool
    has_rowspan: bool
    has_colspan: bool
    
    # 内容特征
    headers: List[str]
    first_col_type: str  # 'index', 'feature', 'model', 'category'
    data_orientation: str  # 'row-wise', 'column-wise', 'matrix'
    
    # 语义特征
    contains_models: bool
    contains_numbers: bool
    contains_ports: bool
    contains_performance: bool
    
    # 样本数据
    sample_cells: List[List[str]]
    
    # 建议
    suggested_extractor: str
    suggested_mappings: List[Dict]


@dataclass
class SemanticPattern:
    """语义模式"""
    pattern_type: str  # 'model_naming', 'param_format', 'value_format', 'section_divider'
    pattern: str
    confidence: float
    examples: List[str]
    suggestion: str


class VisualStructureAnalyzer:
    """视觉结构分析器"""
    
    # 产品型号命名模式
    MODEL_PATTERNS = [
        r'S\d{4}[A-Z]*-[\w-]+',  # H3C S5130S-28P-EI
        r'[A-Z]{2,}\d{3,}[A-Z]*-?[\w-]*',  # 通用型号格式
        r'\d{4}[A-Z]\d{2}[A-Z]*',  # 数字字母混合
    ]
    
    # 参数关键词
    PARAM_KEYWORDS = {
        'performance': ['capacity', 'forwarding', 'throughput', 'bandwidth', 'rate', '交换容量', '转发率'],
        'port': ['port', 'sfp', 'qsfp', 'ethernet', 'base-t', '光口', '电口', '端口'],
        'physical': ['dimension', 'weight', 'size', '尺寸', '重量'],
        'power': ['power', 'poe', 'watt', '功耗', '电源'],
        'memory': ['mac', 'vlan', 'routing', 'arp', 'table', 'entries', '表项'],
        'management': ['console', 'usb', 'management', 'console口', '管理'],
    }
    
    # 表格类型特征
    TABLE_TYPE_FEATURES = {
        'hardware_spec': {
            'keywords': ['switching capacity', 'forwarding', 'dimension', 'weight', 'port'],
            'headers': ['feature', 'attribute', 'specification'],
            'indicators': ['型号', '规格', '参数']
        },
        'model_comparison': {
            'keywords': ['model', 'port', 'interface'],
            'headers': ['model', '端口', '型号'],
            'indicators': ['多型号', '对比']
        },
        'software_features': {
            'keywords': ['vlan', 'routing', 'multicast', 'security'],
            'headers': ['feature', 'description'],
            'indicators': ['软件', '特性', '功能']
        },
        'performance_metrics': {
            'keywords': ['entries', 'table', 'mac', 'vlan', 'routing'],
            'headers': ['entries', 'capacity', 'performance'],
            'indicators': ['性能', '表项', '容量']
        },
        'poe_power': {
            'keywords': ['poe', 'power', 'watt', '802.3'],
            'headers': ['model', 'power', 'quantity'],
            'indicators': ['POE', '供电']
        },
        'protocols': {
            'keywords': ['ieee', 'rfc', 'standard', 'protocol'],
            'headers': ['organization', 'standard', 'protocol'],
            'indicators': ['协议', '标准']
        },
    }
    
    def __init__(self):
        self.soup: Optional[BeautifulSoup] = None
        self.url: str = ""
        self.blocks: List[VisualBlock] = []
        self.regions: List[ContentRegion] = []
        self.tables: List[TableStructure] = []
        self.patterns: List[SemanticPattern] = []
        
    def analyze(self, html: str, url: str = "") -> Dict:
        """执行完整的视觉结构分析"""
        self.url = url
        self.soup = BeautifulSoup(html, 'lxml')
        
        # 1. 提取所有视觉区块
        self._extract_visual_blocks()
        
        # 2. 识别内容区域
        self._identify_content_regions()
        
        # 3. 深度分析表格
        self._analyze_tables()
        
        # 4. 发现语义模式
        self._discover_semantic_patterns()
        
        # 5. 生成综合分析报告
        return self._generate_report()
    
    def _extract_visual_blocks(self):
        """提取页面中的所有视觉区块"""
        self.blocks = []
        
        # 遍历所有元素
        for idx, elem in enumerate(self.soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 
                                                        'section', 'div', 'table', 'ul', 'ol', 
                                                        'p', 'span', 'strong', 'b'])):
            if not elem.get_text(strip=True):
                continue
            
            # 计算DOM深度
            depth = len(list(elem.parents))
            
            # 提取CSS类
            css_classes = elem.get('class', [])
            if isinstance(css_classes, str):
                css_classes = css_classes.split()
            
            # 提取文本内容
            text = elem.get_text(strip=True)
            
            # 检测是否为标题
            is_heading = elem.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']
            heading_level = int(elem.name[1]) if is_heading else 0
            
            # 检测内容类型
            is_table = elem.name == 'table'
            is_list = elem.name in ['ul', 'ol']
            
            # 统计内容
            char_count = len(text)
            word_count = len(text.split())
            numbers = re.findall(r'\d+', text)
            number_count = len(numbers)
            
            # 检测型号提及
            model_mentions = []
            for pattern in self.MODEL_PATTERNS:
                matches = re.findall(pattern, text)
                model_mentions.extend(matches)
            
            # 检测参数提及
            param_mentions = []
            for category, keywords in self.PARAM_KEYWORDS.items():
                for kw in keywords:
                    if kw.lower() in text.lower():
                        param_mentions.append((category, kw))
            
            block = VisualBlock(
                block_type=self._classify_block_type(elem, text),
                tag_name=elem.name,
                css_classes=css_classes,
                text_content=text[:200],  # 限制长度
                element_id=elem.get('id'),
                depth=depth,
                sibling_index=idx,
                is_heading=is_heading,
                heading_level=heading_level,
                is_list=is_list,
                is_table=is_table,
                char_count=char_count,
                word_count=word_count,
                number_count=number_count,
                model_mentions=model_mentions,
                param_mentions=param_mentions
            )
            
            self.blocks.append(block)
    
    def _classify_block_type(self, elem: Tag, text: str) -> str:
        """分类区块类型"""
        if elem.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            return 'header'
        elif elem.name == 'table':
            return 'table'
        elif elem.name in ['ul', 'ol']:
            return 'list'
        elif elem.name == 'section':
            return 'section'
        elif len(text) < 100:
            return 'text'
        else:
            return 'content'
    
    def _identify_content_regions(self):
        """识别内容区域"""
        self.regions = []
        current_region = None
        region_counter = 0
        
        for block in self.blocks:
            # 如果是标题，可能是新区域的开始
            if block.is_heading:
                # 保存当前区域
                if current_region:
                    self.regions.append(current_region)
                
                # 创建新区域
                region_counter += 1
                region_type = self._classify_region_type(block)
                
                current_region = ContentRegion(
                    region_id=f"region_{region_counter}",
                    region_type=region_type,
                    title=block.text_content,
                    heading_element=None,  # 简化处理
                    start_depth=block.depth,
                    end_depth=block.depth,
                    blocks=[block],
                    model_names=set(block.model_mentions),
                    param_keywords=set(p[1] for p in block.param_mentions)
                )
            else:
                # 添加到当前区域
                if current_region:
                    current_region.blocks.append(block)
                    current_region.end_depth = max(current_region.end_depth, block.depth)
                    current_region.model_names.update(block.model_mentions)
                    current_region.param_keywords.update(p[1] for p in block.param_mentions)
                    
                    if block.is_table:
                        current_region.table_count += 1
                    elif block.is_list:
                        current_region.list_count += 1
                    else:
                        current_region.text_block_count += 1
        
        # 保存最后一个区域
        if current_region:
            self.regions.append(current_region)
    
    def _classify_region_type(self, block: VisualBlock) -> str:
        """分类区域类型"""
        text = block.text_content.lower()
        
        # 检查标题关键词
        if any(kw in text for kw in ['specification', 'hardware', 'software', 'performance', 
                                      '规格', '硬件', '软件', '性能']):
            return 'specifications'
        elif any(kw in text for kw in ['feature', 'characteristic', 'advantage',
                                        '特性', '特点', '优势']):
            return 'features'
        elif any(kw in text for kw in ['overview', 'introduction', 'description',
                                        '概述', '简介', '介绍']):
            return 'overview'
        elif any(kw in text for kw in ['model', 'product', 'series',
                                        '型号', '产品', '系列']):
            return 'models'
        
        return 'unknown'
    
    def _analyze_tables(self):
        """深度分析所有表格"""
        tables = self.soup.find_all('table')
        
        for idx, table in enumerate(tables):
            structure = self._analyze_single_table(table, idx)
            if structure:
                self.tables.append(structure)
    
    def _analyze_single_table(self, table: Tag, index: int) -> Optional[TableStructure]:
        """分析单个表格"""
        text = table.get_text(strip=True)
        if len(text) < 200:
            return None
        
        # 提取表头
        headers = []
        header_row = table.find('thead')
        if header_row:
            headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
        else:
            first_row = table.find('tr')
            if first_row:
                headers = [cell.get_text(strip=True) for cell in first_row.find_all(['th', 'td'])]
        
        col_count = len(headers)
        
        # 统计行数
        rows = table.find_all('tr')[1:] if headers else table.find_all('tr')
        row_count = len(rows)
        
        # 检测合并单元格
        has_rowspan = bool(table.find(attrs={'rowspan': True}))
        has_colspan = bool(table.find(attrs={'colspan': True}))
        
        # 分析第一列类型
        first_col_type = self._analyze_first_column(rows, headers)
        
        # 分析数据方向
        data_orientation = self._analyze_data_orientation(rows, headers)
        
        # 检测内容特征
        full_text = table.get_text().lower()
        contains_models = any(re.search(p, full_text) for p in self.MODEL_PATTERNS)
        contains_numbers = bool(re.search(r'\d+\s*(gbps|mhz|w|v)', full_text))
        contains_ports = any(kw in full_text for kw in ['port', 'sfp', 'ethernet', 'base-t'])
        contains_performance = any(kw in full_text for kw in ['capacity', 'forwarding', 'entries'])
        
        # 获取样本数据
        sample_cells = []
        for row in rows[:3]:
            cells = row.find_all(['td', 'th'])
            sample_cells.append([cell.get_text(strip=True)[:50] for cell in cells[:5]])
        
        # 检测表格类型
        table_type, confidence = self._detect_table_type(table, headers, full_text)
        
        # 生成映射建议
        suggested_mappings = self._suggest_param_mappings(rows, headers)
        
        return TableStructure(
            table_index=index,
            table_type=table_type,
            type_confidence=confidence,
            row_count=row_count,
            col_count=col_count,
            has_header=bool(headers),
            has_rowspan=has_rowspan,
            has_colspan=has_colspan,
            headers=headers,
            first_col_type=first_col_type,
            data_orientation=data_orientation,
            contains_models=contains_models,
            contains_numbers=contains_numbers,
            contains_ports=contains_ports,
            contains_performance=contains_performance,
            sample_cells=sample_cells,
            suggested_extractor=self._suggest_extractor(table_type),
            suggested_mappings=suggested_mappings
        )
    
    def _analyze_first_column(self, rows, headers) -> str:
        """分析第一列类型"""
        if not rows:
            return 'unknown'
        
        first_cells = []
        for row in rows[:10]:
            cells = row.find_all(['td', 'th'])
            if cells:
                first_cells.append(cells[0].get_text(strip=True))
        
        # 检查是否为型号
        model_count = sum(1 for cell in first_cells if any(re.search(p, cell) for p in self.MODEL_PATTERNS))
        if model_count > len(first_cells) * 0.5:
            return 'model'
        
        # 检查是否为特征/参数名
        if any(kw in ' '.join(first_cells).lower() for kw in ['port', 'capacity', 'dimension', 'power']):
            return 'feature'
        
        # 检查是否为序号
        if all(re.match(r'^\d+$', cell) for cell in first_cells[:5]):
            return 'index'
        
        return 'category'
    
    def _analyze_data_orientation(self, rows, headers) -> str:
        """分析数据方向"""
        if len(headers) <= 2:
            return 'row-wise'
        
        # 如果第一列看起来是特征名，数据是横向的
        return 'row-wise'
    
    def _detect_table_type(self, table: Tag, headers: List[str], text: str) -> Tuple[str, float]:
        """检测表格类型"""
        text_lower = text.lower()
        header_str = ' '.join(h.lower() for h in headers)
        
        scores = {}
        for table_type, features in self.TABLE_TYPE_FEATURES.items():
            score = 0
            
            # 关键词匹配
            for kw in features['keywords']:
                if kw in text_lower:
                    score += 2
            
            # 表头匹配
            for h in features['headers']:
                if h in header_str:
                    score += 3
            
            scores[table_type] = score
        
        if scores:
            best_type = max(scores, key=scores.get)
            best_score = scores[best_type]
            confidence = min(best_score / 10, 1.0)
            return best_type, confidence
        
        return 'unknown', 0.3
    
    def _suggest_extractor(self, table_type: str) -> str:
        """建议提取器类型"""
        extractor_map = {
            'hardware_spec': 'multi_model_hardware',
            'model_comparison': 'multi_model_hardware',
            'software_features': 'software',
            'performance_metrics': 'performance',
            'poe_power': 'poe_power',
            'protocols': 'protocols',
        }
        return extractor_map.get(table_type, 'generic')
    
    def _suggest_param_mappings(self, rows, headers) -> List[Dict]:
        """建议参数映射"""
        mappings = []
        
        if not rows or not headers:
            return mappings
        
        # 分析第一列的特征名
        for row in rows[:10]:
            cells = row.find_all(['td', 'th'])
            if cells:
                feature_name = cells[0].get_text(strip=True)
                if feature_name:
                    # 尝试匹配已知参数
                    suggested_mapping = self._match_param_pattern(feature_name)
                    if suggested_mapping:
                        mappings.append({
                            'original': feature_name,
                            'suggested': suggested_mapping,
                            'confidence': 'high'
                        })
        
        return mappings
    
    def _match_param_pattern(self, param_name: str) -> Optional[str]:
        """匹配参数模式"""
        param_lower = param_name.lower()
        
        # 常见参数映射
        mappings = {
            r'port\s*switching\s*capacity': '交换容量',
            r'forwarding\s*rate': '包转发率',
            r'mac\s*address': 'MAC地址表',
            r'vlan\s*table': 'VLAN表项',
            r'dimension': '尺寸',
            r'weight': '重量',
            r'power\s*supply': '电源槽位数',
        }
        
        for pattern, chinese in mappings.items():
            if re.search(pattern, param_lower):
                return chinese
        
        return None
    
    def _discover_semantic_patterns(self):
        """发现语义模式"""
        self.patterns = []
        
        # 1. 型号命名模式
        all_models = set()
        for block in self.blocks:
            all_models.update(block.model_mentions)
        
        if all_models:
            self.patterns.append(SemanticPattern(
                pattern_type='model_naming',
                pattern=r'S\d{4}[A-Z]*-[\w-]+',
                confidence=0.9,
                examples=list(all_models)[:5],
                suggestion='检测到H3C型号命名模式'
            ))
        
        # 2. 参数格式模式
        # 分析数值格式
        value_patterns = defaultdict(int)
        for block in self.blocks:
            numbers = re.findall(r'(\d+)\s*(Gbps|MHz|W|V|GB)', block.text_content)
            for num, unit in numbers:
                value_patterns[f'{num}{unit}'] += 1
        
        if value_patterns:
            self.patterns.append(SemanticPattern(
                pattern_type='value_format',
                pattern=r'\d+\s*(Gbps|MHz|W|V|GB)',
                confidence=0.85,
                examples=list(value_patterns.keys())[:5],
                suggestion='检测到标准数值单位格式'
            ))
    
    def _generate_report(self) -> Dict:
        """生成综合分析报告"""
        return {
            'summary': {
                'total_blocks': len(self.blocks),
                'content_regions': len(self.regions),
                'tables_found': len(self.tables),
                'patterns_discovered': len(self.patterns),
            },
            'content_regions': [
                {
                    'id': r.region_id,
                    'type': r.region_type,
                    'title': r.title,
                    'block_count': len(r.blocks),
                    'table_count': r.table_count,
                    'model_names': list(r.model_names)[:10],
                    'param_keywords': list(r.param_keywords)[:10]
                }
                for r in self.regions
            ],
            'table_analysis': [
                {
                    'index': t.table_index,
                    'type': t.table_type,
                    'confidence': t.type_confidence,
                    'dimensions': f"{t.row_count}x{t.col_count}",
                    'structure': {
                        'has_rowspan': t.has_rowspan,
                        'has_colspan': t.has_colspan,
                        'first_col_type': t.first_col_type,
                        'data_orientation': t.data_orientation
                    },
                    'content_features': {
                        'contains_models': t.contains_models,
                        'contains_numbers': t.contains_numbers,
                        'contains_ports': t.contains_ports,
                        'contains_performance': t.contains_performance
                    },
                    'headers': t.headers,
                    'sample_data': t.sample_cells,
                    'suggested_extractor': t.suggested_extractor,
                    'suggested_mappings': t.suggested_mappings
                }
                for t in self.tables
            ],
            'semantic_patterns': [
                {
                    'type': p.pattern_type,
                    'pattern': p.pattern,
                    'confidence': p.confidence,
                    'examples': p.examples,
                    'suggestion': p.suggestion
                }
                for p in self.patterns
            ],
            'recommendations': self._generate_recommendations()
        }
    
    def _generate_recommendations(self) -> List[Dict]:
        """生成配置建议"""
        recommendations = []
        
        # 表格类型建议
        for table in self.tables:
            if table.type_confidence < 0.7:
                recommendations.append({
                    'priority': 'high',
                    'category': 'table_detection',
                    'message': f'表格 {table.table_index} 类型不确定，建议人工确认',
                    'current_guess': table.table_type,
                    'confidence': table.type_confidence,
                    'headers': table.headers,
                    'action': 'review_table_type'
                })
        
        # 参数映射建议
        for table in self.tables:
            for mapping in table.suggested_mappings:
                if mapping.get('confidence') == 'high':
                    recommendations.append({
                        'priority': 'medium',
                        'category': 'param_mapping',
                        'message': f"建议映射参数: {mapping['original']} -> {mapping['suggested']}",
                        'action': 'add_mapping_rule'
                    })
        
        # 结构建议
        if any(r.region_type == 'unknown' for r in self.regions):
            recommendations.append({
                'priority': 'low',
                'category': 'structure',
                'message': '部分内容区域类型不确定，建议检查页面结构',
                'action': 'review_structure'
            })
        
        return recommendations
