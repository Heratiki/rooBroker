from typing import List, Callable, Optional
import asyncio
from rich.console import Console, Group
from rich.text import Text
from rich.panel import Panel


class MenuItem:
    def __init__(self, key: str, label: str, action: Optional[Callable] = None):
        self.key = key
        self.label = label
        self.action = action  # Could be async or sync


class MenuManager:
    def __init__(self, console: Console):
        self.console = console
        self.menus = {
            "main": [
                MenuItem("1", "Discover Models", self._placeholder_action),
                MenuItem("2", "Run Benchmarks", self._placeholder_action),
                MenuItem("3", "Save Model State", self._placeholder_action),
                MenuItem("4", "Update Roomodes", self._placeholder_action),
                MenuItem("5", "View Results", self._placeholder_action),
                MenuItem("6", "Launch Proxy", self._placeholder_action),
                MenuItem("7", "Run All Steps", self._placeholder_action),
                MenuItem("q", "Quit", None),
            ],
            "benchmark": [
                MenuItem("1", "All Benchmarks", self._placeholder_action),
                MenuItem("2", "Basic Benchmarks", self._placeholder_action),
                MenuItem("3", "Advanced Benchmarks", self._placeholder_action),
                MenuItem("4", "Custom Benchmarks", self._placeholder_action),
                MenuItem("b", "Back to Main Menu", self._placeholder_action),
                MenuItem("q", "Quit", None),
            ],
        }
        self.current_menu_key = "main"
        self.selected_index = 0

    async def _placeholder_action(self):
        """Example async action."""
        self.console.print("[yellow]Action executed![/yellow]")
        await asyncio.sleep(1)

    def set_menu(self, menu_key: str):
        """Set the current menu."""
        self.current_menu_key = menu_key
        self.selected_index = 0

    def navigate(self, direction: int):
        """Navigate the menu up or down."""
        items = self.menus[self.current_menu_key]
        self.selected_index = (self.selected_index + direction) % len(items)

    def get_selected_action(self) -> Optional[Callable]:
        """Get the action of the currently selected menu item."""
        items = self.menus[self.current_menu_key]
        return items[self.selected_index].action

    def __rich__(self) -> Panel:
        """Render the menu as a Rich renderable."""
        items_renderable = []
        menu_items = self.menus[self.current_menu_key]
        for idx, item in enumerate(menu_items):
            label = f" {item.key}. {item.label} "
            if idx == self.selected_index:
                items_renderable.append(Text(label, style="bold white on blue"))
            else:
                items_renderable.append(Text(label))
        return Panel(Group(*items_renderable), title="Menu", border_style="blue")
