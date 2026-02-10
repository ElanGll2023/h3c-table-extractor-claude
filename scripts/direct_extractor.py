#!/usr/bin/env python3
"""
Direct LLM table processing - uses current agent's capabilities
"""
import json
import re
from typing import Dict, List, Optional, Tuple
from bs4 import BeautifulSoup, Tag


class DirectTableExtractor:
    """
    Extracts tables by preparing them for LLM analysis.
    In OpenClaw, the agent (me) processes these directly.
    """
    
    def __init__(self):
        self.results = {}
        # Parameters to skip (removable components, board support, etc.)
        self.skip_patterns = [
            r'removable', r'power supply model', r'psu model', 
            r'board support', r'card support', r'是否支持',
            r'电源模块型号', r'可移除'
        ]
    
    def extract_all_tables(self, html_content: str, page_url: str = "") -> Dict[str, Dict]:
        """
        Extract all tables from HTML.
        
        Returns dict of {model_name: {param: value}}
        """
        soup = BeautifulSoup(html_content, 'lxml')
        tables = soup.find_all('table')
        
        all_data = {}
        series_data = {}  # Store series-level info (software, protocols, etc.)
        
        for i, table in enumerate(tables):
            table_data = self._process_table(table, i, page_url)
            if table_data:
                # Separate series-level data from model-specific data
                for model_name, specs in table_data.items():
                    if not specs:  # Skip empty entries
                        continue
                    # Check if this is a series-level entry
                    if 'Series' in model_name or 'Protocols' in model_name or model_name.startswith(('RFC', 'IEEE', 'ITU', 'IETF')):
                        series_data[model_name] = specs
                    else:
                        if model_name not in all_data:
                            all_data[model_name] = {}
                        all_data[model_name].update(specs)
        
        # Merge series-level data into all models
        # Find common series prefix
        if series_data and all_data:
            # Try to identify series from model names
            series_keys = list(series_data.keys())
            model_keys = [k for k in all_data.keys() if k.startswith(('S5130', 'S5590', 'S6520', 'S5560', 'S125', 'S105', 'S76', 'S75'))]
            
            if model_keys:
                # Extract series prefix (e.g., "S5130" from "S5130S-28P-EI")
                first_model = model_keys[0]
                series_prefix = ''
                for prefix in ['S5130S-EI', 'S5130S', 'S5130', 'S5590', 'S6520', 'S5560', 'S125', 'S105', 'S76', 'S75']:
                    if first_model.startswith(prefix):
                        series_prefix = prefix
                        break
                
                # Merge matching series data
                for series_key, series_specs in series_data.items():
                    if series_prefix and series_prefix in series_key:
                        for model_name in model_keys:
                            all_data[model_name].update(series_specs)
                    elif 'Protocols' in series_key:
                        # Protocols apply to all models
                        for model_name in model_keys:
                            all_data[model_name].update(series_specs)
        
        return all_data
    
    def _process_table(self, table: Tag, index: int, page_url: str) -> Optional[Dict[str, Dict]]:
        """Process a single table."""
        # Get table text for classification
        text = table.get_text(strip=True)
        
        # Skip small/nav tables
        if len(text) < 200:
            return None
        
        # Detect table type
        table_type = self._detect_table_type(text)
        
        # Parse table structure
        headers, rows = self._parse_table_structure(table)
        
        if not headers or not rows:
            return None
        
        # Handle based on table type
        if table_type == 'poe':
            return self._extract_poe_table(headers, rows)
        elif table_type == 'software':
            return self._extract_software_table(headers, rows)
        elif table_type == 'performance':
            return self._extract_performance_table(headers, rows)
        elif table_type == 'protocols':
            return self._extract_protocols_table(headers, rows)
        elif len(headers) > 2 and self._is_multi_model_table(headers):
            return self._extract_multi_model_table(headers, rows)
        else:
            return self._extract_generic_table(headers, rows)
    
    def _detect_table_type(self, text: str) -> str:
        """Detect table type from content."""
        text_lower = text.lower()
        
        if any(x in text_lower for x in ['poe', '802.3af', '802.3at', 'power capacity']):
            return 'poe'
        elif any(x in text_lower for x in ['vlan', 'routing protocol', 'security feature']):
            return 'software'
        elif any(x in text_lower for x in ['ieee', 'rfc', 'standard', 'compliance']):
            return 'protocols'
        elif any(x in text_lower for x in ['mac address', 'forwarding rate', 'routing table']):
            return 'performance'
        else:
            return 'hardware'
    
    def _parse_table_structure(self, table: Tag) -> Tuple[List[str], List[Dict]]:
        """Parse table into headers and rows."""
        # Find headers
        thead = table.find('thead')
        if thead:
            header_row = thead.find('tr')
        else:
            header_row = table.find('tr')
        
        if not header_row:
            return [], []
        
        headers = []
        for th in header_row.find_all(['th', 'td']):
            headers.append(th.get_text(strip=True))
        
        # Find data rows
        rows = []
        tbody = table.find('tbody')
        if tbody:
            data_rows = tbody.find_all('tr')
        else:
            data_rows = table.find_all('tr')[1:]  # Skip header
        
        for tr in data_rows:
            row_data = {}
            cells = tr.find_all(['td', 'th'])
            
            for i, cell in enumerate(cells):
                if i < len(headers):
                    # Handle colspan by duplicating value
                    colspan = int(cell.get('colspan', 1))
                    value = cell.get_text(strip=True)
                    for j in range(colspan):
                        if i + j < len(headers):
                            row_data[headers[i + j]] = value
            
            if row_data:
                rows.append(row_data)
        
        return headers, rows
    
    def _is_multi_model_table(self, headers: List[str]) -> bool:
        """Check if table has multiple model columns."""
        # Look for model-like headers (start with S, have numbers)
        model_pattern = re.compile(r'S\d+[\w\-]+')
        return any(model_pattern.search(h) for h in headers)
    
    def _extract_multi_model_table(self, headers: List[str], rows: List[Dict]) -> Dict[str, Dict]:
        """Extract data from multi-model specification table."""
        result = {}
        
        # Identify model columns (those matching SXXXX pattern)
        model_cols = []
        feature_col = headers[0]
        
        for h in headers[1:]:
            if re.search(r'S\d+[\w\-]+', h):
                model_cols.append(h)
        
        # Initialize result for each model
        for model in model_cols:
            result[model] = {}
        
        # Extract data
        for row in rows:
            feature = row.get(feature_col, '')
            if not feature:
                continue
            
            # Skip unwanted parameters
            if self._should_skip_param(feature):
                continue
            
            # Normalize feature name
            norm_feature = self._normalize_param_name(feature)
            if not norm_feature:  # Skip if normalized to None
                continue
            
            for model in model_cols:
                value = row.get(model, '')
                if value and value != '-':
                    # Check if this is a port description
                    if self._is_port_description(feature, value):
                        port_data = self._parse_port_description(feature, value)
                        result[model].update(port_data)
                    else:
                        result[model][norm_feature] = value
        
        return result
    
    def _should_skip_param(self, param: str) -> bool:
        """Check if parameter should be skipped."""
        param_lower = param.lower()
        for pattern in self.skip_patterns:
            if re.search(pattern, param_lower):
                return True
        return False
    
    def _extract_poe_table(self, headers: List[str], rows: List[Dict]) -> Dict[str, Dict]:
        """Extract POE power table with merged cell handling."""
        result = {}
        
        # Find column indices
        model_col = headers[0]
        power_col = None
        ports_col = None
        
        for h in headers:
            if 'power' in h.lower() and 'capacity' in h.lower():
                power_col = h
            elif 'port' in h.lower() and 'quantity' in h.lower():
                ports_col = h
        
        last_model = None
        
        for row in rows:
            model = row.get(model_col, '').strip()
            
            # Handle rowspan (empty model means same as last)
            if not model and last_model:
                model = last_model
            elif model:
                last_model = model
            else:
                continue
            
            if model not in result:
                result[model] = {}
            
            # Extract power
            if power_col and power_col in row:
                power = row[power_col]
                # Check if AC/DC designation in power cell
                if 'AC:' in power or 'DC:' in power:
                    result[model]['POE总功率_' + power.split(':')[0].strip()] = power.split(':')[1].strip()
                else:
                    result[model]['POE总功率'] = power
            
            # Extract port quantities
            if ports_col and ports_col in row:
                ports_text = row[ports_col]
                poe_data = self._parse_poe_ports(ports_text)
                result[model].update(poe_data)
        
        return result
    
    def _extract_generic_table(self, headers: List[str], rows: List[Dict]) -> Dict[str, Dict]:
        """Extract generic single-model table."""
        result = {'generic': {}}
        
        for row in rows:
            if len(headers) >= 2:
                key = row.get(headers[0], '')
                value = row.get(headers[1], '')
                if key and not self._should_skip_param(key):
                    norm_key = self._normalize_param_name(key)
                    if norm_key:
                        result['generic'][norm_key] = value
        
        return result
    
    def _normalize_param_name(self, param: str) -> Optional[str]:
        """Normalize parameter name to Chinese."""
        mappings = {
            r'power\s*consumption|功耗|功率': '功耗',
            r'input\s*voltage|额定电压|输入电压': '输入电压',
            r'switching\s*capacity|交换容量': '交换容量',
            r'forwarding\s*(rate|capacity)|包转发率|转发容量': '包转发率',
            r'mac\s*address|mac地址|mac表': 'MAC地址表',
            r'dimension|尺寸|外形尺寸': '尺寸',
            r'weight|重量': '重量',
            r'temperature|工作温度': '工作温度',
            r'humidity|工作湿度|湿度': '工作湿度',
            r'mtbf|平均无故障': 'MTBF',
            r'mttr|平均修复': 'MTTR',
            r'power\s*supply\s*slots?|电源槽位|电源数量|电源槽': '电源槽位数',
            r'fan\s*(num|number|quantity)|风扇槽位|风扇数量|风扇槽|fan num': '风扇数量',
            r'console|console口|串口|console port': 'Console口',
            r'usb|usb口|usb port': 'USB口',
            r'management|管理口|网管口|management port': '管理网口',
            r'flash|flash内存': 'Flash',
            r'sdram|内存|sdram': 'SDRAM',
            r'cpu|处理器': 'CPU',
            r'latency|时延|延迟|latency': '延迟',
            r'packet\s*buffer|包缓存|报文缓存': '包缓存',
            r'jumbo\s*frame|巨帧': '巨帧',
            r'buffer|缓存|缓冲区': '缓存',
            r'base-t\s*port|电口|以太网口': '电口数量',
            r'sfp\s*port|sfp光口': 'SFP端口数',
        }
        
        param_lower = param.lower()
        for pattern, chinese in mappings.items():
            if re.search(pattern, param_lower):
                return chinese
        
        # Return None for unmapped params (they'll be skipped if not important)
        return None
    
    def _is_port_description(self, feature: str, value: str) -> bool:
        """Check if this is a port description row."""
        port_keywords = ['sfp', 'qsfp', 'base-t', 'ethernet', 'port', '光口', '电口']
        return any(kw in feature.lower() for kw in port_keywords)
    
    def _parse_port_description(self, feature: str, value: str) -> Dict[str, any]:
        """Parse port description into structured data."""
        result = {}
        text = f"{value} {feature}".lower()
        
        # Parse different port types
        patterns = [
            (r'(\d+)\s*[\*x×]?\s*sfp28', 'SFP28端口数'),
            (r'(\d+)\s*[\*x×]?\s*sfp\+', 'SFP+端口数'),
            (r'(\d+)\s*[\*x×]?\s*qsfp28', 'QSFP28端口数'),
            (r'(\d+)\s*[\*x×]?\s*qsfp\+', 'QSFP+端口数'),
            (r'(\d+)\s*[\*x×]?\s*sfp(?!\+|28)', 'SFP端口数'),
            (r'(\d+)\s*[\*x×]?\s*10/?100/?1000\s*base-t', '1000Base-T端口数'),
            (r'(\d+)\s*[\*x×]?\s*2\.5g', '2.5G端口数'),
            (r'(\d+)\s*[\*x×]?\s*5g', '5G端口数'),
            (r'(\d+)\s*[\*x×]?\s*10g', '10G端口数'),
        ]
        
        for pattern, port_type in patterns:
            match = re.search(pattern, text)
            if match:
                result[port_type] = int(match.group(1))
        
        return result
    
    def _parse_poe_ports(self, text: str) -> Dict[str, int]:
        """Parse POE port quantities."""
        result = {}
        
        # Parse different POE standards
        af_match = re.search(r'15\.4W.*802\.3af.*?[:\s]+(\d+)', text)
        at_match = re.search(r'30W.*802\.3at.*?[:\s]+(\d+)', text)
        bt60_match = re.search(r'60W.*802\.3bt.*?[:\s]+(\d+)', text)
        bt90_match = re.search(r'90W.*802\.3bt.*?[:\s]+(\d+)', text)
        
        if af_match:
            result['POE端口数(802.3af)'] = int(af_match.group(1))
        if at_match:
            result['POE+端口数(802.3at)'] = int(at_match.group(1))
        if bt60_match:
            result['POE++端口数(60W)'] = int(bt60_match.group(1))
        if bt90_match:
            result['POE++端口数(90W)'] = int(bt90_match.group(1))
        
        return result

    def _extract_software_table(self, headers: List[str], rows: List[Dict]) -> Dict[str, Dict]:
        """Extract software features table (VLAN, routing, etc.)."""
        result = {}
        
        # Software tables usually have: Feature | Series/Model
        if len(headers) < 2:
            return result
        
        feature_col = headers[0]
        value_col = headers[1]  # Usually "S5130S-EI Series Switches" or similar
        
        # Collect all features
        features = []
        for row in rows:
            feature = row.get(feature_col, '').strip()
            value = row.get(value_col, '').strip()
            if feature and value and not self._should_skip_param(feature):
                features.append(f"{feature}: {value}")
        
        if features:
            # Try to identify the model series from value_col
            model_series = value_col if 'S' in value_col else 'Series'
            result[model_series] = {'软件特性': '; '.join(features[:10])}  # Limit to first 10
        
        return result
    
    def _extract_performance_table(self, headers: List[str], rows: List[Dict]) -> Dict[str, Dict]:
        """Extract performance specifications table."""
        result = {}
        
        if len(headers) < 2:
            return result
        
        feature_col = headers[0]
        value_col = headers[1]
        
        # Extract performance metrics
        perf_data = {}
        for row in rows:
            feature = row.get(feature_col, '').strip()
            value = row.get(value_col, '').strip()
            
            if not feature or not value:
                continue
            
            # Normalize performance parameter names
            norm_name = None
            if 'mac' in feature.lower():
                norm_name = 'MAC地址表'
            elif 'vlan' in feature.lower() and 'table' in feature.lower():
                norm_name = 'VLAN表项'
            elif 'routing' in feature.lower() or 'route' in feature.lower():
                norm_name = '路由表项'
            elif 'arp' in feature.lower():
                norm_name = 'ARP表项'
            elif 'acl' in feature.lower():
                norm_name = 'ACL规则数'
            elif 'mroute' in feature.lower() or 'multicast' in feature.lower():
                norm_name = '组播表项'
            
            if norm_name:
                perf_data[norm_name] = value
        
        if perf_data:
            model_series = value_col if 'S' in value_col else 'Performance'
            result[model_series] = perf_data
        
        return result
    
    def _extract_protocols_table(self, headers: List[str], rows: List[Dict]) -> Dict[str, Dict]:
        """Extract standards and protocols compliance table."""
        result = {}
        
        # Protocols tables usually have: Organization | Standards
        protocols_list = []
        
        for row in rows:
            org = row.get(headers[0], '').strip() if headers else ''
            std = row.get(headers[1], '').strip() if len(headers) > 1 else ''
            
            if org and std:
                protocols_list.append(f"{org}: {std}")
        
        if protocols_list:
            # Store as a single entry
            result['Protocols'] = {'支持协议': '; '.join(protocols_list[:10])}
        
        return result


# Convenience function
def extract_tables_direct(html: str, url: str = "") -> Dict[str, Dict]:
    """Extract tables using direct processing."""
    extractor = DirectTableExtractor()
    return extractor.extract_all_tables(html, url)
