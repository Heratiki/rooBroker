import sys, json, argparse
import os  # required for inserting src folder into path

# Allow direct script execution by adding src folder to sys.path
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from typing import Any, Dict, List, Optional
from rich.console import Console
from rich.prompt import IntPrompt
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn, TimeRemainingColumn

# Corrected relative imports
from rooBroker.core.discovery import discover_all_models
from rooBroker.core.benchmarking import run_standard_benchmarks
from rooBroker.interfaces.lmstudio.client import LMStudioClient
from rooBroker.roo_types.discovery import DiscoveredModel
from rooBroker.roomodes.update import update_roomodes
from rooBroker.lmstudio.context_proxy import run_proxy_server
# from rooBroker.lmstudio.deepeval import benchmark_with_bigbench  # Removed due to deepeval changes removing BIG-BENCH-HARD
from rooBroker.ui.common_formatters import pretty_print_models, pretty_print_benchmarks
from rooBroker.ui.interactive_utils import display_menu, select_models, select_models_by_number, run_proxy_with_ui

console = Console()

def save_modelstate(data: List[Dict[str, Any]], message: str = "Model state saved") -> None:
    """Helper function to save model state with consistent formatting"""
    try:
        # Convert list of models to a dictionary keyed by model_id for consistency
        # with lmstudio_modelstate.py's format
        data_dict = {}
        for model in data:
            model_id = model.get("model_id", model.get("id"))
            if model_id:
                data_dict[model_id] = model
        
        with open(".modelstate.json", "w", encoding="utf-8") as f:
            json.dump(data_dict, f, indent=2, ensure_ascii=False)
        console.print(f"[green]{message}[/green]")
    except Exception as e:
        console.print(f"[red]Error saving model state: {e}[/red]")


def run_and_merge_bigbench(
    models_to_benchmark: List[Dict[str, Any]],
    existing_results: List[Dict[str, Any]],
    console: Optional[Console] = None
) -> List[Dict[str, Any]]:
    """Runs BIG-BENCH-HARD and merges results into the existing list."""
    if not console:
        console = Console() # Ensure console is available

    console.print("\n[bold cyan]Starting BIG-BENCH-HARD benchmarks[/bold cyan]")
    console.print("[yellow]Note: These benchmarks test complex reasoning tasks and may take longer to complete.[/yellow]")

    # Create a map of existing results for easy lookup and update
    results_map = {r.get("model_id"): r for r in existing_results}
    
    # Setup main progress tracker for all models
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console
    ) as progress:
        overall_task = progress.add_task(
            f"[cyan]Running BIG-BENCH-HARD for {len(models_to_benchmark)} models...", 
            total=len(models_to_benchmark)
        )
        
        # Process each model
        for model_index, model in enumerate(models_to_benchmark):
            model_id = model.get("id")
            if not model_id:
                console.print("[yellow]Skipping model with no ID for BIG-BENCH-HARD.[/yellow]")
                progress.update(overall_task, advance=1)
                continue

            # Update progress description to show current model
            progress.update(
                overall_task, 
                description=f"[cyan]BIG-BENCH-HARD [{model_index+1}/{len(models_to_benchmark)}]: {model_id}"
            )
            
            try:
                # Run the benchmark with the enhanced UI in lmstudio_deepeval.py
                console.print(f"\n[bold cyan]═════ BIG-BENCH-HARD: {model_id} ═════[/bold cyan]")
                # Use a separate Console instance for BIG-BENCH-HARD to avoid nested live display issues
                bb_result_data = benchmark_with_bigbench(
                    model,
                    api_endpoint="http://localhost:1234/v1/chat/completions",
                    console=Console()
                )

                # Handle results
                if model_id in results_map:
                    if bb_result_data:
                        # bb_result_data contains 'bigbench_scores', 'predictions', 'raw_results'
                        results_map[model_id].update(bb_result_data)
                        console.print(f"[green]✓ Results merged successfully for {model_id}[/green]")
                    else:
                        console.print(f"[yellow]⚠ No valid results returned for {model_id}[/yellow]")
                        results_map[model_id]["bigbench_status"] = "No results returned"
                else:
                    console.print(f"[yellow]⚠ No standard benchmark result found to merge BBH results into.[/yellow]")
            except Exception as e:
                console.print(f"[bold red]✗ Error running BIG-BENCH-HARD for {model_id}: {e}[/bold red]")
                if model_id in results_map:
                    results_map[model_id]["bigbench_error"] = str(e)
            
            # Update overall progress
            progress.update(overall_task, advance=1)
    
    # Final summary
    bb_models_count = len([r for r in existing_results if "bigbench_scores" in r])
    if bb_models_count > 0:
        console.print(f"\n[bold green]✓ BIG-BENCH-HARD completed for {bb_models_count} of {len(models_to_benchmark)} models[/bold green]")
    else:
        console.print("\n[yellow]⚠ No models completed BIG-BENCH-HARD successfully[/yellow]")

    # The existing_results list has been modified in-place through the map
    return existing_results


def main_menu():
    """Show the main menu and handle user input"""
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
                    continue # Go back to menu

                console.print("[cyan]Running standard benchmarks for selected models...[/cyan]")
                # Initialize the LMStudio client and run standard benchmarks
                lm_client = LMStudioClient()
                results = run_standard_benchmarks(lm_client, selected_models)
                console.print("[green]Standard benchmarking complete![/green]")
                pretty_print_benchmarks(results) # Show standard results

                # Now, ask about Big Bench Hard
                if Prompt.ask("\nRun additional BIG-BENCH-HARD benchmarks (can be slow)?", choices=["y", "n"], default="n") == "y":
                    # Run BBH and merge results into the existing 'results' list
                    results = run_and_merge_bigbench(selected_models, results)
                    console.print("[green]BIG-BENCH-HARD benchmarking complete![/green]")
                    pretty_print_benchmarks(results) # Show potentially updated results
                else:
                     console.print("[cyan]Skipping BIG-BENCH-HARD benchmarks.[/cyan]")
            except Exception as e:
                console.print(f"[red]Error discovering/benchmarking models: {e}[/red]")
        
        elif choice == 2:  # Manual Save
            try:
                console.print("[cyan]Discovering models for state saving...[/cyan]")
                models = discover_all_models()
                save_modelstate(models, "Model state manually saved")
            except Exception as e:
                console.print(f"[red]Error saving model state: {e}[/red]")
        
        elif choice == 3:  # Update Roomodes
            try:
                console.print("[cyan]Updating .roomodes file...[/cyan]")
                success = update_roomodes()
                if success:
                    console.print("[green]Successfully updated .roomodes file![/green]")
                else:
                    console.print("[yellow]No changes made to .roomodes file.[/yellow]")
            except Exception as e:
                console.print(f"[red]Error updating .roomodes: {e}[/red]")
        
        elif choice == 4:  # Run Context Optimization Proxy
            run_proxy_with_ui()
        
        elif choice == 5:  # Run All Steps
            try:
                # Step 1: Discover and benchmark
                console.print("[cyan]Step 1: Discovering models...[/cyan]")
                models = discover_all_models()
                console.print(f"[green]Found {len(models)} models![/green]")
                pretty_print_models(models)
                
                console.print("[cyan]Benchmarking all models (standard)...[/cyan]")
                # Initialize the LMStudio client and run standard benchmarks
                lm_client = LMStudioClient()
                results = run_standard_benchmarks(lm_client, models)
                console.print("[green]Standard benchmarking complete![/green]")
                pretty_print_benchmarks(results)
                # BBH is not run automatically in this mode
                
                # Step 2: Update roomodes
                console.print("[cyan]Step 2: Updating .roomodes file...[/cyan]")
                success = update_roomodes()
                if success:
                    console.print("[green]Successfully updated .roomodes file![/green]")
                else:
                    console.print("[yellow]No changes made to .roomodes file.[/yellow]")
                
                console.print(Panel.fit(
                    "[bold green]All steps completed successfully![/bold green]\\n\\n"
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
    """Main function that handles both CLI and interactive modes"""
    parser = argparse.ArgumentParser(description="LM Studio Project Manager")
    
    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Discover command
    _discover_parser = subparsers.add_parser('discover', help='Discover available LM Studio models')
    
    # Benchmark command
    benchmark_parser = subparsers.add_parser('benchmark', help='Benchmark LM Studio models')
    benchmark_parser.add_argument('--bigbench', action='store_true', help='Run BIG-BENCH-HARD benchmarks after standard ones')
    benchmark_parser.add_argument('--models', type=str, default='all', help='Comma-separated list of model IDs to benchmark, or "all"')

    # Update roomodes command
    _update_parser = subparsers.add_parser('update', help='Update .roomodes file with model benchmarks')
    
    # Context proxy command
    proxy_parser = subparsers.add_parser('proxy', help='Run a context-optimizing proxy for LM Studio')
    proxy_parser.add_argument('--port', type=int, default=1235, help='Port to run the proxy on (default: 1235)')
    
    # Parse arguments
    args = parser.parse_args()
    
    # If no command is specified, run the interactive menu
    if len(sys.argv) == 1:
        return main_menu()
    
    # Otherwise, run the specified command
    if args.command == 'discover':
        try:
            models = discover_all_models()
            pretty_print_models(models)
        except Exception as e:
            console.print(f"[red]Error discovering models: {e}[/red]")
            return 1
            
    elif args.command == 'benchmark':
        try:
            all_models = discover_all_models()
            if args.models.lower() == 'all':
                models_to_benchmark = all_models
            else:
                selected_ids = {s.strip() for s in args.models.split(',')}
                models_to_benchmark = [m for m in all_models if m.get("id") in selected_ids]

            if not models_to_benchmark:
                 console.print("[yellow]No matching models found or selected for benchmarking.[/yellow]")
                 return 1

            console.print(f"Running standard benchmarks for {len(models_to_benchmark)} models...")
            # Initialize the LMStudio client and run standard benchmarks
            lm_client = LMStudioClient()
            results = run_standard_benchmarks(lm_client, models_to_benchmark)
            console.print("[green]Standard benchmarking complete.[/green]")

            # Run Big Bench Hard if requested via flag
            if args.bigbench:
                results = run_and_merge_bigbench(models_to_benchmark, results, console=console)
                console.print("[green]BIG-BENCH-HARD benchmarking complete.[/green]")
            else:
                console.print("[cyan]Skipping BIG-BENCH-HARD benchmarks (use --bigbench flag to enable).[/cyan]")

            # Print final results (standard or merged)
            pretty_print_benchmarks(results)
        except Exception as e:
            console.print(f"[red]Error benchmarking models: {e}[/red]")
            return 1
            
    elif args.command == 'update':
        try:
            success = update_roomodes()
            if success:
                console.print("[green]Successfully updated .roomodes file![/green]")
            else:
                console.print("[yellow]No changes made to .roomodes file.[/yellow]")
                return 1
        except Exception as e:
            console.print(f"[red]Error updating .roomodes: {e}[/red]")
            return 1
            
    elif args.command == 'proxy':
        try:
            # Set the proxy port if specified
            if hasattr(args, 'port'):
                # Use the already imported module
                context_proxy.PROXY_PORT = args.port

            console.print("[green]Starting LM Studio context optimization proxy...[/green]")
            run_proxy_server()
        except Exception as e:
            console.print(f"[red]Error running proxy server: {e}[/red]")
            return 1

    return 0

if __name__ == "__main__":
    # When running main.py directly, the src directory needs to be in PYTHONPATH
    # This is often handled by IDEs or by installing the package (e.g., `pip install -e .`)
    # For direct execution `python src/rooBroker/main.py`, Python might not find the modules.
    # A common workaround for direct script execution is to adjust sys.path,
    # but the best practice is to run it as a module: `python -m rooBroker.main` from the `src` directory
    # or install the package.
    # For simplicity here, we'll assume it's run correctly or installed.
    sys.exit(main())