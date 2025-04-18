import sys
import json
import argparse
from typing import Any, Dict, List, Optional
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, IntPrompt
from rich.panel import Panel
from rich import box
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn, TimeRemainingColumn

# Corrected relative imports
from .lmstudio.model_discovery import discover_lmstudio_models, benchmark_lmstudio_models
from .roomodes.update import update_roomodes # Assuming update_roomodes is in update.py
from .lmstudio.context_proxy import run_proxy_server
from .lmstudio.deepeval import benchmark_with_bigbench
from .lmstudio import context_proxy # Import the module

console = Console()

def display_menu():
    console.print(Panel.fit(
        "[bold cyan]LM Studio Project Manager[/bold cyan]\n"
        "[green]1.[/green] Discover & Benchmark Models\n"
        "[green]2.[/green] Manual Save Model State (Optional)\n"
        "[green]3.[/green] Update Roomodes\n"
        "[green]4.[/green] Run Context Optimization Proxy\n"
        "[green]5.[/green] Run All Steps\n"
        "[green]6.[/green] Exit",
        title="Main Menu",
        border_style="bright_blue"
    ))

def pretty_print_models(models: List[Dict[str, Any]]) -> None:
    table = Table(title="Discovered Models", box=box.SIMPLE)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Family", style="magenta")
    table.add_column("Context Window", style="green")
    for m in models:
        table.add_row(
            str(m.get("id", "")),
            str(m.get("family", "")),
            str(m.get("context_window", ""))
        )
    console.print(table)

def pretty_print_benchmarks(results: List[Dict[str, Any]]) -> None:
    # Standard benchmarks table
    table = Table(title="Standard Benchmark Results", box=box.SIMPLE)
    table.add_column("Model ID", style="cyan", no_wrap=True)
    table.add_column("Simple", style="green")
    table.add_column("Moderate", style="yellow")
    table.add_column("Complex", style="red")
    table.add_column("Context", style="blue")
    table.add_column("Failures", style="magenta")
    
    for r in results:
        table.add_row(
            r.get("model_id", ""),
            f"{r.get('score_simple', 0):.2f}",
            f"{r.get('score_moderate', 0):.2f}",
            f"{r.get('score_complex', 0):.2f}",
            f"{r.get('score_context_window', 0):.2f}",
            str(r.get("failures", 0))
        )
    console.print(table)
    
    # BIG-BENCH-HARD table for models with those results
    bb_models = [r for r in results if "bigbench_scores" in r]
    if bb_models:
        # Prepare category buckets
        categories: Dict[str, List[float]] = {}
        bb_table = Table(title="BIG-BENCH-HARD Results", box=box.SIMPLE)
        bb_table.add_column("Model ID", style="cyan", no_wrap=True)
        bb_table.add_column("Overall", style="green")
        bb_table.add_column("Logical", style="yellow")
        bb_table.add_column("Algorithmic", style="red")
        bb_table.add_column("Abstract", style="blue")
        bb_table.add_column("Mathematics", style="magenta")
        bb_table.add_column("Code Gen", style="cyan")
        bb_table.add_column("Problem Solving", style="green")
        
        for r in bb_models:
            scores = r["bigbench_scores"]
            # group weighted scores by category
            for task in scores.get("tasks", []):
                cat = task.get("complexity_category", "other")
                categories.setdefault(cat, []).append(float(task.get("weighted_score", 0.0)))
            
            # Calculate category averages
            cat_avgs: Dict[str, float] = {
                cat: (sum(vals) / len(vals)) if vals else 0.0
                for cat, vals in categories.items()
            }
            
            bb_table.add_row(
                r.get("model_id", ""),
                f"{scores.get('overall', 0):.2f}",
                f"{cat_avgs.get('logical_reasoning', 0):.2f}",
                f"{cat_avgs.get('algorithmic_thinking', 0):.2f}",
                f"{cat_avgs.get('abstract_reasoning', 0):.2f}",
                f"{cat_avgs.get('mathematics', 0):.2f}",
                f"{cat_avgs.get('code_generation', 0):.2f}",
                f"{cat_avgs.get('problem_solving', 0):.2f}"
            )
        console.print(bb_table)
        
        # Add a weighted averages summary table
        summary_table = Table(title="Overall Performance Summary", box=box.SIMPLE)
        summary_table.add_column("Model ID", style="cyan", no_wrap=True)
        summary_table.add_column("Standard Avg", style="yellow")
        summary_table.add_column("BIG-BENCH Avg", style="green")
        summary_table.add_column("Overall (60/40)", style="red")
        
        for r in bb_models:
            standard_avg = (
                r.get('score_simple', 0.0) +
                r.get('score_moderate', 0.0) +
                r.get('score_complex', 0.0) +
                r.get('score_context_window', 0.0)
            ) / 4
            
            bb_score = r["bigbench_scores"].get('overall', 0.0)
            overall = standard_avg * 0.4 + bb_score * 0.6
            
            summary_table.add_row(
                r.get("model_id", ""),
                f"{standard_avg:.2f}",
                f"{bb_score:.2f}",
                f"{overall:.2f}"
            )
        console.print(summary_table)

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

def select_models(models: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Helper function to let user select which models to benchmark"""
    console.print("[bold cyan]Select models to benchmark (comma-separated IDs or 'all'):[/bold cyan]")
    ids = [str(m.get("id")) for m in models]
    console.print(f"Available model IDs: {', '.join(ids)}")
    selection = Prompt.ask("Enter IDs", default="all")
    if selection.strip().lower() == "all":
        return models
    selected_ids = [s.strip() for s in selection.split(",")]
    selected_models = [m for m in models if str(m.get("id")) in selected_ids]
    console.print(f"[green]Selected {len(selected_models)} models for benchmarking.[/green]")
    return selected_models

def select_models_by_number(models: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Helper function to let user select which models to benchmark by number in the list"""
    # Create a table with numbered models
    table = Table(title="Available Models", box=box.SIMPLE)
    table.add_column("#", style="yellow", no_wrap=True)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Family", style="magenta")
    table.add_column("Context Window", style="green")
    
    # Add rows with index numbers
    for i, m in enumerate(models, 1):
        table.add_row(
            str(i),
            str(m.get("id", "")),
            str(m.get("family", "")),
            str(m.get("context_window", ""))
        )
    
    console.print(table)
    
    # Prompt for selection
    console.print("[bold cyan]Select models to benchmark:[/bold cyan]")
    console.print("Enter model numbers (comma-separated), 'all' for all models, or '0' to cancel")
    selection = Prompt.ask("Your selection", default="all")
    
    # Process selection
    if selection.strip().lower() == "all":
        console.print(f"[green]Selected all {len(models)} models for benchmarking.[/green]")
        return models
    
    if selection.strip() == "0":
        console.print("[yellow]Benchmarking canceled.[/yellow]")
        return []
    
    try:
        # Parse comma-separated numbers
        selected_indices = [int(idx.strip()) for idx in selection.split(",")]
        
        # Check for valid indices
        valid_indices = [idx for idx in selected_indices if 1 <= idx <= len(models)]
        if not valid_indices:
            console.print("[yellow]No valid model numbers selected.[/yellow]")
            return []
        
        # Convert indices to actual models (adjusting for 1-based indexing)
        selected_models = [models[idx-1] for idx in valid_indices]
        
        # Show selection summary
        selected_ids = [m.get("id", "") for m in selected_models]
        console.print(f"[green]Selected {len(selected_models)} models: {', '.join(selected_ids)}[/green]")
        return selected_models
        
    except ValueError:
        console.print("[yellow]Invalid input. Please use numbers separated by commas.[/yellow]")
        return []

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
                bb_result_data = benchmark_with_bigbench(
                    model, 
                    api_endpoint="http://localhost:1234/v1/chat/completions", 
                    console=console
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

def run_proxy_with_ui():
    \"\"\"Run the context optimization proxy with rich UI feedback\"\"\"
    try:
        # Allow user to customize port
        port = IntPrompt.ask(
            "Enter port for the proxy server",
            default=1235
        )

        # Corrected Panel content with single backslashes for newlines
        console.print(Panel.fit(
            "[bold]The proxy will now start running.[/bold]\\n\\n"
            f"Point Roo Code to use [cyan]http://localhost:{port}[/cyan] instead of http://localhost:1234\\n\\n"
            "Press Ctrl+C to stop the proxy and return to the menu.",
            title="Context Optimization Proxy",
            border_style="green"
        ))

        # Set the proxy port using the imported module
        context_proxy.PROXY_PORT = port

        # Start the proxy server
        run_proxy_server()
    except KeyboardInterrupt:
        console.print("[yellow]Proxy server stopped by user.[/yellow]")
    except Exception as e:
        console.print(f"[red]Error running proxy server: {e}[/red]")

def main_menu():
    """Show the main menu and handle user input"""
    while True:
        display_menu()
        choice = IntPrompt.ask("Select an option", default=1)
        
        if choice == 1:  # Discover & Benchmark
            try:
                console.print("[cyan]Discovering models...[/cyan]")
                models = discover_lmstudio_models()
                console.print(f"[green]Found {len(models)} models![/green]")
                
                # Show models with numbers and allow direct selection
                selected_models = select_models_by_number(models)
                if not selected_models:
                    console.print("[yellow]No models selected for benchmarking.[/yellow]")
                    continue # Go back to menu

                console.print("[cyan]Running standard benchmarks for selected models...[/cyan]")
                # Run standard benchmarks first
                results = benchmark_lmstudio_models(selected_models)
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
                models = discover_lmstudio_models()
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
                models = discover_lmstudio_models()
                console.print(f"[green]Found {len(models)} models![/green]")
                pretty_print_models(models)
                
                console.print("[cyan]Benchmarking all models (standard)...[/cyan]")
                # Run standard benchmarks only for "Run All Steps"
                results = benchmark_lmstudio_models(models)
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
            models = discover_lmstudio_models()
            pretty_print_models(models)
        except Exception as e:
            console.print(f"[red]Error discovering models: {e}[/red]")
            return 1
            
    elif args.command == 'benchmark':
        try:
            all_models = discover_lmstudio_models()
            if args.models.lower() == 'all':
                models_to_benchmark = all_models
            else:
                selected_ids = {s.strip() for s in args.models.split(',')}
                models_to_benchmark = [m for m in all_models if m.get("id") in selected_ids]

            if not models_to_benchmark:
                 console.print("[yellow]No matching models found or selected for benchmarking.[/yellow]")
                 return 1

            console.print(f"Running standard benchmarks for {len(models_to_benchmark)} models...")
            # Run standard benchmarks first
            results = benchmark_lmstudio_models(models_to_benchmark)
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