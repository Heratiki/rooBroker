from typing import Any, Dict, List
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, IntPrompt
from rich.panel import Panel
from rich import box
from rooBroker.lmstudio import context_proxy
from rooBroker.ui.common_formatters import pretty_print_models

console = Console()


def display_menu():
    console.print(
        Panel.fit(
            "[bold cyan]LM Studio Project Manager[/bold cyan]\n"
            "[green]1.[/green] Discover & Benchmark Models\n"
            "[green]2.[/green] Manual Save Model State (Optional)\n"
            "[green]3.[/green] Update Roomodes\n"
            "[green]4.[/green] Run Context Optimization Proxy\n"
            "[green]5.[/green] Run All Steps\n"
            "[green]6.[/green] Exit",
            title="Main Menu",
            border_style="bright_blue",
        )
    )


def select_models(models: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Helper function to let user select which models to benchmark"""
    console.print(
        "[bold cyan]Select models to benchmark (comma-separated IDs or 'all'):[/bold cyan]"
    )
    ids = [str(m.get("id")) for m in models]
    console.print(f"Available model IDs: {', '.join(ids)}")
    selection = Prompt.ask("Enter IDs", default="all")
    if selection.strip().lower() == "all":
        return models
    selected_ids = [s.strip() for s in selection.split(",")]
    selected_models = [m for m in models if str(m.get("id")) in selected_ids]
    console.print(
        f"[green]Selected {len(selected_models)} models for benchmarking.[/green]"
    )
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
            str(m.get("context_window", "")),
        )

    console.print(table)

    # Prompt for selection
    console.print("[bold cyan]Select models to benchmark:[/bold cyan]")
    console.print(
        "Enter model numbers (comma-separated), 'all' for all models, or '0' to cancel"
    )
    selection = Prompt.ask("Your selection", default="all")

    # Process selection
    if selection.strip().lower() == "all":
        console.print(
            f"[green]Selected all {len(models)} models for benchmarking.[/green]"
        )
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
        selected_models = [models[idx - 1] for idx in valid_indices]

        # Show selection summary
        selected_ids = [m.get("id", "") for m in selected_models]
        console.print(
            f"[green]Selected {len(selected_models)} models: {', '.join(selected_ids)}[/green]"
        )
        return selected_models

    except ValueError:
        console.print(
            "[yellow]Invalid input. Please use numbers separated by commas.[/yellow]"
        )
        return []


def run_proxy_with_ui():
    """Run the context optimization proxy with rich UI feedback"""
    try:
        # Allow user to customize port
        port = IntPrompt.ask("Enter port for the proxy server", default=1235)

        # Corrected Panel content with single backslashes for newlines
        console.print(
            Panel.fit(
                "[bold]The proxy will now start running.[/bold]\n\n"
                f"Point Roo Code to use [cyan]http://localhost:{port}[/cyan] instead of http://localhost:1234\n\n"
                "Press Ctrl+C to stop the proxy and return to the menu.",
                title="Context Optimization Proxy",
                border_style="green",
            )
        )

        # Set the proxy port using the imported module
        context_proxy.PROXY_PORT = port

        # Start the proxy server
        run_proxy_server()
    except KeyboardInterrupt:
        console.print("[yellow]Proxy server stopped by user.[/yellow]")
    except Exception as e:
        console.print(f"[red]Error running proxy server: {e}[/red]")
