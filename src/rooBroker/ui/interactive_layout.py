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
            "1. Discover Models",
            "2. Benchmark Models",
            "3. Manual Save Model State",
            "4. Update Roomodes",
            "5. Run All Steps",
            "6. View Benchmark Results",
            "7. Launch Context Proxy",
            "8. Exit"
        ]
        self.selected = 0

        self.show_main_menu()

    def show_main_menu(self):
        self.options = [
            "1. Discover Models",
            "2. Benchmark Models",
            "3. Run Configured Benchmarks",
            "4. Update Roomodes",
            "5. Run All Steps",
            "6. View Results",
            "7. Launch Proxy",
            "8. Exit"
        ]

    def show_benchmark_submenu(self):
        self.options = [
            "1. Run All Benchmarks",
            "2. Run Basic Python Benchmarks",
            "3. Run Advanced Python Benchmarks",
            "4. Run Context Benchmarks",
            "5. Back to Main Menu",
            "6. Benchmark Configuration"
        ]

    def show_benchmark_config_menu(self):
        """Displayed when configuring benchmark options."""
        self.options = [
            "1. Set Model Source",
            "2. <Option 2 Placeholder>",
            "3. <Option 3 Placeholder>",
            "4. Back to Benchmark Submenu"
        ]

    def show_model_source_menu(self):
        """Displayed for selecting model source in benchmark config."""
        self.options = [
            "1. Use Discovered Models (Default)",
            "2. Load from State (.modelstate.json)",
            "3. Enter Model IDs Manually",
            "4. Back to Benchmark Config"
        ]

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
    
    def __init__(self, console: Console):
        # Store console for dynamic sizing
        self.console = console
        self.models: List[ModelInfo] = []
        self.scroll_position = 0
        # visible_lines removed; calculated dynamically in __rich__

    def add_model(self, model: ModelInfo) -> None:
        """Add a model to the list."""
        self.models.append(model)

    def scroll_up(self) -> None:
        """Scroll the model list up."""
        if self.scroll_position > 0:
            self.scroll_position -= 1

    def scroll_down(self) -> None:
        """Scroll the model list down."""
        # Recalculate visible_lines dynamically
        available_height = max(1, int(self.console.height * 0.70) - 3)
        visible_lines = available_height
        max_scroll = max(0, len(self.models) - visible_lines)
        if self.scroll_position < max_scroll:
            self.scroll_position += 1

    def __rich__(self) -> Panel:
        """Return the rich panel containing the models list."""
        # Estimate dynamic visible lines based on console height and panel chrome
        available_height = max(1, int(self.console.height * 0.70) - 3)
        visible_lines = available_height
        # Clamp scroll_position within bounds
        max_scroll = max(0, len(self.models) - visible_lines)
        self.scroll_position = min(self.scroll_position, max_scroll)
        # define columns: model name, status, and provider/details
        table = Table(box=None, show_header=False, padding=(0, 1))
        # Select slice of models
        visible_models = self.models[self.scroll_position : self.scroll_position + visible_lines]
        for model in visible_models:
            status_style = {
                "ready": "green",
                "discovered": "yellow",
                "benchmarking": "blue",
                "failed": "red"
            }.get(model.status.lower(), "white")
            
            table.add_row(
                Text(f"- {model.name}", style="white"),
                Text(f"({model.status})", style=status_style),
                Text(model.details or "", style="magenta")
            )

        scroll_info_text = ""
        if len(self.models) > visible_lines:
            scroll_info_text = (
                f"Use [W/S] to scroll ("
                f"{self.scroll_position+1}-"
                f"{min(self.scroll_position+visible_lines,len(self.models))}/"
                f"{len(self.models)})"
            )

        return Panel(
            Group(table, Text(scroll_info_text, style="dim")),
            title="Available Models",
            border_style="blue",
            box=box.ROUNDED
        )

class PromptSection:
    """Manages the prompt improvement section of the TUI."""
    
    def __init__(self):
        self.messages: List[Text] = [] # Store Text objects directly
        self.max_messages = 8
        self._status: Optional[str] = None
        self.benchmarking_status = "No active benchmarking"

    def add_message(self, message: str) -> None:
        """Add a new message to the prompt improvement section, parsing Rich markup."""
        # Parse the message using Rich markup
        text_message = Text.from_markup(message)
        self.messages.append(text_message)
        if len(self.messages) > self.max_messages:
            self.messages.pop(0)

    def set_status(self, status: str) -> None:
        """Set the current status message to display at the top."""
        self._status = status

    def clear_status(self) -> None:
        """Clear the current status message."""
        self._status = None

    def get_benchmarking_panel(self) -> Panel:
        """Return the benchmarking status panel."""
        return Panel(
            Text(self.benchmarking_status),
            title="Benchmarking Status",
            border_style="blue",
            box=box.ROUNDED
        )

    def get_prompt_panel(self) -> Panel:
        """Return the prompt improvement panel."""
        messages_to_display = []
        
        # Add status if set
        if self._status:
            messages_to_display.append(Text(self._status, style="bold cyan"))
            messages_to_display.append(Text("―" * 30, style="dim"))  # Separator
            
        # Add regular messages (already Text objects)
        messages_to_display.extend(self.messages)
        
        content = Group(*messages_to_display)
        return Panel(
            content,
            title="Prompt Improvement",
            border_style="blue",
            box=box.ROUNDED
        )

    def __rich__(self) -> Layout:
        """Return the complete prompt section layout."""
        section = Layout()
        section.split_row(
            Layout(self.get_benchmarking_panel(), name="benchmarking", ratio=1),
            Layout(self.get_prompt_panel(), name="prompt", ratio=2),
        )
        return section

class InteractiveLayout:
    """Interactive terminal UI layout."""
    def __init__(self):
        """Initialize layout components."""
        self.console = Console()
        self.menu = MenuSection()
        self.models = ModelsSection(self.console)
        self.prompt = PromptSection()
        self.layout = Layout()
        self._setup_layout()
        
    def _setup_layout(self):
        """Set up the layout structure."""
        self.layout.split(
            Layout(name="menu"),
            Layout(name="content"),
            Layout(name="status")
        )

    def __rich__(self) -> Layout:
        """Render layout for rich library."""
        # Create main layout
        layout = Layout()
        
        # Split into upper and lower sections
        upper = Layout(name="upper", ratio=2)
        lower = Layout(name="lower", ratio=1)
        layout.split(upper, lower)
        
        # Split upper section into menu and models
        menu_section = Layout(self.menu, name="menu", ratio=1)
        models_section = Layout(self.models, name="models", ratio=2)
        upper.split_row(menu_section, models_section)
        
        # Add prompt section to lower
        lower.update(self.prompt)
        
        return layout

    def render(self):
        """Render the layout for the Live display."""
        return self.layout

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
