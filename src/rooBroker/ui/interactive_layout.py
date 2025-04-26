"""
Interactive mode layout management for rooBroker.

This module defines the layout and rendering logic for the TUI interface.
"""

from typing import Optional, List, Dict
from rich.console import Console, RenderableType
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.align import Align
from rich.style import Style
from rich.padding import Padding
from rich.console import Group
from rich.table import Table
from rich import box
import shutil

MIN_TERMINAL_WIDTH = 80
MIN_TERMINAL_HEIGHT = 24

class MenuSection:
    """Manages the menu section of the TUI."""
    
    def __init__(self) -> None:
        self.selected_item: int = 1
        self.menu_items = [
            "1. Discover & Benchmark Models",
            "2. Manual Save Model State",
            "3. Update Roomodes",
            "4. Run All Steps",
            "5. View Benchmark Results",
            "6. Launch Context Proxy",
            "7. Exit"
        ]

    def __rich__(self) -> RenderableType:
        menu_text = Group(*[
            Text(item, style="cyan" if i + 1 == self.selected_item else "")
            for i, item in enumerate(self.menu_items)
        ])
        return Panel(menu_text, title="Menu Options", border_style="blue")

class ModelsSection:
    """Manages the available models section of the TUI."""
    
    def __init__(self) -> None:
        self.models: List[Dict[str, str]] = []
        self.scroll_position: int = 0
        
    def add_model(self, name: str, status: str) -> None:
        """Add a model to the list."""
        self.models.append({"name": name, "status": status})
    
    def __rich__(self) -> RenderableType:
        table = Table(box=box.SIMPLE, show_header=False, expand=True)
        table.add_column("Model", style="cyan")
        table.add_column("Status", style="green")
        
        visible_models = self.models[self.scroll_position:self.scroll_position + 10]
        for model in visible_models:
            table.add_row(model["name"], model["status"])
            
        if not self.models:
            table.add_row("No models discovered", "")
            
        scroll_info = "\n[dim]Use [W/S] to scroll[/dim]" if len(self.models) > 10 else ""
        group = Group(table, Text(scroll_info))
        return Panel(group, title="Available Models", border_style="blue")

class BenchmarkingSection:
    """Manages the benchmarking status section of the TUI."""
    
    def __init__(self) -> None:
        self.current_model: Optional[str] = None
        self.progress: float = 0.0
        self.time_remaining: str = ""
        
    def update_progress(self, model: str, progress: float, time_remaining: str) -> None:
        """Update the benchmarking progress."""
        self.current_model = model
        self.progress = progress
        self.time_remaining = time_remaining
        
    def __rich__(self) -> RenderableType:
        if not self.current_model:
            content = Text("No benchmarking in progress", style="dim")
        else:
            progress_bar = f"[{'#' * int(self.progress * 20)}{'-' * (20 - int(self.progress * 20))}]"
            content = Group(
                Text(f"Benchmarking {self.current_model}... {progress_bar} {int(self.progress * 100)}%"),
                Text(f"Estimated time remaining: {self.time_remaining}")
            )
        return Panel(content, title="Benchmarking Status", border_style="blue")

class PromptSection:
    """Manages the prompt improvement section of the TUI."""
    
    def __init__(self) -> None:
        self.messages: List[str] = []
        
    def add_message(self, message: str) -> None:
        """Add a message to the prompt improvement section."""
        self.messages.append(message)
        if len(self.messages) > 5:  # Keep only last 5 messages
            self.messages.pop(0)
            
    def __rich__(self) -> RenderableType:
        content = Group(*[Text(msg) for msg in self.messages]) if self.messages else Text("No active prompt improvements", style="dim")
        return Panel(content, title="Prompt Improvement", border_style="blue")

class InteractiveLayout:
    """Manages the overall TUI layout."""
    
    def __init__(self) -> None:
        self.console = Console()
        self.layout = Layout()
        
        # Create sections
        self.menu = MenuSection()
        self.models = ModelsSection()
        self.benchmarking = BenchmarkingSection()
        self.prompt = PromptSection()
        
        # Initialize layout
        self._init_layout()
        
    def _init_layout(self) -> None:
        """Initialize the layout structure."""
        # Split main layout vertically (top and bottom sections)
        self.layout.split(
            Layout(name="top", ratio=70),
            Layout(name="bottom", ratio=30)
        )
        
        # Split top section horizontally (menu and models)
        self.layout["top"].split_row(
            Layout(name="menu", ratio=30),
            Layout(name="models", ratio=70)
        )
        
        # Split bottom section horizontally (benchmarking and prompt)
        self.layout["bottom"].split_row(
            Layout(name="benchmarking", ratio=50),
            Layout(name="prompt", ratio=50)
        )
        
        # Assign renderable content to each section
        self.layout["menu"].renderable = self.menu
        self.layout["models"].renderable = self.models
        self.layout["benchmarking"].renderable = self.benchmarking
        self.layout["prompt"].renderable = self.prompt
        
    def check_terminal_size(self) -> bool:
        """Check if terminal size meets minimum requirements."""
        width, height = shutil.get_terminal_size()
        return width >= MIN_TERMINAL_WIDTH and height >= MIN_TERMINAL_HEIGHT
        
    def display_size_warning(self) -> None:
        """Display warning about terminal size."""
        self.console.print(
            f"[red]Terminal too small. Minimum size required: {MIN_TERMINAL_WIDTH}x{MIN_TERMINAL_HEIGHT}[/red]"
        )
        
    def render(self) -> None:
        """Render the layout if terminal size is adequate."""
        if not self.check_terminal_size():
            self.display_size_warning()
            return
            
        self.console.clear()
        self.console.print(self.layout)
