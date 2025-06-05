import asyncio
from typing import List, Dict, Any, Sequence, Union, cast
from rich.console import Console
from rich.prompt import Prompt
from rooBroker.core.state import save_model_state, load_models_as_list
from rooBroker.core.mode_management import update_room_modes
from rooBroker.actions import action_discover_models, action_run_benchmarks
from rooBroker.ui.interactive_layout import InteractiveLayout, ModelInfo as UIModelInfo
from rooBroker.roo_types.discovery import DiscoveredModel, ModelInfo, OllamaModelInfo
from rooBroker.core.proxy import run_proxy_in_thread, DEFAULT_PROXY_PORT

proxy_server = None
proxy_stop_function = None

discovered_models: List[DiscoveredModel] = []  # Global state for discovered models


def _get_available_providers(
    models: Sequence[Union[DiscoveredModel, Dict[str, Any]]],
) -> List[str]:
    """Return unique providers based on model structure."""
    providers = set()
    for m in models:
        if m.get("family"):
            providers.add("lmstudio")
        elif m.get("name"):
            providers.add("ollama")
    return list(providers)


async def manual_save_state(
    layout: InteractiveLayout, benchmark_results: List[Dict[str, Any]]
):
    """Manually save the current model state."""
    layout.prompt.add_message("[yellow]Saving model state...[/yellow]")
    try:
        if not benchmark_results:
            layout.prompt.add_message(
                "[yellow]No benchmark results to save. Run benchmarks first.[/yellow]"
            )
            return

        await asyncio.to_thread(
            save_model_state,
            benchmark_results,
            file_path=".modelstate.json",
            message="Model state saved to .modelstate.json",
            console=layout.console,
        )
        layout.prompt.add_message("[green]Model state saved successfully.[/green]")

    except Exception as e:
        layout.prompt.add_message(f"[red]Error saving model state: {str(e)}[/red]")


async def update_roomodes_action(layout: InteractiveLayout):
    """Update roomodes configuration."""
    layout.prompt.add_message("[yellow]Updating roomodes...[/yellow]")
    try:
        success = await asyncio.to_thread(
            update_room_modes,
            modelstate_path=".modelstate.json",
            roomodes_path=".roomodes",
            settings_path="roo-code-settings.json",
            console=layout.console,
        )
        if success:
            layout.prompt.add_message("[green]Roomodes updated successfully.[/green]")
            layout.prompt.set_status("Roomodes updated")
        else:
            layout.prompt.add_message(
                "[yellow]Roomodes update completed with some issues.[/yellow]"
            )
            layout.prompt.set_status("Roomodes update had issues")

    except FileNotFoundError:
        layout.prompt.add_message(
            "[red]Error: .modelstate.json not found. Save model state first.[/red]"
        )
        layout.prompt.set_status("Error: model state not found")
    except Exception as e:
        layout.prompt.add_message(f"[red]Error updating roomodes: {str(e)}[/red]")
        layout.prompt.set_status("Error updating roomodes")


async def view_benchmark_results(layout: InteractiveLayout):
    """View benchmark results."""
    layout.prompt.add_message(
        "[yellow]Loading benchmark results from .modelstate.json...[/yellow]"
    )
    layout.prompt.set_status("Loading benchmark results...")

    try:
        # Load model state
        model_list = await asyncio.to_thread(
            load_models_as_list, ".modelstate.json", layout.console
        )

        if not model_list:
            layout.prompt.add_message(
                "[yellow]No benchmark results found in .modelstate.json[/yellow]"
            )
            layout.prompt.set_status("No benchmark results found")
            return

        layout.prompt.add_message(
            f"[green]Loaded benchmark results for {len(model_list)} models[/green]"
        )

        # Display summary for each model
        for model in model_list:
            model_id = model.get("model_id", "Unknown")
            last_updated = model.get("last_updated", "Unknown")

            # Get aggregated metrics if available
            agg_metrics = model.get("aggregated_metrics", {})
            overall_score = agg_metrics.get("overall_score", 0)
            test_pass_rate = agg_metrics.get("avg_test_pass_rate", 0)

            layout.prompt.add_message(f"Model: {model_id}")
            layout.prompt.add_message(f"  Last updated: {last_updated}")
            layout.prompt.add_message(f"  Overall score: {overall_score:.2f}")
            layout.prompt.add_message(f"  Test pass rate: {test_pass_rate:.2f}")

        layout.prompt.set_status(f"Loaded results for {len(model_list)} models")

    except FileNotFoundError:
        layout.prompt.add_message(
            "[red]State file not found. Save model state first.[/red]"
        )
        layout.prompt.set_status("Error: model state not found")
    except Exception as e:
        layout.prompt.add_message(
            f"[red]Error loading benchmark results: {str(e)}[/red]"
        )
        layout.prompt.set_status("Error loading benchmark results")


async def launch_context_proxy(layout: InteractiveLayout):
    """Launch the context proxy server."""
    global proxy_server, proxy_stop_function

    layout.prompt.add_message("[yellow]Launching context proxy...[/yellow]")
    try:
        if proxy_server:
            layout.prompt.add_message(
                "[yellow]Proxy server is already running.[/yellow]"
            )
            return

        proxy_server, proxy_stop_function = await asyncio.to_thread(
            run_proxy_in_thread,
            provider_host="localhost",
            provider_port=1234,
            proxy_port=DEFAULT_PROXY_PORT,
            console=layout.console,
        )
        layout.prompt.add_message(
            f"[green]Proxy running on port {DEFAULT_PROXY_PORT}[/green]"
        )

    except Exception as e:
        layout.prompt.add_message(f"[red]Error launching proxy: {str(e)}[/red]")


async def discover_models_only(
    layout: InteractiveLayout, discovered_models_arg: List[DiscoveredModel]
):
    """Discover models and update the TUI layout."""
    global discovered_models

    layout.prompt.add_message("[yellow]Starting model discovery process...[/yellow]")
    layout.prompt.set_status("Discovering models...")

    try:
        layout.models.models.clear()
        temp_models, status = await asyncio.to_thread(action_discover_models)

        if status["total_count"] > 0:
            # Update the global and passed discovered_models
            discovered_models.clear()
            discovered_models.extend(temp_models)
            discovered_models_arg.clear()
            discovered_models_arg.extend(temp_models)

            # Add discovered models to the UI
            for model in discovered_models:
                model_id = model.get("id")
                if not model_id:
                    continue

                provider = "LM Studio"  # Default assumption
                if model.get("provider"):
                    provider = model.get("provider", "Unknown")
                elif model.get("name") and not model.get("family"):
                    provider = "Ollama"

                # Create UIModelInfo instance for TUI
                tui_model_info = UIModelInfo(
                    name=str(model_id),
                    status="discovered",
                    details=f"Provider: {provider}",
                )
                layout.models.add_model(tui_model_info)

            layout.prompt.add_message(
                f"[green]Discovered {status['total_count']} models.[/green]"
            )
            layout.prompt.set_status("Model discovery completed")

        else:
            layout.prompt.add_message("[yellow]No models were discovered.[/yellow]")
            layout.prompt.set_status("No models found")

    except Exception as e:
        layout.prompt.add_message(f"[red]Error during model discovery: {str(e)}[/red]")
        layout.prompt.set_status("Model discovery failed")


async def run_benchmarks_with_config(
    layout: InteractiveLayout,
    app_state: Dict[str, Any],
    benchmark_results: List[Dict[str, Any]],
    discovered_models: List[DiscoveredModel],
):
    """Run benchmarks based on the configuration in app_state."""
    layout.prompt.add_message("[yellow]Starting benchmark execution...[/yellow]")
    layout.prompt.set_status("Preparing benchmarks...")

    model_source = app_state["benchmark_config"].get("model_source", "discovered")
    models_to_run: List[DiscoveredModel] = []

    if model_source == "discovered":
        models_to_run = discovered_models
    elif model_source == "state":
        try:
            raw_models = await asyncio.to_thread(
                load_models_as_list, ".modelstate.json", layout.console
            )
            for raw_model in raw_models:
                if "id" in raw_model:
                    if "family" in raw_model:
                        models_to_run.append(
                            cast(
                                DiscoveredModel,
                                ModelInfo(
                                    id=raw_model["id"],
                                    family=raw_model.get("family", ""),
                                ),
                            )
                        )
                    elif "name" in raw_model:
                        models_to_run.append(
                            cast(
                                DiscoveredModel,
                                OllamaModelInfo(
                                    id=raw_model["id"], name=raw_model["name"]
                                ),
                            )
                        )
        except FileNotFoundError:
            layout.prompt.add_message("[red]State file not found.[/red]")
            return
    elif model_source == "manual":
        layout.console.show_cursor(True)
        ids_str = layout.console.input(
            "Enter model IDs to benchmark (comma-separated): "
        )
        layout.console.show_cursor(False)
        parsed_ids = [mid.strip() for mid in ids_str.split(",") if mid.strip()]
        for mid in parsed_ids:
            models_to_run.append(cast(DiscoveredModel, ModelInfo(id=mid)))

    if not models_to_run:
        layout.prompt.add_message("[red]No models selected or found.[/red]")
        return

    # Determine provider preference
    provider_name = app_state["benchmark_config"].get("provider")
    if provider_name is None:
        providers_detected = _get_available_providers(models_to_run)
        if len(providers_detected) == 1:
            provider_name = providers_detected[0]
        elif len(providers_detected) > 1:
            layout.prompt.add_message(
                "[yellow]Multiple providers detected. Please specify one in config.[/yellow]"
            )
            return
        else:
            layout.prompt.add_message(
                "[red]Cannot determine provider. Specify in config or check models.[/red]"
            )
            return

    filters = app_state["benchmark_config"].get("filters", {})
    num_samples = app_state["benchmark_config"].get("num_samples", 3)
    verbose = app_state["benchmark_config"].get("verbose", False)

    results = await asyncio.to_thread(
        action_run_benchmarks,
        model_source=model_source,
        model_ids=[m["id"] for m in models_to_run] if model_source == "manual" else [],
        discovered_models_list=models_to_run if model_source == "discovered" else [],
        benchmark_filters=filters,
        provider_preference=provider_name,
        run_options={"samples": num_samples, "verbose": verbose},
        benchmark_dir="./benchmarks",
        state_file=".modelstate.json",
    )

    if results:
        benchmark_results.extend(results)
        layout.prompt.add_message("[green]Benchmarking completed successfully.[/green]")
    else:
        layout.prompt.add_message(
            "[yellow]Benchmarking finished, but no results were produced.[/yellow]"
        )


async def run_all_steps(
    layout: InteractiveLayout,
    app_state: Dict[str, Any],
    discovered_models: List[DiscoveredModel],
    benchmark_results: List[Dict[str, Any]],
):
    """Run all steps in sequence."""
    layout.prompt.add_message("[yellow]Running all steps sequentially...[/yellow]")
    layout.prompt.set_status("Running all steps...")

    # 1. Discover models
    await discover_models_only(layout, discovered_models)

    # Check if discovery was successful before proceeding
    if not discovered_models:
        layout.prompt.add_message(
            "[red]Discovery failed. Aborting remaining steps.[/red]"
        )
        layout.prompt.set_status("Discovery failed")
        return

    # 2. Benchmark models
    await run_benchmarks_with_config(
        layout, app_state, benchmark_results, discovered_models
    )

    # Check if benchmarking produced results before proceeding
    if not benchmark_results:
        layout.prompt.add_message(
            "[red]Benchmarking failed or produced no results. Aborting remaining steps.[/red]"
        )
        layout.prompt.set_status("Benchmarking failed")
        return

    # 3. Save model state
    await manual_save_state(layout, benchmark_results)

    # 4. Update roomodes
    await update_roomodes_action(layout)

    layout.prompt.add_message("[green]All steps completed.[/green]")
    layout.prompt.set_status("All steps completed")


async def handle_benchmark_option(
    option: str,
    layout: InteractiveLayout,
    app_state: Dict[str, Any],
    benchmark_results: List[Dict[str, Any]],
    discovered_models: List[DiscoveredModel],
):
    """Handle benchmark submenu options."""
    if option == "all":
        app_state["benchmark_config"]["filters"] = {}
    elif option == "basic":
        app_state["benchmark_config"]["filters"] = {"difficulty": "basic"}
    elif option == "advanced":
        app_state["benchmark_config"]["filters"] = {"difficulty": "advanced"}
    elif option == "custom":
        difficulties = ["basic", "intermediate", "advanced", None]
        types = ["statement", "function", "class", "algorithm", "context", None]

        # Show additional prompts for custom configuration
        layout.console.print("\nCustom Benchmark Configuration")
        difficulties_str = ", ".join(str(d) for d in difficulties if d)
        types_str = ", ".join(str(t) for t in types if t)
        layout.console.print(f"Available difficulties: {difficulties_str}")
        layout.console.print(f"Available types: {types_str}")

        # Get difficulty
        diff = Prompt.ask("Select difficulty", choices=difficulties)
        type_ = Prompt.ask("Select type", choices=types)

        app_state["benchmark_config"]["filters"] = {
            "difficulty": diff if diff != "None" else None,
            "type": type_ if type_ != "None" else None,
        }

    await run_benchmarks_with_config(
        layout, app_state, benchmark_results, discovered_models
    )
