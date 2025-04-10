import sys
import json
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, IntPrompt
from rich.panel import Panel
from rich import box

from lmstudio_model_discovery import discover_lmstudio_models, benchmark_lmstudio_models
from lmstudio_modelstate import update_modelstate_json
from lmstudio_roomodes import update_roomodes

console = Console()

def display_menu():
    console.print(Panel.fit(
        "[bold cyan]LM Studio Project Manager[/bold cyan]\n"
        "[green]1.[/green] Discover & Benchmark Models\n"
        "[green]2.[/green] Manual Save Model State (Optional)\n"
        "[green]3.[/green] Update Roomodes\n"
        "[green]4.[/green] Run All Steps\n"
        "[green]5.[/green] Exit",
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

def main():
    models = []
    benchmark_results = []
    
    # Try to load previous state at startup
    try:
        with open(".modelstate.json", "r", encoding="utf-8") as f:
            state_data = json.load(f)
            
        if isinstance(state_data, dict):
            if "models" in state_data:
                # Format: {"models": [...]}
                models = state_data["models"]
                benchmark_results = models  # Assuming model data contains benchmark results
                console.print(f"[green]Loaded {len(models)} models from previous session[/green]")
            else:
                # Format: {model_id: model_data, ...}
                models_list = list(state_data.values())
                models = models_list
                benchmark_results = models_list
                console.print(f"[green]Loaded {len(models)} models from previous session[/green]")
    except (FileNotFoundError, json.JSONDecodeError):
        console.print("[yellow]No previous session data found[/yellow]")

    while True:
        display_menu()
        choice = Prompt.ask("[bold yellow]Select an option[/bold yellow]", choices=["1", "2", "3", "4", "5"])

        if choice == "1":
            console.print("[bold cyan]Discovering models...[/bold cyan]")
            try:
                models = discover_lmstudio_models()
                pretty_print_models(models)
                # Save discovered models immediately
                save_modelstate(models, "Discovered models saved to .modelstate.json")
                # Let user select models for benchmarking
                models = select_models(models)
                console.print("[bold cyan]Benchmarking selected models...[/bold cyan]")
                benchmark_results = benchmark_lmstudio_models(models)
                pretty_print_benchmarks(benchmark_results)
                # Results already saved by the benchmark function after each model
                console.print("[green]Benchmark results saved to .modelstate.json[/green]")
            except Exception as e:
                console.print(f"[red]Error during discovery and benchmarking:[/red] {e}")

        elif choice == "2":
            if not benchmark_results:
                console.print("[yellow]No benchmark results available. Running manual save will create an empty state file.[/yellow]")
                if Prompt.ask("Continue anyway?", choices=["y", "n"], default="n") == "n":
                    continue
            console.print("[bold cyan]Manually saving current model state...[/bold cyan]")
            save_modelstate(benchmark_results, "Model state manually saved to .modelstate.json")
            console.print("[green]Note: This is optional as state is automatically saved during benchmarking.[/green]")

        elif choice == "3":
            console.print("[bold cyan]Updating .roomodes...[/bold cyan]")
            try:
                update_roomodes()
                console.print("[green].roomodes updated successfully[/green]")
            except Exception as e:
                console.print(f"[red]Error updating .roomodes:[/red] {e}")

        elif choice == "4":
            console.print("[bold cyan]Running full pipeline...[/bold cyan]")
            try:
                # Discover and save
                console.print("[bold cyan]Step 1/3: Discovering models...[/bold cyan]")
                models = discover_lmstudio_models()
                pretty_print_models(models)
                save_modelstate(models, "Discovered models saved to .modelstate.json")
                
                # Select models
                models = select_models(models)
                
                # Benchmark
                console.print("[bold cyan]Step 2/3: Benchmarking selected models...[/bold cyan]")
                benchmark_results = benchmark_lmstudio_models(models)
                pretty_print_benchmarks(benchmark_results)
                # Results already saved by benchmark function
                
                # Update roomodes
                console.print("[bold cyan]Step 3/3: Updating RooCode modes...[/bold cyan]")
                update_roomodes()
                console.print("[green]Full pipeline completed successfully![/green]")
            except Exception as e:
                console.print(f"[red]Error running full pipeline:[/red] {e}")

        elif choice == "5":
            console.print("[bold magenta]Goodbye![/bold magenta]")
            sys.exit(0)

if __name__ == "__main__":
    main()