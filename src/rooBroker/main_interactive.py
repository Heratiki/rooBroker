"""
Interactive mode entry point for rooBroker.

This module provides a rich terminal user interface for the rooBroker application,
allowing users to discover, benchmark, and manage LM Studio models.
"""

import sys
import asyncio
import importlib.util
from typing import List, Dict, Any, Optional, Sequence, Union, cast

# Dynamic platform-specific imports
if sys.platform.startswith("win"):
    try:
        import msvcrt  # type: ignore
    except ImportError:
        msvcrt = None
else:
    try:
        import tty  # type: ignore
        import termios  # type: ignore
    except ImportError:
        tty = None
        termios = None

from rich.console import Console
from rich.live import Live
from rich.prompt import Prompt
from rich.progress import Progress, TextColumn, BarColumn, MofNCompleteColumn, TimeRemainingColumn

from rooBroker.ui.interactive_layout import InteractiveLayout
from rooBroker.roo_types.discovery import DiscoveredModel
from rooBroker.interfaces.lmstudio.client import LMStudioClient
from rooBroker.interfaces.ollama.client import OllamaClient
from . import interactive_actions

# Global variables
console = Console()
layout = InteractiveLayout()
discovered_models: List[DiscoveredModel] = []
benchmark_results: List[Dict[str, Any]] = []
proxy_server = None
proxy_stop_function = None
current_menu: str = "main"
app_state = {
    'benchmark_config': {
        'model_source': 'discovered',
        'provider': None,
        'provider_options': []
    }
}

difficulties = ["basic", "intermediate", "advanced", None]
types = ["statement", "function", "class", "algorithm", "context", None]

model_list_scroll = 0  # Track scroll position for model list

# Helper functions
def read_single_key() -> str:
    """Read a single keypress from the user."""
    if sys.platform.startswith("win") and msvcrt is not None:
        return msvcrt.getwch()  # type: ignore
    elif termios is not None and tty is not None:
        fd = sys.stdin.fileno()
        try:
            old_settings = termios.tcgetattr(fd)  # type: ignore
            try:
                tty.setraw(fd)  # type: ignore
                ch = sys.stdin.read(1)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)  # type: ignore
            return ch
        except:
            pass
    return "\n"

MENU_OPTIONS = {
    'main': [
        ('1', 'Discover Models', lambda: interactive_actions.discover_models_only(layout, discovered_models)),
        ('2', 'Run Benchmarks', lambda: None),  # Placeholder, menu transition handled in key processing
        ('3', 'Save Model State', lambda: interactive_actions.manual_save_state(layout, benchmark_results)),
        ('4', 'Update Roomodes', lambda: interactive_actions.update_roomodes_action(layout)),
        ('5', 'View Results', lambda: interactive_actions.view_benchmark_results(layout)),
        ('6', 'Launch Proxy', lambda: interactive_actions.launch_context_proxy(layout)),
        ('7', 'Run All Steps', lambda: interactive_actions.run_all_steps(layout, app_state, discovered_models, benchmark_results)),
        ('q', 'Quit', None)
    ],
    'benchmark': [
        ('1', 'All Benchmarks', lambda: interactive_actions.handle_benchmark_option('all', layout, app_state, benchmark_results, discovered_models)),
        ('2', 'Basic Benchmarks', lambda: interactive_actions.handle_benchmark_option('basic', layout, app_state, benchmark_results, discovered_models)),
        ('3', 'Advanced Benchmarks', lambda: interactive_actions.handle_benchmark_option('advanced', layout, app_state, benchmark_results, discovered_models)),
        ('4', 'Custom Benchmarks', lambda: interactive_actions.handle_benchmark_option('custom', layout, app_state, benchmark_results, discovered_models)),
        ('b', 'Back to Main Menu', lambda: None),  # Placeholder, menu transition handled in key processing
        ('q', 'Quit', None)
    ]
}

def _draw_menu(menu_type: str = 'main', selected: int = 0):
    """Draw the menu with the currently selected item highlighted."""
    menu_items = MENU_OPTIONS[menu_type]
    for idx, (key, label, _) in enumerate(menu_items):
        if idx == selected:
            console.print(f"[bold white on blue] {key}. {label} [/]")
        else:
            console.print(f" {key}. {label}")

async def interactive_main_async():
    """Main async function for interactive mode."""
    global current_menu
    selected = 0
    current_menu = 'main'

    console.clear()
    with Live(layout, refresh_per_second=4, screen=True, auto_refresh=False) as live:
        live.start()
        
        while True:
            try:
                # Update layout and menu
                live.update(layout, refresh=True)
                
                # Draw menu
                with console.capture() as capture:
                    console.print("\n")
                    _draw_menu(current_menu, selected)
                live.console.print(capture.get())
                live.refresh()

                # Get input
                key = read_single_key()
                menu_items = MENU_OPTIONS[current_menu]

                # Handle navigation
                if key == '\x1b':  # Escape sequence
                    next_char = read_single_key()
                    if next_char == '[':
                        arrow = read_single_key()
                        if arrow == 'A':  # Up arrow
                            selected = (selected - 1) % len(menu_items)
                            continue
                        elif arrow == 'B':  # Down arrow
                            selected = (selected + 1) % len(menu_items)
                            continue

                if key == 'w':  # Scroll model list up
                    layout.models.scroll_up()
                    continue
                
                if key == 's':  # Scroll model list down
                    layout.models.scroll_down()
                    continue

                if key == 'q':  # Quit
                    break

                if key == 'b' and current_menu != 'main':  # Back to main menu
                    current_menu = 'main'
                    selected = 0
                    continue

                # Handle menu transitions
                if current_menu == 'main' and key == '2':
                    current_menu = 'benchmark'
                    selected = 0
                    continue

                # Handle action selection
                action = None
                # Handle Enter/Space for selected item
                if key in ['\r', '\n', ' ']:
                    action = menu_items[selected][2]
                # Handle number keys and shortcuts
                else:
                    for shortcut, _, act in menu_items:
                        if str(key) == str(shortcut):  # Convert both to string for comparison
                            action = act
                            break

                if action is not None:
                    if action is None:  # Quit option
                        break
                    try:
                        # Check if it's a direct coroutine or a lambda that returns one
                        if asyncio.iscoroutinefunction(action):
                            await action()
                        else:
                            # Execute the action and await if it returns a coroutine
                            result = action()
                            if asyncio.iscoroutine(result):
                                await result
                    except Exception as e:
                        layout.prompt.add_message(f"[red]Error: {str(e)}[/red]")
                        continue

            except Exception as e:
                layout.prompt.add_message(f"[red]Error: {str(e)}[/red]")
                live.refresh()
                await asyncio.sleep(1)  # Give user time to see error

def _cleanup_resources():
    global proxy_stop_function
    if proxy_stop_function:
        layout.prompt.add_message("[yellow]Stopping context proxy...[/yellow]")
        proxy_stop_function()
        layout.prompt.add_message("[green]Context proxy stopped.[/green]")

# Main execution
def main():
    """Main entry point."""
    console.print("[bold blue]Welcome to rooBroker Interactive Mode[/]")
    try:
        asyncio.run(interactive_main_async())
    except KeyboardInterrupt:
        pass
    finally:
        _cleanup_resources()
        console.print("\n[bold blue]Exiting rooBroker Interactive Mode.[/]")

# Ensure this file can be run as a script
if __name__ == "__main__":
    main()