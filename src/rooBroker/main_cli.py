"""
Command-line interface entry point for rooBroker.
"""

import argparse
import sys
from typing import List, NoReturn, Optional, cast, Dict, Any

from rooBroker.core import run_standard_benchmarks
from rooBroker.core.discovery import discover_models_with_status
from rooBroker.core.state import load_models_as_list, save_model_state
from rooBroker.interfaces.lmstudio.client import LMStudioClient
from rooBroker.interfaces.ollama.client import OllamaClient
from rooBroker.ui.common_formatters import pretty_print_benchmarks, pretty_print_models
from rooBroker.interfaces.base import ModelProviderClient
from rooBroker.roo_types.discovery import DiscoveredModel
from rooBroker.core.mode_management import update_room_modes


def handle_discover(args: argparse.Namespace) -> None:
    print("Discovering models...")
    try:
        models, status = discover_models_with_status()

        if models:
            # Convert DiscoveredModel objects to dictionaries
            # model_dicts = [model.__dict__ for model in models]
            pretty_print_models(models)
            print(f"Successfully discovered {len(models)} models.")
        else:
            print("No models discovered.")

        for provider, info in status["providers"].items():
            if info["status"] is True:
                print(
                    f"{provider} Status: OK (Found {info.get('model_count', 0)} models)"
                )
            else:
                print(
                    f"{provider} Status: FAILED - Error: {info.get('error', 'Unknown error')}"
                )

    except Exception as e:
        print(f"An error occurred during model discovery: {e}")


def handle_benchmark(args: argparse.Namespace) -> None:
    try:
        # Initialize models_to_benchmark
        models_to_benchmark: List[DiscoveredModel] = []

        # Determine Models
        if args.load_state:
            print("Loading models from state...")
            loaded_models: List[Dict[str, Any]] = load_models_as_list()

            if not loaded_models:
                print("Error: No models found in state file.")
                return

            # Transform Loaded Data
            temporary_list = []
            for loaded_model in loaded_models:
                model_data = {}
                id = loaded_model.get("model_id") or loaded_model.get("id")
                if id is None:
                    continue
                model_data["id"] = id

                # Extract additional keys if they exist
                for key in ["name", "family", "context_window", "version", "created"]:
                    model_data[key] = loaded_model.get(key) or loaded_model.get("context_length") if key == "context_window" else None

                temporary_list.append(model_data)

            models_to_benchmark = temporary_list

        else:
            print("Discovering models for benchmarking...")
            discovered_models_list, _ = discover_models_with_status()
            if not discovered_models_list:
                print("Error: Failed to discover any models.")
                return

            models_to_benchmark = discovered_models_list

        # Filter Models by Provider
        if args.provider:
            if args.provider == "lmstudio":
                models_to_benchmark = [
                    model for model in models_to_benchmark
                    if model.get("family") or not model.get("name") or model.get("name") == model.get("id")
                ]
                print(f"Filtered for LM Studio: {len(models_to_benchmark)} models remain.")

            elif args.provider == "ollama":
                models_to_benchmark = [
                    model for model in models_to_benchmark
                    if model.get("name") and not model.get("family")
                ]
                print(f"Filtered for Ollama: {len(models_to_benchmark)} models remain.")

            if not models_to_benchmark:
                print("Error: No models matching the specified provider were found/loaded.")
                return

        # Filter Models (Optional)
        if args.model_id:
            models_to_benchmark = [
                model for model in models_to_benchmark if model.get("id") in args.model_id
            ]
            if not models_to_benchmark:
                print("Error: Specified model IDs not found.")
                return

        # Check if Models Exist
        if not models_to_benchmark:
            print("Error: No models selected for benchmarking.")
            return

        # Instantiate Client
        client: Optional[ModelProviderClient] = None
        if args.provider == "lmstudio":
            client = LMStudioClient()
        elif args.provider == "ollama":
            client = OllamaClient()
        else:
            print("Error: --provider ('lmstudio' or 'ollama') is required for benchmarking.")
            return

        # Run Benchmarks
        print("Starting benchmarks...")
        kwargs = {}
        if args.samples is not None:
            kwargs["num_samples"] = args.samples

        benchmark_results = run_standard_benchmarks(
            client=client, models_to_benchmark=models_to_benchmark, verbose=args.verbose, **kwargs
        )

        # Display Results
        if benchmark_results:
            pretty_print_benchmarks(benchmark_results)
        else:
            print("Benchmarking completed, but no results were generated.")

        print("Benchmarking process finished.")

    except Exception as e:
        print(f"An error occurred during benchmarking: {e}")


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

    if hasattr(args, "func"):
        args.func(args)
        return 0
    else:
        parser.print_help()
        return 1


def main() -> NoReturn:
    """
    Main entry point for CLI mode.

    Returns:
        NoReturn: The function exits the program with an appropriate status code.
    """
    # TODO: Implement CLI logic here
    return exit(0)  # Temporary return until CLI implementation


if __name__ == "__main__":
    sys.exit(cli_main())
