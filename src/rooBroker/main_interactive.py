"""Interactive interface entry point for rooBroker.

This module provides the interactive menu-driven interface for rooBroker,
allowing users to discover models, run benchmarks, update room modes,
and run the proxy server through a user-friendly menu system.
"""

import sys
from rich.console import Console
from rich.prompt import IntPrompt, Prompt
from rich.panel import Panel

from rooBroker.core.discovery import discover_all_models
from rooBroker.core.benchmarking import run_standard_benchmarks
from rooBroker.core.big_bench import run_bigbench_benchmarks
from rooBroker.core.state import save_model_state
from rooBroker.core.mode_management import update_room_modes
from rooBroker.core.proxy import run_proxy_server, ProxyConfig
from rooBroker.interfaces.lmstudio.client import LMStudioClient
from rooBroker.ui.common_formatters import pretty_print_models, pretty_print_benchmarks
from rooBroker.ui.interactive_utils import display_menu, select_models_by_number


def main_menu():
    """Show the main menu and handle user input."""
    console = Console()
    
    while True:
        display_menu()
        choice = IntPrompt.ask("Select an option", default=1)
        
        if choice == 1:  # Discover & Benchmark
            try:
                console.print("[cyan]Discovering models...[/cyan]")
                models = discover_all_models()
                console.print(f"[green]Found {len(models)} models![/green]")
                
                # Show models with numbers and allow direct selection
                selected_models = select_models_by_number(models)
                if not selected_models:
                    console.print("[yellow]No models selected for benchmarking.[/yellow]")
                    continue # Go back to menu                console.print("[cyan]Running standard benchmarks for selected models...[/cyan]")
                # Initialize the LMStudio client and run standard benchmarks
                lm_client = LMStudioClient()
                results = run_standard_benchmarks(lm_client, selected_models, console=console)
                console.print("[green]Standard benchmarking complete![/green]")
                pretty_print_benchmarks(results) # Show standard results

                # Now, ask about Big Bench Hard
                if Prompt.ask("\nRun additional BIG-BENCH-HARD benchmarks (can be slow)?", choices=["y", "n"], default="n") == "y":
                    console.print("[cyan]Running BIG-BENCH-HARD benchmarks...[/cyan]")
                    # Run BBH and merge results into the existing 'results' list
                    results = run_bigbench_benchmarks(lm_client, selected_models, results, console=console)
                    console.print("[green]BIG-BENCH-HARD benchmarking complete![/green]")
                    pretty_print_benchmarks(results) # Show updated results with BBH scores
                else:
                     console.print("[cyan]Skipping BIG-BENCH-HARD benchmarks.[/cyan]")
            except Exception as e:
                console.print(f"[red]Error discovering/benchmarking models: {e}[/red]")
        
        elif choice == 2:  # Manual Save
            try:
                console.print("[cyan]Discovering models for state saving...[/cyan]")
                models = discover_all_models()
                save_model_state(models, message="Model state manually saved", console=console)
            except Exception as e:
                console.print(f"[red]Error saving model state: {e}[/red]")
        
        elif choice == 3:  # Update Roomodes
            try:
                console.print("[cyan]Updating .roomodes file...[/cyan]")
                success = update_room_modes(console=console)
                if success:
                    console.print("[green]Successfully updated .roomodes file![/green]")
                else:
                    console.print("[yellow]No changes made to .roomodes file.[/yellow]")
            except Exception as e:
                console.print(f"[red]Error updating .roomodes: {e}[/red]")
        
        elif choice == 4:  # Run Context Optimization Proxy
            try:
                # Allow user to customize port
                port = IntPrompt.ask(
                    "Enter port for the proxy server",
                    default=1235
                )

                # Show information panel
                console.print(Panel.fit(
                    "[bold]The proxy will now start running.[/bold]\n\n"
                    f"Point your application to [cyan]http://localhost:{port}[/cyan] instead of http://localhost:1234\n\n"
                    "Press Ctrl+C to stop the proxy and return to the menu.",
                    title="Context Optimization Proxy",
                    border_style="green"
                ))

                # Configure and start the proxy server
                config = ProxyConfig(
                    port=port,
                    target_url="http://localhost:1234",
                    verbose=True
                )
                
                run_proxy_server(config)
            except KeyboardInterrupt:
                console.print("[yellow]Proxy server stopped by user.[/yellow]")
            except Exception as e:
                console.print(f"[red]Error running proxy server: {e}[/red]")
        
        elif choice == 5:  # Run All Steps
            try:
                # Step 1: Discover and benchmark
                console.print("[cyan]Step 1: Discovering models...[/cyan]")
                models = discover_all_models()
                console.print(f"[green]Found {len(models)} models![/green]")
                pretty_print_models(models)
                  console.print("[cyan]Benchmarking all models...[/cyan]")
                # Initialize the LMStudio client and run standard benchmarks
                lm_client = LMStudioClient()
                results = run_standard_benchmarks(lm_client, models, console=console)
                console.print("[green]Standard benchmarking complete![/green]")
                pretty_print_benchmarks(results)
                
                # Ask about Big Bench Hard
                if Prompt.ask("\nRun BIG-BENCH-HARD benchmarks as well (can be slow)?", choices=["y", "n"], default="n") == "y":
                    console.print("[cyan]Running BIG-BENCH-HARD benchmarks...[/cyan]")
                    results = run_bigbench_benchmarks(lm_client, models, results, console=console)
                    console.print("[green]BIG-BENCH-HARD benchmarking complete![/green]")
                    pretty_print_benchmarks(results)
                else:
                    console.print("[cyan]Skipping BIG-BENCH-HARD benchmarks.[/cyan]")
                
                # Step 2: Update roomodes
                console.print("[cyan]Step 2: Updating .roomodes file...[/cyan]")
                success = update_room_modes(console=console)
                if success:
                    console.print("[green]Successfully updated .roomodes file![/green]")
                else:
                    console.print("[yellow]No changes made to .roomodes file.[/yellow]")
                
                console.print(Panel.fit(
                    "[bold green]All steps completed successfully![/bold green]\n\n"
                    "You can now run the Context Optimization Proxy (Option 4) to maximize context windows.",
                    border_style="green"
                ))
            except Exception as e:
                console.print(f"[red]Error running workflow: {e}[/red]")
        
        elif choice == 6:  # Exit
            console.print("[cyan]Exiting...[/cyan]")
            return 0
        
        else:
            console.print("[yellow]Invalid option selected. Please try again.[/yellow]")
        
        console.print()


def main():
    """Main function that handles interactive mode."""
    try:
        return main_menu()
    except KeyboardInterrupt:
        Console().print("\n[yellow]Program interrupted by user.[/yellow]")
        return 1
    except Exception as e:
        Console().print(f"\n[red]Unexpected error: {e}[/red]")
        return 1


if __name__ == "__main__":
    # When running main_interactive.py directly, the src directory needs to be in PYTHONPATH
    # For direct execution `python src/rooBroker/main_interactive.py`, Python might not find the modules.
    # A common workaround for direct script execution is to adjust sys.path,
    # but the best practice is to run it as a module: `python -m rooBroker.main_interactive` 
    # from the `src` directory or install the package.
    sys.exit(main())
