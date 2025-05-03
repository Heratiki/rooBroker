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

from rooBroker.ui.interactive_layout import InteractiveLayout, ModelInfo as UIModelInfo
from rooBroker.roo_types.discovery import (
    DiscoveredModel,
    ModelInfo as DiscoveryModelInfo,
    OllamaModelInfo
)
from rooBroker.core.benchmarking import load_benchmarks_from_directory
from rooBroker.core.state import save_model_state, load_models_as_list
from rooBroker.core.mode_management import update_room_modes
from rooBroker.core.proxy import run_proxy_in_thread, DEFAULT_PROXY_PORT
from rooBroker.interfaces.lmstudio.client import LMStudioClient
from rooBroker.interfaces.ollama.client import OllamaClient
from rooBroker.actions import action_discover_models, action_run_benchmarks

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

def _get_available_providers(models: Sequence[Union[DiscoveredModel, Dict[str, Any]]]) -> List[str]:
    """Return unique providers based on model structure."""
    providers = set()
    for m in models:
        if m.get("family"):
            providers.add("lmstudio")
        elif m.get("name"):
            providers.add("ollama")
    return list(providers)

def _scroll_model_list(direction: int):
    """Scroll the model list up or down."""
    global model_list_scroll
    total_models = len(layout.models.models)
    visible_models = 10  # Adjust based on your display area
    
    if direction < 0:  # Scroll up
        model_list_scroll = max(0, model_list_scroll - 1)
    else:  # Scroll down
        max_scroll = max(0, total_models - visible_models)
        model_list_scroll = min(max_scroll, model_list_scroll + 1)
      # Update the model list display by accessing the models directly
    if layout.models.models:  # Only update if we have models
        visible_start = model_list_scroll
        visible_end = model_list_scroll + 10  # Show 10 models at a time
        visible_models = layout.models.models[visible_start:visible_end]
        layout.models.models.clear()
        for model in visible_models:
            layout.models.add_model(model)

# Interactive action functions (Ensure only one definition exists below)

async def discover_models_only():
    """Discover models and update the TUI layout."""
    global discovered_models

    layout.prompt.add_message("[yellow]Starting model discovery process...[/yellow]")
    layout.prompt.set_status("Discovering models...")

    try:
        layout.models.models.clear()
        discovered_models, status = await asyncio.to_thread(action_discover_models)
        
        if status["total_count"] > 0:
            # Add discovered models to the UI
            for model in discovered_models:
                model_id = model.get("id")
                if not model_id:
                    continue

                provider = "LM Studio"  # Default assumption
                if model.get("provider"):
                    provider = model.get("provider", "Unknown")
                elif model.get("name") and not model.get("family"):
                    provider = "Ollama"

                # Create UIModelInfo instance for TUI
                tui_model_info = UIModelInfo(
                    name=str(model_id),
                    status="discovered",
                    details=f"Provider: {provider}"
                )
                layout.models.add_model(tui_model_info)

            layout.prompt.add_message(f"[green]Successfully discovered {status['total_count']} models[/green]")
            layout.prompt.set_status(f"Discovered {status['total_count']} models")
        else:
            layout.prompt.add_message("[red]No supported models found[/red]")
            layout.prompt.set_status("No models discovered")

    except Exception as e:
        layout.prompt.add_message(f"[red]Error during discovery: {str(e)}[/red]")
        layout.prompt.set_status("Error during discovery")

async def manual_save_state():
    """Manually save the current model state."""
    global benchmark_results

    layout.prompt.add_message("[yellow]Saving model state...[/yellow]")
    try:
        if not benchmark_results:
            layout.prompt.add_message("[yellow]No benchmark results to save. Run benchmarks first.[/yellow]")
            return

        # Convert benchmark results to the format expected by save_model_state
        model_state_data = benchmark_results

        # Save model state
        # Use await asyncio.to_thread to prevent blocking the UI
        await asyncio.to_thread(
            save_model_state,
            model_state_data,
            file_path=".modelstate.json",
            message="Model state saved to .modelstate.json",
            console=console
        )
        layout.prompt.add_message("[green]Model state saved successfully.[/green]")

    except Exception as e:
        layout.prompt.add_message(f"[red]Error saving model state: {str(e)}[/red]")

async def update_roomodes_action():
    """Update roomodes configuration."""
    layout.prompt.add_message("[yellow]Updating roomodes...[/yellow]")
    try:
        # Call update_room_modes
        # Use await asyncio.to_thread to prevent blocking the UI
        success = await asyncio.to_thread(
            update_room_modes,
            modelstate_path=".modelstate.json",
            roomodes_path=".roomodes",
            settings_path="roo-code-settings.json",
            console=console
        )
        if success:
            layout.prompt.add_message("[green]Roomodes updated successfully.[/green]")
            layout.prompt.set_status("Roomodes updated")
        else:
            layout.prompt.add_message("[yellow]Roomodes update completed with some issues.[/yellow]")
            layout.prompt.set_status("Roomodes update had issues")

    except FileNotFoundError:
        layout.prompt.add_message("[red]Error: .modelstate.json not found. Save model state first.[/red]")
        layout.prompt.set_status("Error: model state not found")
    except Exception as e:
        layout.prompt.add_message(f"[red]Error updating roomodes: {str(e)}[/red]")
        layout.prompt.set_status("Error updating roomodes")

async def run_all_steps():
    """Run all steps in sequence."""
    layout.prompt.add_message("[yellow]Running all steps sequentially...[/yellow]")
    layout.prompt.set_status("Running all steps...")

    # 1. Discover models
    await discover_models_only()

    # Check if discovery was successful before proceeding
    if not discovered_models:
        layout.prompt.add_message("[red]Discovery failed. Aborting remaining steps.[/red]")
        layout.prompt.set_status("Discovery failed")
        return

    # 2. Benchmark models
    await run_benchmarks_with_config()

    # Check if benchmarking produced results before proceeding
    if not benchmark_results:
        layout.prompt.add_message("[red]Benchmarking failed or produced no results. Aborting remaining steps.[/red]")
        layout.prompt.set_status("Benchmarking failed")
        return

    # 3. Save model state
    await manual_save_state()
    
    # 4. Update roomodes
    await update_roomodes_action()
    
    layout.prompt.add_message("[green]All steps completed.[/green]")
    layout.prompt.set_status("All steps completed")

async def view_benchmark_results():
    """View benchmark results."""
    layout.prompt.add_message("[yellow]Loading benchmark results from .modelstate.json...[/yellow]")
    layout.prompt.set_status("Loading benchmark results...")

    try:
        # Load model state
        model_list = await asyncio.to_thread(load_models_as_list, ".modelstate.json", console)

        if not model_list:
            layout.prompt.add_message("[yellow]No benchmark results found in .modelstate.json[/yellow]")
            layout.prompt.set_status("No benchmark results found")
            return

        layout.prompt.add_message(f"[green]Loaded benchmark results for {len(model_list)} models[/green]")

        # Display summary for each model
        for model in model_list:
            model_id = model.get("model_id", "Unknown")
            last_updated = model.get("last_updated", "Unknown")

            # Get aggregated metrics if available
            agg_metrics = model.get("aggregated_metrics", {})
            overall_score = agg_metrics.get("overall_score", 0)
            test_pass_rate = agg_metrics.get("avg_test_pass_rate", 0)

            layout.prompt.add_message(f"Model: {model_id}")
            layout.prompt.add_message(f"  Last updated: {last_updated}")
            layout.prompt.add_message(f"  Overall score: {overall_score:.2f}")
            layout.prompt.add_message(f"  Test pass rate: {test_pass_rate:.2f}")

        layout.prompt.set_status(f"Loaded results for {len(model_list)} models")

    except FileNotFoundError:
        layout.prompt.add_message("[red]State file not found. Save model state first.[/red]")
        layout.prompt.set_status("Error: model state not found")
    except Exception as e:
        layout.prompt.add_message(f"[red]Error loading benchmark results: {str(e)}[/red]")
        layout.prompt.set_status("Error loading benchmark results")

async def launch_context_proxy():
    """Launch the context proxy server."""
    global proxy_server, proxy_stop_function

    layout.prompt.add_message("[yellow]Launching context proxy...[/yellow]")
    try:
        if proxy_server:
             layout.prompt.add_message("[yellow]Context proxy is already running.[/yellow]")
             return
        proxy_server, proxy_stop_function = await asyncio.to_thread(
            run_proxy_in_thread,
            provider_host="localhost",
            provider_port=1234,
            proxy_port=DEFAULT_PROXY_PORT,
            console=console
        )
        layout.prompt.add_message(f"[green]Proxy running on port {DEFAULT_PROXY_PORT}[/green]")

    except Exception as e:
        layout.prompt.add_message(f"[red]Error launching proxy: {str(e)}[/red]")

async def run_benchmarks_with_config():
    """Run benchmarks based on the configuration in app_state."""
    global app_state, discovered_models, benchmark_results

    layout.prompt.add_message("[yellow]Starting benchmark execution...[/yellow]")
    layout.prompt.set_status("Preparing benchmarks...")

    model_source = app_state['benchmark_config'].get('model_source', 'discovered')
    models_to_run: List[DiscoveredModel] = []

    if model_source == 'discovered':
        models_to_run = discovered_models
    elif model_source == 'state':
        try:
            raw_models = await asyncio.to_thread(load_models_as_list, ".modelstate.json", console)
            for raw_model in raw_models:
                if "id" in raw_model:
                    if "family" in raw_model:
                        models_to_run.append(cast(DiscoveredModel, DiscoveryModelInfo(id=raw_model["id"], family=raw_model.get("family", ""))))
                    elif "name" in raw_model:
                        models_to_run.append(cast(DiscoveredModel, OllamaModelInfo(id=raw_model["id"], name=raw_model["name"])))
        except FileNotFoundError:
            layout.prompt.add_message("[red]State file not found.[/red]")
            return
    elif model_source == 'manual':
        console.show_cursor(True)
        ids_str = console.input("Enter model IDs to benchmark (comma-separated): ")
        console.show_cursor(False)
        parsed_ids = [mid.strip() for mid in ids_str.split(',') if mid.strip()]
        for mid in parsed_ids:
            models_to_run.append(cast(DiscoveredModel, DiscoveryModelInfo(id=mid)))

    if not models_to_run:
        layout.prompt.add_message("[red]No models selected or found.[/red]")
        return

    # Determine provider preference
    provider_name = app_state['benchmark_config'].get('provider')
    if provider_name is None:
        providers_detected = _get_available_providers(models_to_run)
        if len(providers_detected) == 1:
            provider_name = providers_detected[0]
        # Add logic to prompt user if multiple providers or none detected
        elif len(providers_detected) > 1:
             layout.prompt.add_message("[yellow]Multiple providers detected. Please specify one in config.[/yellow]")
             return # Or prompt user
        else:
             layout.prompt.add_message("[red]Cannot determine provider. Specify in config or check models.[/red]")
             return

    filters = app_state['benchmark_config'].get('filters', {})
    num_samples = app_state['benchmark_config'].get('num_samples', 3)
    verbose = app_state['benchmark_config'].get('verbose', False)

    results = await asyncio.to_thread(
        action_run_benchmarks,
        model_source=model_source,
        model_ids=[m["id"] for m in models_to_run] if model_source == 'manual' else [],
        discovered_models_list=models_to_run if model_source == 'discovered' else [], # Pass discovered list
        benchmark_filters=filters,
        provider_preference=provider_name, # Pass determined provider
        run_options={"samples": num_samples, "verbose": verbose},
        benchmark_dir="./benchmarks",
        state_file=".modelstate.json",
    )

    if results:
        benchmark_results.extend(results)
        layout.prompt.add_message("[green]Benchmarking completed successfully.[/green]")
    else:
        layout.prompt.add_message("[yellow]Benchmarking finished, but no results were produced.[/yellow]")

def handle_menu_choice(menu_type: str):
    """Handle menu transitions."""
    global current_menu
    current_menu = menu_type

async def invoke_benchmark_option(option: str):
    """Wrapper to properly invoke benchmark options."""
    return await handle_benchmark_option(option)

MENU_OPTIONS = {
    'main': [
        ('1', 'Discover Models', discover_models_only),
        ('2', 'Run Benchmarks', lambda: handle_menu_choice('benchmark')),
        ('3', 'Save Model State', manual_save_state),
        ('4', 'Update Roomodes', update_roomodes_action),
        ('5', 'View Results', view_benchmark_results),
        ('6', 'Launch Proxy', launch_context_proxy),
        ('7', 'Run All Steps', run_all_steps),
        ('q', 'Quit', None)
    ],
    'benchmark': [
        ('1', 'All Benchmarks', lambda: invoke_benchmark_option('all')),
        ('2', 'Basic Benchmarks', lambda: invoke_benchmark_option('basic')),
        ('3', 'Advanced Benchmarks', lambda: invoke_benchmark_option('advanced')),
        ('4', 'Custom Benchmarks', lambda: invoke_benchmark_option('custom')),
        ('b', 'Back to Main Menu', lambda: handle_menu_choice('main')),
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

async def handle_benchmark_option(option: str):
    """Handle benchmark submenu options."""
    global app_state
    if option == 'all':
        app_state['benchmark_config']['filters'] = {}
    elif option == 'basic':
        app_state['benchmark_config']['filters'] = {'difficulty': 'basic'}
    elif option == 'advanced':
        app_state['benchmark_config']['filters'] = {'difficulty': 'advanced'}
    elif option == 'custom':
        # Show additional prompts for custom configuration
        console.print("\nCustom Benchmark Configuration")
        difficulties_str = ", ".join(str(d) for d in difficulties if d)
        types_str = ", ".join(str(t) for t in types if t)
        console.print(f"Available difficulties: {difficulties_str}")
        console.print(f"Available types: {types_str}")
        
        # Get difficulty
        diff = Prompt.ask("Select difficulty", choices=difficulties)
        type_ = Prompt.ask("Select type", choices=types)
        
        app_state['benchmark_config']['filters'] = {
            'difficulty': diff if diff != 'None' else None,
            'type': type_ if type_ != 'None' else None
        }
    
    # Now correctly await the async function
    await run_benchmarks_with_config()

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
                menu_items = MENU_OPTIONS[current_menu]                # Handle navigation
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
                    _scroll_model_list(-1)
                    continue
                
                if key == 's':  # Scroll model list down
                    _scroll_model_list(1)
                    continue

                if key == 'q':  # Quit
                    break

                if key == 'b' and current_menu != 'main':  # Back to main menu
                    current_menu = 'main'
                    selected = 0
                    continue                # Handle action selection
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