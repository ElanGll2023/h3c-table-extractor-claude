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
        
        # Extract series features (applies to all models in series)
        series_features = self._extract_series_features(soup, page_url)
        
        # Extract model descriptions from page
        model_descriptions = self._extract_model_descriptions(soup)
        
        for i, table in enumerate(tables):
            table_data = self._process_table(table, i, page_url)
            if table_data:
                # Separate series-level data from model-specific data
                for model_name, specs in table_data.items():
                    if not specs:  # Skip empty entries
                        continue
                    # Check if this is a series-level entry
                    if 'Series' in model_name or 'Performance' in model_name or 'Protocols' in model_name or model_name.startswith(('RFC', 'IEEE', 'ITU', 'IETF')):
                        series_data[model_name] = specs
                    else:
                        if model_name not in all_data:
                            all_data[model_name] = {}
                        all_data[model_name].update(specs)
        
        # Add URL, descriptions, and series features to all models
        for model_name in all_data:
            # Add page URL
            all_data[model_name]['链接地址'] = page_url
            
            # Add model description if found
            if model_name in model_descriptions:
                all_data[model_name]['型号描述'] = model_descriptions[model_name]
            
            # Add series features
            if series_features:
                all_data[model_name]['系列特性'] = series_features
        
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
                    elif 'Performance' in series_key:
                        # Performance data applies to all models in the series
                        for model_name in model_keys:
                            all_data[model_name].update(series_specs)
        
        # Post-processing: normalize and merge fields
        for model_name, specs in all_data.items():
            # Merge 1G端口数 into 1000Base-T端口数
            if '1G端口数' in specs and '1000Base-T端口数' not in specs:
                specs['1000Base-T端口数'] = specs['1G端口数']
            # Remove the redundant 1G端口数 field after merging
            if '1G端口数' in specs:
                del specs['1G端口数']
            
            # Merge POE总功率_AC/DC into POE总功率
            poe_power_parts = []
            if 'POE总功率_AC' in specs:
                poe_power_parts.append(f"AC:{specs['POE总功率_AC']}W")
            if 'POE总功率_DC' in specs:
                poe_power_parts.append(f"DC:{specs['POE总功率_DC']}W")
            if poe_power_parts and 'POE总功率' not in specs:
                specs['POE总功率'] = '/'.join(poe_power_parts)
            
            # Remove redundant POE power fields after merging
            if 'POE总功率_AC' in specs:
                del specs['POE总功率_AC']
            if 'POE总功率_DC' in specs:
                del specs['POE总功率_DC']
            
            # Classify as box switch or chassis switch
            specs['交换机类型'] = self._classify_switch_type(model_name, specs)
        
        return all_data
    
    def _classify_switch_type(self, model_name: str, specs: Dict) -> str:
        """Classify switch as box (fixed) or chassis (modular) type."""
        # Chassis switches typically have these model prefixes
        chassis_prefixes = ['S125', 'S105', 'S76', 'S75', 'S95', 'S98']
        
        # Check model name prefix
        for prefix in chassis_prefixes:
            if model_name.startswith(prefix):
                return '框式交换机'
        
        # Check for chassis-specific parameters
        chassis_params = ['业务板槽位', '主控板槽位', '接口板槽位', '槽位数', 'chassis', 'slot']
        for param in specs:
            param_lower = param.lower()
            if any(cp in param_lower for cp in chassis_params):
                return '框式交换机'
        
        # Default to box switch
        return '盒式交换机'
    
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
        
        # Check if this is a multi-model hardware table
        if len(headers) > 2 and self._is_multi_model_table(headers):
            return self._extract_multi_model_table(headers, rows)
        else:
            return self._extract_generic_table(headers, rows)
    
    def _detect_table_type(self, text: str) -> str:
        """Detect table type from content."""
        text_lower = text.lower()
        
        # Check for protocols first (to avoid misclassification with POE keywords)
        if 'organization' in text_lower and any(x in text_lower for x in ['ieee', 'rfc', 'standard']):
            return 'protocols'
        elif 'standards and protocols' in text_lower:
            return 'protocols'
        # Check for actual POE power tables (not just model names with PWR)
        elif any(x in text_lower for x in ['poe power capacity', 'total poe power', '802.3af', '802.3at']) and 'quantity' in text_lower:
            return 'poe'
        elif any(x in text_lower for x in ['entries', 'mac address entries', 'vlan table', 'routing entries', 'arp entries']):
            # Performance tables often have "Entries" in title and contain metrics
            return 'performance'
        elif any(x in text_lower for x in ['vlan', 'routing protocol', 'security feature', 'layer 2', 'layer 3']):
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
        
        # Handle special tables with merged title row (e.g., "FeatureS5130S-EI Series Switches")
        # These tables actually have 2 columns: Feature | Description
        # Only apply to Feature/Entries tables, not to Organization/Protocols tables
        if len(headers) == 1:
            header_text = headers[0].lower()
            if any(keyword in header_text for keyword in ['feature', 'entries']):
                # This is a software or performance table with implicit 2 columns
                headers = ['Feature', 'Description']
            # Note: Organization/Protocols tables keep their original structure
        
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
            r'sfp\+\s*port|sfp\+\s*光口': 'SFP+端口数',
            r'sfp(?!\+)\s*port|sfp(?!\+)\s*光口': 'SFP端口数',
            r'sfp28\s*port|sfp28\s*光口': 'SFP28端口数',
            r'qsfp\+\s*port|qsfp\+\s*光口': 'QSFP+端口数',
            r'qsfp(?!\+)\s*port|qsfp(?!\+)\s*光口': 'QSFP端口数',
            r'qsfp28\s*port|qsfp28\s*光口': 'QSFP28端口数',
            r'multigiga|multi-giga|2\.5g|5g|多速率': 'MultiGiga端口数',
            r'maximum\s*stacking\s*bandwidth|堆叠带宽|最大堆叠带宽': '最大堆叠带宽',
            r'maximum\s*stacking\s*num|堆叠数量|最大堆叠数': '最大堆叠数',
        }
        
        param_lower = param.lower()
        for pattern, chinese in mappings.items():
            if re.search(pattern, param_lower):
                return chinese
        
        # Return None for unmapped params (they'll be skipped if not important)
        return None
    
    def _is_port_description(self, feature: str, value: str) -> bool:
        """Check if this is a port description row."""
        port_keywords = ['sfp', 'qsfp', 'base-t', 'ethernet', 'port', '光口', '电口', 'multigiga', 'multi-giga']
        return any(kw in feature.lower() for kw in port_keywords)
    
    def _parse_port_description(self, feature: str, value: str) -> Dict[str, any]:
        """Parse port description into structured data."""
        result = {}
        
        # Skip if value is empty or just "/" (indicates not applicable)
        if not value or value.strip() in ['/', '-', '']:
            return result
        
        text = f"{value} {feature}".lower()
        value_lower = value.lower()
        
        # First, try to extract the main port number from value (e.g., "24 (8*BASE-T combo)")
        # Pattern: number followed by optional combo info
        main_match = re.match(r'(\d+)\s*(?:\([^)]*\))?', value_lower)
        if main_match:
            port_count = int(main_match.group(1))
            
            # Determine port type from feature
            if 'sfp28' in text:
                result['SFP28端口数'] = port_count
            elif 'sfp+' in text or 'sfp plus' in text:
                result['SFP+端口数'] = port_count
            elif 'qsfp28' in text:
                result['QSFP28端口数'] = port_count
            elif 'qsfp+' in text or 'qsfp plus' in text:
                result['QSFP+端口数'] = port_count
            elif 'sfp' in text:
                result['SFP端口数'] = port_count
            elif 'multigiga' in text or '2.5g' in text:
                # Multigiga port - could be 1G/2.5G/5G/10G
                result['MultiGiga端口数'] = port_count
                # Also extract specific speeds if mentioned
                if '1g' in text:
                    result['1G端口数'] = port_count
                if '2.5g' in text or '2.5gb' in text:
                    result['2.5G端口数'] = port_count
                if '5g' in text or '5gb' in text:
                    result['5G端口数'] = port_count
                if '10g' in text or '10gb' in text:
                    result['10G端口数'] = port_count
            elif 'base-t' in text or 'ethernet' in text or '电口' in text:
                result['1000Base-T端口数'] = port_count
        
        # Parse Combo port info: e.g., "24 (8*BASE-T combo)" or "(8 combo)"
        combo_match = re.search(r'\((\d+)\s*\*?\s*(?:base-t\s*)?combo\)', text)
        if combo_match:
            result['Combo端口数'] = int(combo_match.group(1))
        
        # Also parse 2.5G, 5G, 10G ports from full text
        patterns_ng = [
            (r'(\d+)\s*[\*x×]?\s*2\.5g', '2.5G端口数'),
            (r'(\d+)\s*[\*x×]?\s*5g', '5G端口数'),
            (r'(\d+)\s*[\*x×]?\s*10g', '10G端口数'),
        ]
        
        for pattern, port_type in patterns_ng:
            match = re.search(pattern, text)
            if match:
                result[port_type] = int(match.group(1))
        
        return result
    
    def _parse_poe_ports(self, text: str) -> Dict[str, int]:
        """Parse POE port quantities."""
        result = {}
        
        # More precise patterns to avoid greedy matching issues
        # Pattern: 15.4W (802.3af): 8 or 15.4W: 8 (802.3af)
        af_patterns = [
            r'15\.4W\s*\(802\.3af\)[:\s]+(\d+)(?!\d)',  # 15.4W (802.3af): 8
            r'15\.4W[:\s]+(\d+)\s*\(802\.3af\)',       # 15.4W: 8 (802.3af)
        ]
        at_patterns = [
            r'30W\s*\(802\.3at\)[:\s]+(\d+)(?!\d)',     # 30W (802.3at): 4
            r'30W[:\s]+(\d+)\s*\(802\.3at\)',          # 30W: 4 (802.3at)
        ]
        bt60_patterns = [
            r'60W\s*\(802\.3bt\)[:\s]+(\d+)(?!\d)',    # 60W (802.3bt): X
            r'60W[:\s]+(\d+)\s*\(802\.3bt\)',          # 60W: X (802.3bt)
        ]
        bt90_patterns = [
            r'90W\s*\(802\.3bt\)[:\s]+(\d+)(?!\d)',    # 90W (802.3bt): X
            r'90W[:\s]+(\d+)\s*\(802\.3bt\)',          # 90W: X (802.3bt)
        ]
        
        # Try each pattern group
        for pattern in af_patterns:
            match = re.search(pattern, text)
            if match:
                val = int(match.group(1))
                # Validate: port count should be reasonable (1-48)
                if 1 <= val <= 48:
                    result['POE端口数(802.3af)'] = val
                    break
                
        for pattern in at_patterns:
            match = re.search(pattern, text)
            if match:
                val = int(match.group(1))
                if 1 <= val <= 48:
                    result['POE+端口数(802.3at)'] = val
                    break
                
        for pattern in bt60_patterns:
            match = re.search(pattern, text)
            if match:
                val = int(match.group(1))
                if 1 <= val <= 48:
                    result['POE++端口数(60W)'] = val
                    break
                
        for pattern in bt90_patterns:
            match = re.search(pattern, text)
            if match:
                val = int(match.group(1))
                if 1 <= val <= 48:
                    result['POE++端口数(90W)'] = val
                    break
        
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
            # Use a unique key for performance data to avoid overwriting software features
            model_series = value_col if 'S' in value_col else 'Performance'
            perf_key = model_series.replace('Switches', 'Performance') if 'Switches' in model_series else f"{model_series} Performance"
            result[perf_key] = perf_data
        
        return result
    
    def _extract_protocols_table(self, headers: List[str], rows: List[Dict]) -> Dict[str, Dict]:
        """Extract standards and protocols compliance table."""
        result = {}
        
        # Protocols tables usually have: Organization | Standards
        # But Organization may use rowspan - need to track last org
        protocols_list = []
        last_org = ''
        
        for row in rows:
            org = row.get(headers[0], '').strip() if headers else ''
            std = row.get(headers[1], '').strip() if len(headers) > 1 else ''
            
            # Update last_org if we have a new organization
            if org and not org.startswith('802.') and not org.startswith('RFC'):
                last_org = org
            
            # If org looks like a protocol (starts with 802. or RFC), use last_org
            if org and (org.startswith('802.') or org.startswith('RFC')):
                std = org
                org = last_org
            
            if org and std:
                protocols_list.append(f"{org}: {std}")
        
        if protocols_list:
            # Store as a single entry with all protocols
            result['Protocols'] = {'支持协议': '; '.join(protocols_list)}
        
        return result

    def _extract_model_descriptions(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract model descriptions from the page."""
        descriptions = {}
        
        # Look for text patterns like 'S5130S-28S-EI: 24 x 10/100/1000BASE-T...'
        text_content = soup.get_text()
        
        # Pattern: ModelName: description (up to newline or next model)
        # Examples:
        # S5570S-28S-EI: 24 x 10/100/1000BASE-T Ethernet ports, 4 x 1G/10G BASE-X SFP+ ports
        # S5130S-28P-EI: 24 x 10/100/1000BASE-T Ports and 4 x 1000BASE-X SFP Ports
        model_patterns = [
            r'(S\d{4}[A-Z]*-[\w-]+):\s*([0-9x\s/]+(?:BASE-T|Ethernet|Ports|SFP)[^\n;]+?)(?=\n|S\d{4}|$)',
            r'(S\d{4}[A-Z]*-[\w-]+)\s*[:：]\s*([^\n]+?)(?=\n|S\d{4}|$)',
        ]
        
        for pattern in model_patterns:
            matches = re.findall(pattern, text_content, re.IGNORECASE)
            for model, desc in matches:
                model = model.strip()
                desc = desc.strip()
                # Clean up description - take first sentence or up to 200 chars
                if len(desc) > 200:
                    desc = desc[:200] + '...'
                # Only keep if description looks valid (contains port info or reasonable length)
                if len(desc) > 10 and (any(kw in desc.lower() for kw in ['port', 'base', 'ethernet', 'sfp']) or len(desc) < 100):
                    descriptions[model] = desc
        
        # Also look in specific HTML elements (product cards, descriptions, etc.)
        # Look for elements that contain both model name and description
        for elem in soup.find_all(['div', 'p', 'td', 'span']):
            text = elem.get_text(strip=True)
            # Check if this element contains a model name
            model_match = re.search(r'(S\d{4}[A-Z]*-[\w-]+)', text)
            if model_match:
                model = model_match.group(1)
                # Check if there's a description after the model name
                parts = text.split(model, 1)
                if len(parts) > 1:
                    desc = parts[1].strip()
                    # Remove leading colon or other separators
                    desc = re.sub(r'^[\s:：]+', '', desc)
                    # Take reasonable length description
                    if len(desc) > 10 and len(desc) < 200:
                        if model not in descriptions:
                            descriptions[model] = desc
        
        return descriptions

    def _extract_series_features(self, soup: BeautifulSoup, page_url: str = "") -> str:
        """Extract series-level feature keywords from page."""
        features = []
        
        # Look for h2/h3 headers that describe product features
        # Skip table-related headers and generic page sections
        skip_patterns = [
            'hardware', 'specification', 'performance', 'poe', 'removable',
            'components', 'matrix', 'standards', 'protocols', 'resource',
            'related', 'cloud', 'ai', 'intelligent', 'security', 'smb',
            'terminal', 'industry', 'solution', 'service', 'policy',
            'online', 'training', 'partner', 'profile', 'news', 'contact',
            'blog', 'learning', 'certification', 'exhibition',
            '规格', '性能', '硬件', '软件', '协议', '标准', '资源',
            '博客', '培训', '认证', '展览', '联系'
        ]
        
        # Only look at h2 headers (main section titles) before the tables
        # Find the first table and only consider headers before it
        first_table = soup.find('table')
        
        headers = soup.find_all(['h2', 'h3'])
        for h in headers:
            # Skip if after the first table (to avoid footer navigation)
            if first_table and h.sourceline and first_table.sourceline:
                if h.sourceline > first_table.sourceline:
                    # Check if there are more tables after this header
                    # If so, it might be a valid feature section
                    pass  # We'll filter by content instead
            
            text = h.get_text(strip=True)
            # Skip if too long or too short
            if len(text) > 80 or len(text) < 5:
                continue
            # Skip if contains skip keywords
            text_lower = text.lower()
            if any(sp in text_lower for sp in skip_patterns):
                continue
            # Skip "Hardware Specifications (continued)" variations
            if 'continued' in text_lower:
                continue
            # Skip if it looks like navigation/footer (contains common footer terms)
            if any(term in text_lower for term in ['global', 'help', 'become', 'business']):
                continue
            # This looks like a feature title
            if text and text not in features:
                features.append(text)
        
        return '; '.join(features) if features else ''


# Convenience function
def extract_tables_direct(html: str, url: str = "") -> Dict[str, Dict]:
    """Extract tables using direct processing."""
    extractor = DirectTableExtractor()
    return extractor.extract_all_tables(html, url)
