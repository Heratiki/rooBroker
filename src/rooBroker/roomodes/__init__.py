"""
Roo Code Modes (roomodes) package
Provides utilities for generating and updating Roo Code mode configurations.
"""
from .utils import slugify
from .mode_generation import generate_mode_entry, create_boomerang_mode
from .analysis_parsing import extract_strategy_from_analysis, extract_core_insight, extract_coding_insights

__all__ = [
    'slugify',
    'generate_mode_entry',
    'create_boomerang_mode',
    'extract_strategy_from_analysis',
    'extract_core_insight',
    'extract_coding_insights',
]
