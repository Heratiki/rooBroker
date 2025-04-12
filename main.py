import sys
import json
import argparse
import os
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, IntPrompt
from rich.panel import Panel
from rich import box

from lmstudio_model_discovery import discover_lmstudio_models, benchmark_lmstudio_models
from lmstudio_modelstate import update_modelstate_json
from lmstudio_roomodes import update_roomodes
from lmstudio_context_proxy import run_proxy_server

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

def pretty_print_models(models):
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

def pretty_print_benchmarks(results):
    table = Table(title="Benchmark Results", box=box.SIMPLE)
    table.add_column("Model ID", style="cyan", no_wrap=True)
    table.add_column("Simple", style="green")
    table.add_column("Moderate", style="yellow")
    table.add_column("Complex", style="red")
    table.add_column("Failures", style="magenta")
    for r in results:
        table.add_row(
            r.get("model_id", ""),
            f"{r.get('score_simple', 0):.2f}",
            f"{r.get('score_moderate', 0):.2f}",
            f"{r.get('score_complex', 0):.2f}",
            str(r.get("failures", 0))
        )
    console.print(table)

def save_modelstate(data, message="Model state saved"):
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

def select_models(models):
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

def run_proxy_with_ui():
    """Run the context optimization proxy with rich UI feedback"""
    try:
        # Allow user to customize port
        port = IntPrompt.ask(
            "Enter port for the proxy server",
            default=1235
        )
        
        console.print(Panel.fit(
            "[bold]The proxy will now start running.[/bold]\n\n"
            f"Point Roo Code to use [cyan]http://localhost:{port}[/cyan] instead of http://localhost:1234\n\n"
            "Press Ctrl+C to stop the proxy and return to the menu.",
            title="Context Optimization Proxy",
            border_style="green"
        ))
        
        # Set the proxy port
        import lmstudio_context_proxy
        lmstudio_context_proxy.PROXY_PORT = port
        
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
                pretty_print_models(models)
                
                if Prompt.ask("Benchmark these models?", choices=["y", "n"], default="y") == "y":
                    selected_models = select_models(models)
                    console.print("[cyan]Benchmarking selected models...[/cyan]")
                    results = benchmark_lmstudio_models(selected_models)
                    console.print("[green]Benchmarking complete![/green]")
                    pretty_print_benchmarks(results)
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
                
                console.print("[cyan]Benchmarking models...[/cyan]")
                results = benchmark_lmstudio_models(models)
                console.print("[green]Benchmarking complete![/green]")
                pretty_print_benchmarks(results)
                
                # Step 2: Update roomodes
                console.print("[cyan]Step 2: Updating .roomodes file...[/cyan]")
                success = update_roomodes()
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
    """Main function that handles both CLI and interactive modes"""
    parser = argparse.ArgumentParser(description="LM Studio Project Manager")
    
    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Discover command
    discover_parser = subparsers.add_parser('discover', help='Discover available LM Studio models')
    
    # Benchmark command
    benchmark_parser = subparsers.add_parser('benchmark', help='Benchmark LM Studio models')
    
    # Update roomodes command
    update_parser = subparsers.add_parser('update', help='Update .roomodes file with model benchmarks')
    
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
            models = discover_lmstudio_models()
            console.print(f"Benchmarking {len(models)} models...")
            results = benchmark_lmstudio_models(models)
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
                import lmstudio_context_proxy
                lmstudio_context_proxy.PROXY_PORT = args.port
            
            console.print("[green]Starting LM Studio context optimization proxy...[/green]")
            run_proxy_server()
        except Exception as e:
            console.print(f"[red]Error running proxy server: {e}[/red]")
            return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())