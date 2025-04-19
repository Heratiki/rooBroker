"""
Configuration and shared constants for LM Studio integrations.
Includes API endpoints and rich console detection.
"""
from typing import Optional
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

    console: Console = Console()
    rich_available: bool = True
except ImportError:
    Console = None  # type: ignore
    Prompt = None  # type: ignore
    Progress = None  # type: ignore
    TextColumn = None  # type: ignore
    BarColumn = None  # type: ignore
    TimeElapsedColumn = None  # type: ignore
    TimeRemainingColumn = None  # type: ignore
    SpinnerColumn = None  # type: ignore
    Live = None  # type: ignore
    Layout = None  # type: ignore
    Table = None  # type: ignore
    Text = None  # type: ignore
    box = None  # type: ignore
    console = None  # type: ignore
    rich_available = False

# API endpoints
LM_STUDIO_MODELS_ENDPOINT: str = "http://localhost:1234/v1/models"
CHAT_COMPLETIONS_ENDPOINT: str = "http://localhost:1234/v1/chat/completions"
