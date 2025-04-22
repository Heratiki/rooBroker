"""
Configuration and shared constants for LM Studio integrations.
Includes API endpoints and rich console detection.
"""
from typing import Optional, Any
import sys

# Rich console and components detection
try:
    from rich.console import Console
    from rich.prompt import Prompt
    from rich.progress import Progress, TextColumn, BarColumn, TimeElapsedColumn, TimeRemainingColumn, SpinnerColumn
    from rich.live import Live
    from rich.layout import Layout
    from rich.table import Table
    from rich.text import Text
    from rich import box

    console = Console()
    rich_available: bool = True
except ImportError:
    Console: Optional[Any] = None
    Prompt: Optional[Any] = None
    Progress: Optional[Any] = None
    TextColumn: Optional[Any] = None
    BarColumn: Optional[Any] = None
    TimeElapsedColumn: Optional[Any] = None
    TimeRemainingColumn: Optional[Any] = None
    SpinnerColumn: Optional[Any] = None
    Live: Optional[Any] = None
    Layout: Optional[Any] = None
    Table: Optional[Any] = None
    Text: Optional[Any] = None
    box: Optional[Any] = None
    console: Optional[Any] = None
    rich_available: bool = False

# API endpoints
LM_STUDIO_MODELS_ENDPOINT: str = "http://localhost:1234/v1/models"
CHAT_COMPLETIONS_ENDPOINT: str = "http://localhost:1234/v1/chat/completions"
