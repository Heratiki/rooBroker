"""User interface components for rooBroker.

This package provides UI utilities for both CLI and interactive modes.
"""

from rooBroker.ui.common_formatters import (
    pretty_print_models,
    pretty_print_benchmarks,
)
from rooBroker.ui.menu_manager import MenuItem, MenuManager
from rooBroker.ui.interactive_layout import (
    InteractiveLayout,
    ModelInfo,
    MenuSection,
    ModelsSection,
    PromptSection,
)
from rooBroker.ui.interactive_utils import (
    display_menu,
    select_models,
    select_models_by_number,
    run_proxy_with_ui,
)

__all__ = [
    # Formatters
    "pretty_print_models",
    "pretty_print_benchmarks",
    # Menu management
    "MenuItem",
    "MenuManager",
    # Interactive layout
    "InteractiveLayout",
    "ModelInfo",
    "MenuSection",
    "ModelsSection",
    "PromptSection",
    # Interactive utilities
    "display_menu",
    "select_models",
    "select_models_by_number",
    "run_proxy_with_ui",
]
