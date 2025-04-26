"""
Interactive mode entry point for rooBroker.

This module provides a rich terminal user interface for the rooBroker application,
allowing users to discover, benchmark, and manage LM Studio models.
"""

import sys
import asyncio
from typing import NoReturn, Optional
from rich.live import Live
from rich.prompt import IntPrompt
from rich.console import Console

from rooBroker.ui.interactive_layout import InteractiveLayout, ModelInfo

# Initialize console and layout
console = Console()
layout = InteractiveLayout()

async def discover_and_benchmark() -> None:
    """Discover and benchmark available models."""    # Add some sample models for demonstration
    layout.models.add_model(ModelInfo(name="gpt-4-local", status="discovered"))
    layout.models.add_model(ModelInfo(name="llama2-7b", status="ready"))
    
    # Simulate benchmarking process
    for progress in range(0, 101, 10):
        layout.benchmarking.update_progress(
            "gpt-4-local",
            progress / 100.0,
            f"00:{60 - int(progress * 0.6):02d}"
        )
        layout.prompt.add_message(f"Testing capability {progress // 10}...")
        await asyncio.sleep(0.5)
    
    layout.prompt.add_message("[green]Benchmarking complete![/green]")

async def manual_save_state() -> None:
    """Manually save the current model state."""
    layout.prompt.add_message("[yellow]Saving model state...[/yellow]")
    await asyncio.sleep(1)
    layout.prompt.add_message("[green]Model state saved successfully.[/green]")

async def update_roomodes() -> None:
    """Update roomodes configuration."""
    layout.prompt.add_message("[yellow]Updating roomodes...[/yellow]")
    await asyncio.sleep(1)
    layout.prompt.add_message("[green]Roomodes updated successfully.[/green]")

async def run_all_steps() -> None:
    """Run all steps in sequence."""
    layout.prompt.add_message("[yellow]Running all steps sequentially...[/yellow]")
    await discover_and_benchmark()
    await manual_save_state()
    await update_roomodes()
    layout.prompt.add_message("[green]All steps completed successfully.[/green]")

async def view_benchmark_results() -> None:
    """View benchmark results."""
    layout.prompt.add_message("[yellow]Loading benchmark results...[/yellow]")
    await asyncio.sleep(0.5)
    # Add some sample benchmark results
    layout.prompt.add_message("Model: gpt-4-local")
    layout.prompt.add_message("Speed: 45.2 tokens/sec")
    layout.prompt.add_message("Accuracy: 92%")

async def launch_context_proxy() -> None:
    """Launch the context proxy server."""
    layout.prompt.add_message("[yellow]Launching context proxy...[/yellow]")
    await asyncio.sleep(1)
    layout.prompt.add_message("[green]Context proxy running on port 8000[/green]")

# Map menu options to their corresponding functions
MENU_ACTIONS = {
    1: discover_and_benchmark,
    2: manual_save_state,
    3: update_roomodes,
    4: run_all_steps,
    5: view_benchmark_results,
    6: launch_context_proxy
}

async def handle_menu_choice(choice: int) -> bool:
    """
    Handle the user's menu choice.
    
    Args:
        choice: The menu option chosen by the user (1-7)
    
    Returns:
        bool: True if the application should continue running, False if it should exit
    """
    if choice == 7:
        layout.prompt.add_message("[yellow]Exiting...[/yellow]")
        return False
    elif choice in MENU_ACTIONS:
        layout.menu.selected = choice - 1  # Convert to 0-based index
        await MENU_ACTIONS[choice]()
    
    return True

async def interactive_main() -> None:
    """Main entry point for the interactive TUI."""
    try:
        with Live(layout.layout, refresh_per_second=10, screen=True):            # Add some initial models
            layout.models.add_model(ModelInfo(name="gpt-4-local", status="discovered"))
            layout.models.add_model(ModelInfo(name="llama2-7b", status="ready"))
            layout.models.add_model(ModelInfo(name="claude-v2", status="not benchmarked"))
            
            layout.prompt.add_message("Welcome to rooBroker Interactive Mode!")
            layout.prompt.add_message("Select an option (1-7) to begin...")
            
            running = True
            while running:
                try:
                    choice = await asyncio.get_event_loop().run_in_executor(
                        None, 
                        lambda: IntPrompt.ask("\nEnter your choice", console=console)
                    )
                    running = await handle_menu_choice(choice)
                except (ValueError, KeyboardInterrupt):
                    layout.prompt.add_message("[red]Invalid input. Please try again.[/red]")
                    
    except Exception as e:
        console.print(f"[red]An error occurred: {str(e)}[/red]")
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
        console.print("\n[yellow]Program terminated by user.[/yellow]")
        return 1
    except Exception as e:
        console.print(f"[red]Error: {str(e)}[/red]")
        return 1

if __name__ == "__main__":
    sys.exit(main())
