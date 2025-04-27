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
from rich.prompt import IntPrompt
from rich.console import Console
from rich.text import Text

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
from rooBroker.core.benchmarking import run_standard_benchmarks
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

    if not discovered_models:
        layout.prompt.add_message("[yellow]No models discovered yet. Run discovery first (Option 1).[/yellow]")
        layout.prompt.set_status("No models to benchmark")
        return

    # Determine available clients based on discovery status (reuse logic from original function)
    # We need the status dictionary again, perhaps store it globally or re-run a quick check?
    # For now, let's assume we can determine the client based on discovered_models
    
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
        
        # Run benchmarks (this is a blocking operation)
        # We'll simulate progress updates for each model
        model_count = len(discovered_models)
        completed_models = 0
        
        # Use asyncio to run benchmarks in chunks while updating UI
        for idx, model in enumerate(discovered_models):
            model_id = model.get("id")
            if not model_id:
                continue
                
            # Get provider based on the model type
            provider = "LM Studio"
            if model.get("name") and not model.get("family"):
                provider = "Ollama"
            
            # Update the model status to "benchmarking"
            for ui_model in layout.models.models:
                if ui_model.name == model_id:
                    ui_model.status = "benchmarking"
                    break
            
            # Update benchmarking status
            start_time = datetime.now()
            estimated_duration = timedelta(minutes=2)  # Estimated time per model
            
            # Show benchmarking progress
            layout.benchmarking.current_model = model_id
            layout.benchmarking.progress = 0.0
            
            # Update status in Prompt Improvement panel
            layout.prompt.set_status(f"Benchmarking {model_id}...")
            layout.prompt.add_message(f"Benchmarking model: {model_id}...")
            
            # We'll benchmark this model in the background and update progress
            # Create a task for running the benchmark
            # For real benchmarking, we'd need to split it into steps or use thread pool
            model_result = None
            
            try:
                # Simulate benchmarking progress since we can't easily get progress from the actual benchmark
                progress_steps = 10
                step = 0
                for step in range(progress_steps + 1):
                    progress = step / progress_steps
                    layout.benchmarking.progress = progress
                    
                    # Calculate time remaining
                    elapsed = datetime.now() - start_time
                    if progress > 0:
                        total_estimated = elapsed / progress
                        remaining = total_estimated - elapsed
                        remaining_str = f"{int(remaining.total_seconds() // 60):02d}:{int(remaining.total_seconds() % 60):02d}"
                    else:
                        remaining_str = "--:--"
                        
                    layout.benchmarking.time_remaining = remaining_str
                    
                    # Only do a real pause for simulation steps, not during actual benchmarking
                    if step < progress_steps:
                        await asyncio.sleep(0.5)  # Simulate progress
                
                # At this point we'd normally have benchmark results
                # For now we run one model at a time in a blocking way
                # In a full implementation, we would use a thread pool
                if step == progress_steps:
                    # In a real implementation, we'd check if we've reached the last step
                    # and then run the actual benchmark
                    single_model_results = await asyncio.to_thread(
                        run_standard_benchmarks, 
                        client, 
                        [model],
                        num_samples=3  # Reduced samples for faster results
                    )
                    
                    if single_model_results and len(single_model_results) > 0:
                        model_result = single_model_results[0]
                        benchmark_results.append(model_result)
                
                # Update model status
                for ui_model in layout.models.models:
                    if ui_model.name == model_id:
                        if model_result:
                            # Extract the aggregated score if available
                            agg_metrics = model_result.get("aggregated_metrics", {})
                            score = agg_metrics.get("overall_score", 0)
                            ui_model.status = f"score: {score:.2f}"
                            ui_model.details = f"Provider: {provider}, Benchmarked"
                        else:
                            ui_model.status = "failed"
                        break
                
                completed_models += 1
                overall_progress = completed_models / model_count
                
                layout.prompt.add_message(f"[green]Completed benchmarking for {model_id}[/green]")
                layout.prompt.add_message(f"Overall progress: {completed_models}/{model_count} models")
                
            except Exception as e:
                layout.prompt.add_message(f"[red]Error benchmarking {model_id}: {str(e)}[/red]")
                for ui_model in layout.models.models:
                    if ui_model.name == model_id:
                        ui_model.status = "failed"
                        break
        
        # Reset benchmarking display when done
        layout.benchmarking.current_model = None
        layout.benchmarking.progress = 0.0
        layout.benchmarking.time_remaining = None
        
        layout.prompt.add_message(f"[green]Benchmarking complete for {completed_models}/{model_count} models[/green]")
        layout.prompt.set_status(f"Benchmarked {completed_models}/{model_count} models")

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
    """Main entry point for the interactive TUI."""
    try:
        with Live(layout.layout, refresh_per_second=10, screen=True):            # Initialize empty models panel
            layout.prompt.add_message("Welcome to rooBroker Interactive Mode!")
            layout.prompt.add_message("Select an option (1-8) to begin...")
            layout.prompt.set_status("Ready")
            
            running = True
            while running:
                # Read a single keypress without requiring Enter
                key = await asyncio.get_event_loop().run_in_executor(None, read_single_key)
                # Handle Ctrl+C (Windows returns '\x03')
                if key == '\x03':
                    layout.prompt.add_message("\n[yellow]Ctrl+C detected. Exiting...[/yellow]")
                    running = False
                    await handle_menu_choice(8)
                    break
                # Handle scroll and quit keys
                if key.lower() in ['w', 's', 'q']:
                    # For 'w'/'s', scrolling; for 'q', quit
                    cont = layout.handle_input(key)
                    if not cont:
                        running = False
                        await handle_menu_choice(8)
                        break
                    continue
                # Handle numeric menu selections
                if key.isdigit():
                    choice = int(key)
                    running = await handle_menu_choice(choice)
                    continue
                # Ignore other keys
                # Optionally, display instruction hint
                layout.prompt.add_message("[dim]Press 1-8 to select, W/S to scroll, Q to quit[/dim]")
                layout.prompt.set_status("Waiting for input")
                
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
        # Already handled in interactive_main, just ensure clean exit code
        console.print("\n[yellow]Program terminated by user.[/yellow]")
        return 1
    except Exception as e:
        console.print(f"[red]Fatal Error: {str(e)}[/red]")
        # Consider logging the traceback here for debugging
        return 1
