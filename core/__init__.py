"""
Universal Product Specs Extractor - Robust Version
可累加的配置驱动产品规格提取器 - 健壮版
"""

from .rule_engine import RuleEngine, ProductProfile, ExtractionRule, get_rule_engine
from .visual_analyzer import VisualStructureAnalyzer
from .page_analyzer import PageAnalyzer, PageAnalysisReport
from .universal_extractor import UniversalExtractor, extract_specs
from .robust_extractor import RobustUniversalExtractor, extract_robust, analyze_page
from .config_wizard import ConfigurationWizard

__version__ = "2.1.0"
__all__ = [
    'RuleEngine',
    'ProductProfile',
    'ExtractionRule',
    'VisualStructureAnalyzer',
    'PageAnalyzer',
    'PageAnalysisReport',
    'UniversalExtractor',
    'RobustUniversalExtractor',
    'extract_specs',
    'extract_robust',
    'analyze_page',
    'ConfigurationWizard',
    'get_rule_engine',
]
