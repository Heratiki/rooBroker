"""
Interactive mode entry point for rooBroker.

This module provides a rich terminal user interface for the rooBroker application,
allowing users to discover, benchmark, and manage LM Studio models.
"""

import sys
import asyncio
from typing import NoReturn, Optional, List, Dict, Any, cast, Callable, Awaitable
from datetime import datetime, timedelta

from rich.live import Live
from rich.prompt import IntPrompt, Prompt
from rich.console import Console
from rich.text import Text
from rich.progress import Progress, TextColumn, BarColumn, MofNCompleteColumn, TimeRemainingColumn

import sys
# Cross-platform single-key reader
if sys.platform.startswith("win"):
    import msvcrt
    def read_single_key() -> str:
        """Read a single keypress on Windows."""
        return msvcrt.getwch()
else:
    import termios as _termios, tty as _tty
    def read_single_key() -> str:
        """Read a single keypress on Unix-like systems."""
        fd = sys.stdin.fileno()
        old_settings = _termios.tcgetattr(fd)  # type: ignore
        try:
            _tty.setraw(fd)  # type: ignore
            ch = sys.stdin.read(1)
        finally:
            _termios.tcsetattr(fd, _termios.TCSADRAIN, old_settings)  # type: ignore
        return ch


from rooBroker.ui.interactive_layout import InteractiveLayout, ModelInfo
from rooBroker.core.discovery import discover_all_models, discover_models_with_status
from rooBroker.core.benchmarking import run_standard_benchmarks, load_benchmarks_from_directory
from rooBroker.core.state import save_model_state, load_models_as_list
from rooBroker.core.mode_management import update_room_modes
from rooBroker.core.proxy import run_proxy_in_thread, DEFAULT_PROXY_PORT
from rooBroker.roo_types.discovery import DiscoveredModel
from rooBroker.interfaces.lmstudio.client import LMStudioClient
from rooBroker.interfaces.ollama.client import OllamaClient

# Initialize console and layout
console = Console()
layout = InteractiveLayout()

# Global state for discovered models
discovered_models: List[DiscoveredModel] = []
# Global state for benchmarking results
benchmark_results: List[Dict[str, Any]] = []
# Global proxy server state
proxy_server = None
proxy_stop_function = None
current_menu: str = "main"
app_state = {
    'benchmark_config': {
        'model_source': 'discovered'
    }
}

async def discover_models_only() -> None:
    """Discover available models without benchmarking."""
    global discovered_models
    
    layout.prompt.add_message("[yellow]Starting model discovery process...[/yellow]")
    layout.prompt.set_status("Discovering models...")
    
    try:
        # Clear the models panel
        layout.models.models.clear()
        
        # Update the prompt with progress
        layout.prompt.set_status("Connecting to LM Studio...")
        
        # Discover models with provider status
        discovered_models, status = discover_models_with_status()
        
        # Report discovery status by provider
        lm_studio_status = status["providers"]["LM Studio"]
        ollama_status = status["providers"]["Ollama"]
        total_models = status["total_count"]
        
        # Update UI with provider-specific statuses
        if lm_studio_status["status"]:
            layout.prompt.add_message(f"[green]Found {lm_studio_status['count']} models from LM Studio[/green]")
        else:
            error_msg = lm_studio_status["error"] or "unknown error"
            layout.prompt.add_message(f"[yellow]Warning: Failed to connect to LM Studio: {error_msg}[/yellow]")
        
        layout.prompt.set_status("Connecting to Ollama...")
        
        if ollama_status["status"]:
            layout.prompt.add_message(f"[green]Found {ollama_status['count']} models from Ollama[/green]")
        else:
            error_msg = ollama_status["error"] or "unknown error"
            layout.prompt.add_message(f"[yellow]Warning: Failed to connect to Ollama: {error_msg}[/yellow]")
        
        # Summarize discovery results
        if total_models > 0:
            # Success - at least some models were found
            layout.prompt.set_status(f"Discovered {total_models} models")
            layout.prompt.add_message(f"[green]Successfully discovered {total_models} models in total[/green]")
            
            # Add discovered models to the UI
            for model in discovered_models:
                # Handle different model types (LMStudio or Ollama)
                model_id = model.get("id")
                if not model_id:
                    continue
                    
                # Get provider based on the model type
                provider = "LM Studio"
                if model.get("name") and not model.get("family"):
                    provider = "Ollama"
                    
                layout.models.add_model(ModelInfo(
                    name=model_id,
                    status="discovered",
                    details=f"Provider: {provider}" 
                ))
            
            layout.prompt.add_message("[green]Model discovery complete.[/green]")
            layout.prompt.set_status(f"Discovered {total_models} models")
            
        else:
            # Total failure - no models found from any provider
            layout.prompt.add_message("[red]No supported models found[/red]")
            layout.prompt.add_message("[yellow]Make sure LM Studio or Ollama is running and try again.[/yellow]")
            layout.prompt.set_status("No models discovered")
        
    except Exception as e:
        layout.prompt.add_message(f"[red]Error during discovery: {str(e)}[/red]")
        layout.prompt.set_status("Error during discovery")


async def benchmark_models_only() -> None:
    """Benchmark the previously discovered models."""
    global discovered_models
    global benchmark_results

    layout.prompt.add_message("[yellow]Starting benchmarking process...[/yellow]")
    layout.prompt.set_status("Starting benchmarking...")

    # Load benchmarks
    console = Console()
    benchmarks = load_benchmarks_from_directory("./benchmarks")
    if not benchmarks:
        layout.prompt.add_message("[red]No benchmarks found in the specified directory.[/red]")
        layout.prompt.set_status("No benchmarks to run")
        return

    # Display benchmark options
    console.print("[bold]Available Benchmarks:[/bold]")
    for idx, benchmark in enumerate(benchmarks):
        console.print(f"[{idx + 1}] {benchmark['name']} ({benchmark['type']}, {benchmark['difficulty']})")

    # Prompt user for selection
    selection = Prompt.ask(
        "Enter the numbers of the benchmarks to run (comma-separated) or 'all' to run all",
        default="all"
    )

    # Filter benchmarks based on user selection
    if selection.lower() != "all":
        try:
            selected_indices = [int(i) - 1 for i in selection.split(",")]
            benchmarks = [benchmarks[i] for i in selected_indices if 0 <= i < len(benchmarks)]
        except (ValueError, IndexError):
            layout.prompt.add_message("[red]Invalid selection. Aborting benchmarking process.[/red]")
            layout.prompt.set_status("Invalid selection")
            return

    if not benchmarks:
        layout.prompt.add_message("[red]No benchmarks selected to run.[/red]")
        layout.prompt.set_status("No benchmarks to run")
        return

    # Determine available clients based on discovery status
    has_lm_studio = any(model.get("family") for model in discovered_models)
    has_ollama = any(model.get("name") and not model.get("family") for model in discovered_models)

    client = None
    if has_lm_studio:
        client = LMStudioClient()
        layout.prompt.add_message("Using LM Studio client for benchmarking")
    elif has_ollama:
        client = OllamaClient()
        layout.prompt.add_message("Using Ollama client for benchmarking")
    else:
        layout.prompt.add_message("[red]No supported model providers available for benchmarking based on discovered models.[/red]")
        layout.prompt.clear_status()
        return

    try:
        # Clear previous benchmark results if any
        benchmark_results.clear()

        # Setup Progress display within the Live context
        # Note: Using console.print inside Live might interfere.
        # Consider adding a dedicated panel in the layout for progress,
        # or temporarily stopping the Live display during benchmarking.
        # For simplicity, we'll print progress outside the Live TUI for now.
        with Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeRemainingColumn(),
            console=console,  # Use the main console
            transient=True  # Clear progress on exit
        ) as progress:
            # Run benchmarks using asyncio.to_thread
            results = await asyncio.to_thread(
                run_standard_benchmarks,
                client,
                discovered_models,
                benchmarks_to_run=benchmarks,
                progress=progress,  # Pass the progress object
                num_samples=3,  # Reduced samples for faster results
                verbose=False # Keep verbose off for interactive mode unless specifically needed
            )
            benchmark_results.extend(results)

        layout.prompt.add_message("[green]Benchmarking process completed successfully.[/green]")
        layout.prompt.set_status("Benchmarking completed")

    except Exception as e:
        layout.prompt.add_message(f"[red]Error during benchmarking: {str(e)}[/red]")
        layout.prompt.set_status("Error during benchmarking")


async def manual_save_state() -> None:
    """Manually save the current model state."""
    global benchmark_results
    
    layout.prompt.add_message("[yellow]Saving model state...[/yellow]")
    layout.prompt.set_status("Saving model state...")
    
    try:
        if not benchmark_results:
            layout.prompt.add_message("[yellow]No benchmark results to save. Run benchmarks first.[/yellow]")
            layout.prompt.set_status("No benchmark results to save")
            return
        
        # Convert benchmark results to the format expected by save_model_state
        model_state_data = []
        for result in benchmark_results:
            model_state_data.append(result)
        
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
        layout.prompt.set_status("Model state saved")
        
    except Exception as e:
        layout.prompt.add_message(f"[red]Error saving model state: {str(e)}[/red]")
        layout.prompt.set_status("Error saving model state")


async def update_roomodes_action() -> None:
    """Update roomodes configuration."""
    layout.prompt.add_message("[yellow]Updating roomodes...[/yellow]")
    layout.prompt.set_status("Updating roomodes...")
    
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


async def run_all_steps() -> None:
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
    await benchmark_models_only()

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


async def view_benchmark_results() -> None:
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
            
    except Exception as e:
        layout.prompt.add_message(f"[red]Error loading benchmark results: {str(e)}[/red]")
        layout.prompt.set_status("Error loading benchmark results")


async def launch_context_proxy() -> None:
    """Launch the context proxy server."""
    global proxy_server
    global proxy_stop_function
    
    layout.prompt.add_message("[yellow]Launching context proxy...[/yellow]")
    layout.prompt.set_status("Launching context proxy...")
    
    # If proxy is already running, notify user
    if proxy_server:
        layout.prompt.add_message("[yellow]Context proxy is already running.[/yellow]")
        layout.prompt.set_status("Context proxy already running")
        return
    
    try:
        # Launch the proxy server in a background thread
        proxy_result = await asyncio.to_thread(
            run_proxy_in_thread,
            provider_host="localhost",
            provider_port=1234,  # Default LM Studio port
            proxy_port=DEFAULT_PROXY_PORT,
            console=console
        )
        
        proxy_server, proxy_stop_function = proxy_result
        
        layout.prompt.add_message(f"[green]Context proxy running on port {DEFAULT_PROXY_PORT}[/green]")
        layout.prompt.add_message("[green]Configure API clients to use http://localhost:1235[/green]")
        layout.prompt.set_status(f"Proxy running on port {DEFAULT_PROXY_PORT}")
        
    except OSError as e:
        layout.prompt.add_message(f"[red]Error launching proxy: {str(e)}[/red]")
        layout.prompt.add_message(f"[yellow]Port {DEFAULT_PROXY_PORT} may already be in use.[/yellow]")
        layout.prompt.set_status("Error launching proxy")
    except Exception as e:
        layout.prompt.add_message(f"[red]Error launching proxy: {str(e)}[/red]")
        layout.prompt.set_status("Error launching proxy")


async def run_filtered_benchmarks(filter_criteria: dict) -> None:
    """Run a predefined set of benchmarks based on filter_criteria."""
    global benchmark_results, discovered_models, current_menu
    layout.prompt.add_message("[yellow]Starting filtered benchmarks...[/yellow]")
    layout.prompt.set_status("Running benchmarks")
    # Load and filter
    benchmarks = load_benchmarks_from_directory("./benchmarks")
    filtered = []
    for bm in benchmarks:
        if filter_criteria.get("all"):
            filtered = benchmarks
            break
        if filter_criteria.get("difficulty") and bm.get("difficulty") != filter_criteria["difficulty"]:
            continue
        if filter_criteria.get("tags"):
            tags = [t.lower() for t in bm.get("tags", [])]
            if not any(t in tags for t in filter_criteria["tags"]):
                continue
        if filter_criteria.get("type") and bm.get("type") != filter_criteria["type"]:
            continue
        filtered.append(bm)
    if not filtered:
        layout.prompt.add_message("[yellow]No benchmarks match criteria.[/yellow]")
        layout.prompt.set_status("No benchmarks match filters")
        current_menu = "main"
        layout.menu.show_main_menu()
        return
    # Choose client
    has_lm = any(m.get("family") for m in discovered_models)
    has_ol = any(m.get("name") and not m.get("family") for m in discovered_models)
    if has_lm:
        client = LMStudioClient()
    elif has_ol:
        client = OllamaClient()
    else:
        layout.prompt.add_message("[red]No providers available.[/red]")
        layout.prompt.set_status("No client")
        current_menu = "main"
        layout.menu.show_main_menu()
        return
    # Run benchmarks
    benchmark_results.clear()
    with Progress(
        TextColumn("[bold blue]{task.description}"), BarColumn(),
        MofNCompleteColumn(), TimeRemainingColumn(),
        console=console, transient=True
    ) as progress:
        results = await asyncio.to_thread(
            run_standard_benchmarks,
            client,
            discovered_models,
            benchmarks_to_run=filtered,
            progress=progress,
            num_samples=3,
            verbose=False
        )
        benchmark_results.extend(results)
    layout.prompt.add_message("[green]Filtered benchmarking complete.[/green]")
    layout.prompt.set_status("Benchmarks done")
    current_menu = "main"
    layout.menu.show_main_menu()


# Map menu options to their corresponding functions
# Type hint for the dictionary values
ActionType = Callable[[], Awaitable[None]]

MENU_ACTIONS: Dict[int, ActionType] = {
    1: discover_models_only,
    2: benchmark_models_only,
    3: manual_save_state,
    4: update_roomodes_action,
    5: run_all_steps,
    6: view_benchmark_results,
    7: launch_context_proxy
}


async def handle_menu_choice(choice: int) -> bool:
    """
    Handle the user's menu choice.
    
    Args:
        choice: The menu option chosen by the user (1-8)
    
    Returns:
        bool: True if the application should continue running, False if it should exit
    """
    if choice == 8:
        # Clean up before exiting
        if proxy_server and proxy_stop_function:
            layout.prompt.add_message("[yellow]Stopping proxy server...[/yellow]")
            layout.prompt.set_status("Stopping proxy server...")
            await asyncio.to_thread(proxy_stop_function)
            
        layout.prompt.add_message("[yellow]Exiting...[/yellow]")
        layout.prompt.set_status("Exiting...")
        return False
    elif choice in MENU_ACTIONS:
        layout.menu.selected = choice - 1  # Convert to 0-based index
        await MENU_ACTIONS[choice]()
    else:
        layout.prompt.add_message(f"[red]Invalid choice: {choice}. Please select an option from 1 to 8.[/red]")
        layout.prompt.set_status("Invalid choice")

    
    return True


async def interactive_main() -> None:
    global current_menu, app_state
    """Main entry point for the interactive TUI."""
    # Define cleanup helper function
    def _cleanup_resources():
        global proxy_stop_function
        try:
            if proxy_stop_function is not None:
                console.print("[yellow]Stopping proxy server...[/yellow]")
                proxy_stop_function()
        except Exception as e:
            console.print(f"[red]Error during cleanup: {e}[/red]")
            
    try:
        with Live(layout.layout, refresh_per_second=10, screen=True):
            layout.prompt.add_message("Welcome to rooBroker Interactive Mode!")
            layout.prompt.add_message("Select an option (1-8) to begin...")
            layout.prompt.set_status("Ready")
            
            running = True
            try:
                while running:
                    # Read a single keypress without requiring Enter
                    key = read_single_key()
                    
                    if current_menu == "main":
                        if key == '1':
                            # Discover models
                            layout.menu.selected = 0  # Option 1 is at index 0
                            await discover_models_only()
                        elif key == '2':
                            # Benchmark models
                            current_menu = "benchmark_submenu"
                            layout.menu.show_benchmark_submenu()
                        elif key == '3':
                            # Save state
                            layout.menu.selected = 2  # Option 3 is at index 2
                            await manual_save_state()
                        elif key == '4':
                            # Update roomodes
                            layout.menu.selected = 3  # Option 4 is at index 3
                            await update_roomodes_action()
                        elif key == '5':
                            # Run all steps
                            layout.menu.selected = 4  # Option 5 is at index 4
                            await run_all_steps()
                        elif key == '6':
                            # View benchmark results
                            layout.menu.selected = 5  # Option 6 is at index 5
                            await view_benchmark_results()
                        elif key == '7':
                            # Launch context proxy
                            layout.menu.selected = 6  # Option 7 is at index 6
                            await launch_context_proxy()
                        elif key == '8':
                            # Exit
                            layout.menu.selected = 7  # Option 8 is at index 7
                            _cleanup_resources()  # Clean up resources before exiting
                            return  # Exit the program
                        elif key == '\x1b':  # Escape key
                            console.print("[yellow]Escape key pressed. Exiting...[/yellow]")
                            _cleanup_resources()  # Clean up resources before exiting
                            running = False
                            break
                        else:
                            # Invalid key, show message
                            layout.prompt.add_message("[red]Invalid key. Please press 1-8, or Q to quit.[/red]")
                            layout.prompt.set_status("Invalid key pressed")
            
                    elif current_menu == "benchmark_submenu":
                        if key == '1':
                            await run_filtered_benchmarks({'all': True})
                        elif key == '2':
                            await run_filtered_benchmarks({'difficulty': 'basic', 'tags': ['python']})
                        elif key == '3':
                            await run_filtered_benchmarks({'difficulty': 'advanced', 'tags': ['python']})
                        elif key == '4':
                            await run_filtered_benchmarks({'type': 'context'})
                        elif key == '5':
                            current_menu = "main"
                            layout.menu.show_main_menu()
                        elif key == '6':  # new config option in submenu
                            current_menu = "benchmark_config"
                            layout.menu.show_benchmark_config_menu()
                            layout.prompt.add_message(
                                f"Current model source: {app_state['benchmark_config']['model_source']}"
                            )
                    
                    elif current_menu == "benchmark_config":
                        # 1 = Set Model Source
                        if key == '1':
                            current_menu = "benchmark_model_source"
                            layout.menu.show_model_source_menu()
                            layout.prompt.add_message(
                                f"Select a model source (current: {app_state['benchmark_config']['model_source']})"
                            )
                        # ...handle other config options...
                        elif key == '4':
                            current_menu = "benchmark_submenu"
                            layout.menu.show_benchmark_submenu()
                    
                    elif current_menu == "benchmark_model_source":
                        if key == '1':
                            app_state['benchmark_config']['model_source'] = 'discovered'
                            layout.prompt.add_message("[green]Model source set to: discovered[/green]")
                        elif key == '2':
                            app_state['benchmark_config']['model_source'] = 'state'
                            layout.prompt.add_message("[green]Model source set to: state[/green]")
                        elif key == '3':
                            app_state['benchmark_config']['model_source'] = 'manual'
                            layout.prompt.add_message("[yellow]Manual ID entry will be implemented later.[/yellow]")
                        elif key == '4':
                            pass  # back without change
                        # return to config menu
                        current_menu = "benchmark_config"
                        layout.menu.show_benchmark_config_menu()
            
            except KeyboardInterrupt:
                console.print("\n[yellow]Ctrl+C detected. Exiting...[/yellow]")
                _cleanup_resources()  # Use the helper function for consistency
            
            layout.prompt.add_message("[green]Thank you for using rooBroker![/green]")
            layout.prompt.set_status("Exited interactive mode")
    
    except Exception as e:
        console.print(f"[red]An unexpected error occurred in the main loop: {str(e)}[/red]")
        # Potentially log the full traceback here
        raise


def main() -> int:
    """
    Main synchronous entry point for interactive mode.
    
    Returns:
        int: Exit code (0 for success, non-zero for errors)
    """
    try:
        asyncio.run(interactive_main())
        return 0
    except KeyboardInterrupt:
        # Primary cleanup happens in interactive_main before the exception propagates
        console.print("[yellow]Program terminated by keyboard interrupt.[/yellow]")
        return 1
    except Exception as e:
        console.print(f"[red]Fatal Error: {str(e)}[/red]")
        # Consider logging the traceback here for debugging
        return 1
