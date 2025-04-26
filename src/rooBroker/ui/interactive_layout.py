"""Terminal UI layout management for rooBroker interactive mode."""
from typing import Optional, List, Dict
import asyncio
from dataclasses import dataclass
from rich.layout import Layout
from rich.live import Live
from rich.console import Console, Group
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich import box

MIN_TERMINAL_WIDTH = 80
MIN_TERMINAL_HEIGHT = 24

@dataclass
class ModelInfo:
    """Information about a discovered model."""
    name: str
    status: str
    details: Optional[str] = None

class MenuSection:
    """Manages the menu section of the TUI."""
    
    def __init__(self):
        self.options = [
            "1. Discover & Benchmark Models",
            "2. Manual Save Model State",
            "3. Update Roomodes",
            "4. Run All Steps",
            "5. View Benchmark Results",
            "6. Launch Context Proxy",
            "7. Exit"
        ]
        self.selected = 0

    def __rich__(self) -> Panel:
        """Return the rich panel containing the menu."""
        menu_items = []
        for i, option in enumerate(self.options):
            if i == self.selected:
                menu_items.append(Text(option, style="bold cyan"))
            else:
                menu_items.append(Text(option))
        
        return Panel(
            Group(*menu_items),
            title="Menu",
            border_style="blue",
            box=box.ROUNDED
        )

class ModelsSection:
    """Manages the available models section of the TUI."""
    
    def __init__(self):
        self.models: List[ModelInfo] = []
        self.scroll_position = 0
        self.visible_lines = 10

    def add_model(self, model: ModelInfo) -> None:
        """Add a model to the list."""
        self.models.append(model)

    def scroll_up(self) -> None:
        """Scroll the model list up."""
        if self.scroll_position > 0:
            self.scroll_position -= 1

    def scroll_down(self) -> None:
        """Scroll the model list down."""
        if self.scroll_position < max(0, len(self.models) - self.visible_lines):
            self.scroll_position += 1

    def __rich__(self) -> Panel:
        """Return the rich panel containing the models list."""
        table = Table(box=None, show_header=False, padding=(0, 1))
        
        visible_models = self.models[self.scroll_position:self.scroll_position + self.visible_lines]
        for model in visible_models:
            status_style = {
                "ready": "green",
                "discovered": "yellow",
                "benchmarking": "blue",
                "failed": "red"
            }.get(model.status.lower(), "white")
            
            table.add_row(
                Text(f"- {model.name}", style="white"),
                Text(f"({model.status})", style=status_style)
            )

        scroll_info = ""
        if len(self.models) > self.visible_lines:
            scroll_info = "\nUse [W/S] to scroll"

        return Panel(
            Group(table, Text(scroll_info, style="dim")),
            title="Available Models",
            border_style="blue",
            box=box.ROUNDED
        )

class BenchmarkingSection:
    """Manages the benchmarking status section of the TUI."""
    
    def __init__(self):
        self.current_model: Optional[str] = None
        self.progress: float = 0.0
        self.status: str = "Idle"
        self.time_remaining: Optional[str] = None

    def update_progress(self, model: str, progress: float, time_remaining: Optional[str] = None) -> None:
        """Update the benchmarking progress."""
        self.current_model = model
        self.progress = progress
        self.time_remaining = time_remaining

    def __rich__(self) -> Panel:
        """Return the rich panel containing the benchmarking status."""
        if not self.current_model:
            content = Text("No active benchmarking", style="dim")
        else:
            progress_bar = "█" * int(self.progress * 20) + "▒" * (20 - int(self.progress * 20))
            content = Group(
                Text(f"Benchmarking {self.current_model}..."),
                Text(f"[{progress_bar}] {int(self.progress * 100)}%"),
                Text(f"Time remaining: {self.time_remaining or 'calculating...'}")
            )

        return Panel(
            content,
            title="Benchmarking Status",
            border_style="blue",
            box=box.ROUNDED
        )

class PromptSection:
    """Manages the prompt improvement section of the TUI."""
    
    def __init__(self):
        self.messages: List[str] = []
        self.max_messages = 5

    def add_message(self, message: str) -> None:
        """Add a new message to the prompt improvement section."""
        self.messages.append(message)
        if len(self.messages) > self.max_messages:
            self.messages.pop(0)

    def __rich__(self) -> Panel:
        """Return the rich panel containing the prompt improvement messages."""
        content = Group(*[Text(msg) for msg in self.messages])
        return Panel(
            content,
            title="Prompt Improvement",
            border_style="blue",
            box=box.ROUNDED
        )

class InteractiveLayout:
    """Main class managing the entire TUI layout."""
    
    def __init__(self):
        self.console = Console()
        self.layout = Layout()
        
        # Create the main sections
        self.menu = MenuSection()
        self.models = ModelsSection()
        self.benchmarking = BenchmarkingSection()
        self.prompt = PromptSection()
        
        # Configure the layout
        self._setup_layout()

    def _setup_layout(self) -> None:
        """Set up the initial layout structure."""
        # Split main layout vertically (70/30)
        self.layout.split_column(
            Layout(name="top", ratio=70),
            Layout(name="bottom", ratio=30)
        )
        
        # Split top section horizontally (30/70)
        self.layout["top"].split_row(
            Layout(name="menu", ratio=30),
            Layout(name="models", ratio=70)
        )
        
        # Split bottom section horizontally (50/50)
        self.layout["bottom"].split_row(
            Layout(name="benchmarking", ratio=50),
            Layout(name="prompt", ratio=50)
        )
        
        # Assign sections to layout areas
        self.layout["menu"].update(self.menu)
        self.layout["models"].update(self.models)
        self.layout["benchmarking"].update(self.benchmarking)
        self.layout["prompt"].update(self.prompt)

    def check_terminal_size(self) -> bool:
        """Check if the terminal is large enough for the UI."""
        width, height = self.console.size
        return width >= MIN_TERMINAL_WIDTH and height >= MIN_TERMINAL_HEIGHT

    async def run(self) -> None:
        """Run the interactive UI."""
        if not self.check_terminal_size():
            self.console.print(
                f"[red]Terminal too small. Minimum size: {MIN_TERMINAL_WIDTH}x{MIN_TERMINAL_HEIGHT}[/red]"
            )
            return

        with Live(self.layout, refresh_per_second=4, screen=True) as live:
            while True:
                # Update layout
                self._setup_layout()
                
                # Refresh display
                live.update(self.layout)
                
                # Wait a bit before next update
                await asyncio.sleep(0.25)

    def handle_input(self, key: str) -> bool:
        """Handle user input and return whether to continue running."""
        if key.lower() == 'q':
            return False
        elif key in ['w', 'W']:
            self.models.scroll_up()
        elif key in ['s', 'S']:
            self.models.scroll_down()
        elif key.isdigit() and 1 <= int(key) <= 7:
            self.menu.selected = int(key) - 1
            if int(key) == 7:  # Exit option
                return False
        return True
