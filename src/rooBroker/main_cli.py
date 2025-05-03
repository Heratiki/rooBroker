"""
Command-line interface entry point for rooBroker.
"""

import argparse
import sys
from typing import List, NoReturn, Optional, cast, Dict, Any
from pathlib import Path
from rich.progress import Progress, TextColumn, BarColumn, MofNCompleteColumn, TimeRemainingColumn
from rich.console import Console  # Import Console

from rooBroker.core.benchmarking import load_benchmarks_from_directory
from rooBroker.core.discovery import discover_models_with_status
from rooBroker.core.state import load_models_as_list, save_model_state
from rooBroker.interfaces.lmstudio.client import LMStudioClient
from rooBroker.interfaces.ollama.client import OllamaClient
from rooBroker.ui.common_formatters import pretty_print_benchmarks, pretty_print_models
from rooBroker.interfaces.base import ModelProviderClient
from rooBroker.roo_types.discovery import DiscoveredModel
from rooBroker.core.mode_management import update_room_modes
from rooBroker.core.log_config import logger
from rooBroker.actions import action_discover_models, action_run_benchmarks  # Import the new action function

# Instantiate Console
console = Console()


def handle_discover(args: argparse.Namespace) -> None:
    logger.info("Discovering models...")
    try:
        # Use the new action function to discover models
        models, status = action_discover_models()

        # Log the discovery status
        logger.info(status.get("message", ""))

        if models:
            # Convert DiscoveredModel objects to dictionaries
            # model_dicts = [model.__dict__ for model in models]
            pretty_print_models(models)
            logger.info(f"Successfully discovered {len(models)} models.")
        else:
            logger.warning("No models discovered.")

        for provider, info in status["providers"].items():
            if info["status"] is True:
                logger.info(f"{provider} Status: OK (Found {info.get('count', 0)} models)")
            else:
                logger.error(f"{provider} Status: FAILED - Error: {info.get('error', 'Unknown error')}")

    except Exception as e:
        logger.exception(f"An error occurred during model discovery: {e}")


def handle_benchmark(args: argparse.Namespace) -> None:
    """Handle the benchmark command."""
    try:
        # Determine model source
        if args.model_id:
            model_source = "manual"
        elif args.load_state:
            model_source = "state"
        else:
            model_source = "state"  # Default to state if neither is specified

        # Set model IDs if manual source
        model_ids = args.model_id if model_source == "manual" else []

        # Create benchmark filters
        benchmark_filters = {
            "tags": args.tags,
            "difficulty": args.difficulty,
            "type": args.type,
            "task_ids": args.task_ids,
        }

        # Set provider preference
        provider_preference = args.provider

        # Create run options
        run_options = {
            "samples": args.samples,
            "verbose": args.verbose,
        }

        # Set benchmark directory
        benchmark_dir = args.benchmark_dir

        # Call action_run_benchmarks
        benchmark_results = action_run_benchmarks(
            model_source=model_source,
            model_ids=model_ids,
            discovered_models_list=[],  # Not applicable in CLI context
            benchmark_filters=benchmark_filters,
            provider_preference=provider_preference,
            run_options=run_options,
            benchmark_dir=benchmark_dir,
            state_file=".modelstate.json",
        )

        # Process and print benchmark results
        if not benchmark_results:
            print("No benchmark results were produced.")
            return

        # Calculate averages and print results
        pretty_print_benchmarks(benchmark_results)
        print("Benchmarking process finished.")

    except Exception as e:
        logger.exception(f"An error occurred during benchmarking: {e}")


def handle_save_state(args: argparse.Namespace) -> None:
    try:
        input_file_path = ".modelstate.json"
        output_file_path = args.output_file

        print(f"Loading model state from {input_file_path}...")
        loaded_data: List[Dict[str, Any]] = load_models_as_list(file_path=input_file_path)

        if not loaded_data:
            print(f"Warning: No data found in {input_file_path}. Nothing to save.")
            return

        print(f"Saving model state to {output_file_path}...")
        save_model_state(data=loaded_data, file_path=output_file_path)

    except Exception as e:
        print(f"An error occurred while saving state: {e}")


def handle_update_modes(args: argparse.Namespace) -> None:
    try:
        print("Updating room modes...")

        modelstate_path = args.modelstate_file
        roomodes_path = args.roomodes_file
        settings_path = args.settings_file

        success = update_room_modes(
            modelstate_path=modelstate_path,
            roomodes_path=roomodes_path,
            settings_path=settings_path
        )

        if success:
            print("Mode update process completed successfully.")
        else:
            print("Mode update process finished with errors.")

    except FileNotFoundError as e:
        print(f"File not found: {e}")
    except Exception as e:
        print(f"An error occurred while updating modes: {e}")


def cli_main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="rooBroker: Manage and benchmark local LLMs."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Discover subparser
    discover_parser = subparsers.add_parser(
        "discover", help="Discover available models from providers."
    )
    discover_parser.set_defaults(func=handle_discover)

    # Benchmark subparser
    benchmark_parser = subparsers.add_parser(
        "benchmark", help="Run benchmarks on discovered models."
    )
    benchmark_parser.add_argument(
        "--model-id",
        nargs="+",
        help="Specify one or more model IDs to benchmark (default: all found/loaded).",
    )
    benchmark_parser.add_argument(
        "--load-state",
        action="store_true",
        help="Load models to benchmark from .modelstate.json instead of discovering.",
    )
    benchmark_parser.add_argument(
        "--provider",
        type=str,
        help="Specify the provider client to use for benchmarking (required if not loading state).",
    )
    benchmark_parser.add_argument(
        "--samples",
        type=int,
        help="Number of samples per benchmark task (default defined in core).",
    )
    benchmark_parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output during benchmarking to see individual task details and responses."
    )
    benchmark_parser.add_argument(
        "--benchmark-dir",
        type=str,
        default="benchmarks",
        help="Directory to load benchmarks from (default: 'benchmarks')."
    )
    benchmark_parser.add_argument(
        "--task-ids",
        nargs="+",
        help="Filter benchmarks by task IDs."
    )
    benchmark_parser.add_argument(
        "--tags",
        nargs="+",
        help="Filter benchmarks by tags."
    )
    benchmark_parser.add_argument(
        "--difficulty",
        type=str,
        help="Filter benchmarks by difficulty level."
    )
    benchmark_parser.add_argument(
        "--type",
        type=str,
        help="Filter benchmarks by type."
    )
    benchmark_parser.set_defaults(func=handle_benchmark)

    # Save-state subparser
    parser_save_state = subparsers.add_parser(
        'save-state',
        help='Load and save the model state file (.modelstate.json).'
    )
    parser_save_state.add_argument(
        '-o', '--output-file',
        type=str,
        default='.modelstate.json',
        help='Path to save the model state JSON file (default: .modelstate.json)'
    )
    parser_save_state.set_defaults(func=handle_save_state)

    # Update-modes subparser
    parser_update_modes = subparsers.add_parser(
        'update-modes',
        help='Update .roomodes file based on .modelstate.json.'
    )
    parser_update_modes.add_argument(
        '--modelstate-file',
        type=str,
        default='.modelstate.json',
        help='Path to the input model state JSON file (default: .modelstate.json)'
    )
    parser_update_modes.add_argument(
        '--roomodes-file',
        type=str,
        default='.roomodes',
        help='Path to the output .roomodes file (default: .roomodes)'
    )
    parser_update_modes.add_argument(
        '--settings-file',
        type=str,
        default='roo-code-settings.json',
        help='Path to the roo-code-settings.json file to update (default: roo-code-settings.json)'
    )
    parser_update_modes.set_defaults(func=handle_update_modes)

    args = parser.parse_args(argv)

    try:
        if hasattr(args, "func"):
            args.func(args) # Execute the command function
            return 0
        else:
            # Handle cases where no command was provided or func is not set
            parser.print_help()
            return 1 # Return an error code if no command was run
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        return 1 # Return specific code for interruption
    except Exception as e:
        # Log the exception for debugging purposes
        logger.exception(f"An unexpected error occurred: {e}")
        # Print a user-friendly error message
        console.print(f"[red]Error: {str(e)}[/red]")
        return 1 # Return a general error code


if __name__ == "__main__":
    sys.exit(cli_main()) # Call cli_main directly
