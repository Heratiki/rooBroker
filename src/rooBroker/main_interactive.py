"""
Interactive mode entry point for rooBroker.

This module provides a rich terminal user interface for the rooBroker application,
allowing users to discover, benchmark, and manage LM Studio models.
"""

import sys
import asyncio
from typing import NoReturn, Optional, List, Dict, Any, cast, Callable, Awaitable, Sequence, Union
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
        'model_source': 'discovered',
        'provider': None,
        'provider_options': []
    }
}

difficulties = ["basic", "intermediate", "advanced", None]
types = ["statement", "function", "class", "algorithm", "context", None]

def _get_available_providers(
    models: Sequence[Union[DiscoveredModel, Dict[str, Any]]]
) -> List[str]:
    """Return unique providers based on model structure."""
    providers = set()
    for m in models:
        if m.get("family"):
            providers.add("lmstudio")
        elif m.get("name"):
            providers.add("ollama")
    return list(providers)


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


async def run_benchmarks_with_config() -> None:
    """Run benchmarks based on the configuration in app_state."""
    global app_state, discovered_models, benchmark_results, current_menu

    layout.prompt.add_message("[yellow]Starting benchmark execution...[/yellow]")
    layout.prompt.set_status("Preparing benchmarks...")

    # Model selection
    model_source = app_state['benchmark_config'].get('model_source', 'discovered')
    models_to_run: List[DiscoveredModel] = []

    if model_source == 'discovered':
        models_to_run = discovered_models
        layout.prompt.add_message("[green]Using discovered models for benchmarking.[/green]")
    elif model_source == 'state':
        try:
            raw_models = await asyncio.to_thread(load_models_as_list, ".modelstate.json", console)
            models_to_run = [DiscoveredModel(**model) for model in raw_models]
            if not models_to_run:
                layout.prompt.add_message("[yellow]No models found in state file.[/yellow]")
                return
            layout.prompt.add_message("[green]Loaded models from state file.[/green]")
        except FileNotFoundError:
            layout.prompt.add_message("[red]State file not found. Save model state first.[/red]")
            return
    elif model_source == 'manual':
        console.show_cursor(True)
        ids_str = console.input("Enter model IDs to benchmark (comma-separated): ")
        console.show_cursor(False)
        parsed_ids = [mid.strip() for mid in ids_str.split(',') if mid.strip()]
        if parsed_ids:
            models_to_run = [{"id": mid, "name": mid} for mid in parsed_ids]
            layout.prompt.add_message("[green]Using manually entered model IDs for benchmarking.[/green]")
        else:
            layout.prompt.add_message("[red]No valid model IDs entered. Aborting.[/red]")
            return

    if not models_to_run:
        layout.prompt.add_message("[red]No models selected or found.[/red]")
        return

    # Provider client selection
    provider_name = app_state['benchmark_config'].get('provider')
    if provider_name is None:
        providers_detected = _get_available_providers(models_to_run)
        if len(providers_detected) == 1:
            provider_name = providers_detected[0]
            app_state['benchmark_config']['provider'] = provider_name
        else:
            layout.prompt.add_message("[red]Provider not selected or ambiguous. Aborting.[/red]")
            return

    if provider_name == 'lmstudio':
        client = LMStudioClient()
    elif provider_name == 'ollama':
        client = OllamaClient()
    else:
        layout.prompt.add_message("[red]Invalid provider selected. Aborting.[/red]")
        return

    layout.prompt.add_message(f"[green]Using provider: {provider_name}.[/green]")

    # Benchmark filtering
    all_benchmarks = load_benchmarks_from_directory("./benchmarks")
    filters = app_state['benchmark_config'].get('filters', {})
    benchmarks_to_run = [
        bm for bm in all_benchmarks
        if (not filters.get('tags') or any(tag in bm.get('tags', []) for tag in filters['tags']))
        and (not filters.get('difficulty') or bm.get('difficulty') == filters['difficulty'])
        and (not filters.get('type') or bm.get('type') == filters['type'])
    ]

    if not benchmarks_to_run:
        layout.prompt.add_message("[red]No benchmarks match filters. Aborting.[/red]")
        return

    layout.prompt.add_message(f"[green]Selected {len(benchmarks_to_run)} benchmarks to run.[/green]")

    # Run parameters
    num_samples = app_state['benchmark_config'].get('samples', 20)
    verbose = app_state['benchmark_config'].get('verbose', False)
    layout.prompt.add_message(f"[green]Number of samples: {num_samples}, Verbose: {verbose}.[/green]")

    # Execute benchmarks
    layout.prompt.set_status("Running benchmarks...")
    benchmark_results.clear()

    try:
        with Progress(
            TextColumn("[bold blue]{task.description}"), BarColumn(),
            MofNCompleteColumn(), TimeRemainingColumn(),
            console=console, transient=True
        ) as progress:
            results = await asyncio.to_thread(
                run_standard_benchmarks,
                client=client,
                models_to_benchmark=models_to_run,
                benchmarks_to_run=benchmarks_to_run,
                progress=progress,
                num_samples=num_samples,
                verbose=verbose
            )
            benchmark_results.extend(results)
        layout.prompt.add_message("[green]Benchmark run complete.[/green]")
    except Exception as e:
        layout.prompt.add_message(f"[red]Error during benchmark execution: {str(e)}[/red]")
    finally:
        current_menu = "main"
        layout.menu.show_main_menu()


def _cleanup_resources() -> None:
    """Clean up any resources before exiting."""
    global proxy_server, proxy_stop_function
    
    if proxy_stop_function:
        try:
            proxy_stop_function()
            proxy_server = None
            proxy_stop_function = None
        except Exception as e:
            console.print(f"[yellow]Warning: Error while stopping proxy: {str(e)}[/yellow]")


# Map menu options to their corresponding functions
# Type hint for the dictionary values
ActionType = Callable[[], Awaitable[None]]

MENU_ACTIONS: Dict[int, ActionType] = {
    1: discover_models_only,
    3: run_benchmarks_with_config,
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


async def handle_benchmark_option(key_num: int) -> None:
    """Handle benchmark submenu options."""
    if key_num == 1:
        await benchmark_models_only()
    elif key_num == 2:
        # Run basic benchmarks
        await run_filtered_benchmarks({"difficulty": "basic"})
    elif key_num == 3:
        # Run advanced benchmarks
        await run_filtered_benchmarks({"difficulty": "advanced"})
    elif key_num == 4:
        # Run context benchmarks
        await run_filtered_benchmarks({"type": "context"})
        
# Main interactive function 
async def interactive_main() -> None:
    global current_menu
    
    # Create the live display
    layout_renderable = layout.render()
    
    with Live(layout_renderable, console=console, screen=True, refresh_per_second=10) as live:
        try:
            # Show initial menu
            layout.menu.show_main_menu()
            
            while True:
                # Get a single keypress (normalized to lowercase)
                key = read_single_key()
                
                # Handle quit command globally
                if key.lower() == 'q':
                    layout.prompt.add_message("[yellow]Exiting...[/yellow]")
                    _cleanup_resources()
                    break
                
                # Handle digit-based menu options
                if key.isdigit():
                    key_num = int(key)
                    
                    if current_menu == "main":
                        if 1 <= key_num <= 8:
                            if key_num == 8:  # Exit option
                                layout.prompt.add_message("[yellow]Exiting...[/yellow]")
                                _cleanup_resources()
                                break
                            # Other main menu options
                            if key_num in MENU_ACTIONS:
                                await MENU_ACTIONS[key_num]()
                            else:
                                layout.prompt.set_status("Invalid option")
                    
                    # Handle other menus similarly
                    elif current_menu == "benchmark_submenu":
                        if 1 <= key_num <= 6:
                            if key_num == 5:
                                current_menu = "main"
                                layout.menu.show_main_menu()
                            elif key_num == 6:
                                current_menu = "benchmark_config"
                                layout.menu.show_benchmark_config_menu()
                            else:
                                await handle_benchmark_option(key_num)
                    
                    # ... other menu handlers ...
                else:
                    layout.prompt.set_status("Invalid key. Please press 1-8, or Q to quit.")
                
                # Update the live display
                layout_renderable = layout.render()
                live.update(layout_renderable)
                
                await asyncio.sleep(0.1)  # Small delay to prevent CPU hogging
                
        except Exception as e:
            layout.prompt.add_message(f"[red]Error in menu handling: {str(e)}[/red]")
            raise


def main() -> int:
    print("DEBUG: Starting main()") # Basic print for debugging
    try:
        print("DEBUG: About to run interactive_main()")
        asyncio.run(interactive_main())
        return 0
    except KeyboardInterrupt:
        print("DEBUG: KeyboardInterrupt caught")
        console.print("[yellow]Program terminated by keyboard interrupt.[/yellow]")
        return 1
    except Exception as e:
        print(f"DEBUG: Exception caught: {str(e)}")
        import traceback
        traceback.print_exc()
        console.print(f"[red]Fatal Error: {str(e)}[/red]")
        return 1

if __name__ == "__main__":
    print("DEBUG: __main__ block entered")
    import sys
    sys.exit(main())
