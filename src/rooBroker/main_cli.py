"""CLI entry point for rooBroker.

This module provides the command-line interface for rooBroker, allowing users
to discover models, run benchmarks, update room modes, and run the proxy server
directly from the command line.
"""

import sys
import argparse
from rich.console import Console

from rooBroker.core.discovery import discover_all_models
from rooBroker.core.benchmarking import run_standard_benchmarks
from rooBroker.core.big_bench import run_bigbench_benchmarks
from rooBroker.core.mode_management import update_room_modes
from rooBroker.core.proxy import run_proxy_server, ProxyConfig
from rooBroker.interfaces.lmstudio.client import LMStudioClient
from rooBroker.ui.common_formatters import pretty_print_models, pretty_print_benchmarks


def main():
    """Main CLI entry point for rooBroker."""
    console = Console()
    
    parser = argparse.ArgumentParser(description="rooBroker - LLM Benchmarking and Management Tool")
    
    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Discover command
    _discover_parser = subparsers.add_parser('discover', help='Discover available LLM models')
      # Benchmark command
    benchmark_parser = subparsers.add_parser('benchmark', help='Benchmark LLM models')
    benchmark_parser.add_argument('--models', type=str, default='all', 
                                 help='Comma-separated list of model IDs to benchmark, or "all"')
    benchmark_parser.add_argument('--bigbench', action='store_true',
                                 help='Run BIG-BENCH-HARD benchmarks after standard ones')

    # Update roomodes command
    _update_parser = subparsers.add_parser('update', help='Update .roomodes file with model benchmarks')
    
    # Context proxy command
    proxy_parser = subparsers.add_parser('proxy', help='Run a context-optimizing proxy server')
    proxy_parser.add_argument('--port', type=int, default=1235, 
                             help='Port to run the proxy on (default: 1235)')
    
    # Parse arguments
    args = parser.parse_args()
    
    # If no command specified, show help and exit
    if len(sys.argv) == 1:
        parser.print_help()
        return 0
    
    # Execute the requested command
    if args.command == 'discover':
        try:
            console.print("[cyan]Discovering models...[/cyan]")
            models = discover_all_models()
            console.print(f"[green]Found {len(models)} models![/green]")
            pretty_print_models(models)
        except Exception as e:
            console.print(f"[red]Error discovering models: {e}[/red]")
            return 1
            
    elif args.command == 'benchmark':
        try:
            console.print("[cyan]Discovering models...[/cyan]")
            all_models = discover_all_models()
            console.print(f"[green]Found {len(all_models)} models![/green]")
            
            if args.models.lower() == 'all':
                models_to_benchmark = all_models
            else:
                selected_ids = {s.strip() for s in args.models.split(',')}
                models_to_benchmark = [m for m in all_models if m.get("id") in selected_ids]

            if not models_to_benchmark:
                 console.print("[yellow]No matching models found or selected for benchmarking.[/yellow]")
                 return 1            console.print(f"[cyan]Running standard benchmarks for {len(models_to_benchmark)} models...[/cyan]")
            # Initialize the LMStudio client and run standard benchmarks
            lm_client = LMStudioClient()
            results = run_standard_benchmarks(lm_client, models_to_benchmark, console=console)
            console.print("[green]Standard benchmarking complete.[/green]")

            # Run Big Bench Hard if requested via flag
            if args.bigbench:
                console.print("[cyan]Running BIG-BENCH-HARD benchmarks...[/cyan]")
                results = run_bigbench_benchmarks(lm_client, models_to_benchmark, results, console=console)
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
            console.print("[cyan]Updating .roomodes file...[/cyan]")
            success = update_room_modes(console=console)
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
            port = args.port
            console.print(f"[green]Starting context optimization proxy on port {port}...[/green]")
            console.print(f"[cyan]Point your application to http://localhost:{port}[/cyan]")
            console.print("[yellow]Press Ctrl+C to stop the proxy.[/yellow]")
            
            config = ProxyConfig(
                port=port,
                target_url="http://localhost:1234",
                verbose=True
            )
            
            run_proxy_server(config)
        except KeyboardInterrupt:
            console.print("\n[yellow]Proxy server stopped by user.[/yellow]")
        except Exception as e:
            console.print(f"[red]Error running proxy server: {e}[/red]")
            return 1

    return 0


if __name__ == "__main__":
    # When running main_cli.py directly, the src directory needs to be in PYTHONPATH
    # For direct execution `python src/rooBroker/main_cli.py`, Python might not find the modules.
    # A common workaround for direct script execution is to adjust sys.path,
    # but the best practice is to run it as a module: `python -m rooBroker.main_cli` 
    # from the `src` directory or install the package.
    sys.exit(main())
