from .core.discovery import discover_models_with_status
from .core.log_config import logger
from rooBroker.roo_types.discovery import DiscoveredModel, ModelInfo, OllamaModelInfo
from typing import List, Dict, Any, Tuple, Optional
from rooBroker.core.benchmarking import load_benchmarks_from_directory, run_standard_benchmarks
from rooBroker.core.state import load_models_as_list
from rooBroker.interfaces.lmstudio.client import LMStudioClient
from rooBroker.interfaces.ollama.client import OllamaClient
from rich.progress import Progress, TextColumn, BarColumn, MofNCompleteColumn, TimeRemainingColumn
from rich.console import Console

def action_discover_models() -> Tuple[List[DiscoveredModel], Dict[str, Any]]:
    """Discover models and return the results along with their status."""
    try:
        models, status = discover_models_with_status()
        return models, status
    except Exception as e:
        logger.error(f"Error discovering models: {e}")
        return [], {"error": str(e)}

def action_run_benchmarks(
    model_source: str,  # "discovered", "state", or "manual"
    model_ids: List[str] = [],  # Used if model_source is "manual"
    discovered_models_list: List[DiscoveredModel] = [],  # Used if model_source is "discovered"
    benchmark_filters: Dict[str, Any] = {},  # e.g., {"tags": ["python"], "difficulty": "basic"}
    provider_preference: Optional[str] = None,  # "lmstudio" or "ollama", determines client if not obvious from models
    run_options: Dict[str, Any] = {},  # e.g., {"samples": 20, "verbose": False}
    benchmark_dir: str = "./benchmarks",  # Directory for benchmarks
    state_file: str = ".modelstate.json"  # State file path
) -> List[Dict[str, Any]]:  # Returns benchmark results
    """Run benchmarks based on the provided parameters."""
    try:
        # Load benchmarks
        benchmarks = load_benchmarks_from_directory(benchmark_dir)
        if not benchmarks:
            logger.error("No benchmarks found in the specified directory.")
            return []

        # Filter benchmarks
        filtered_benchmarks = [
            bm for bm in benchmarks
            if (not benchmark_filters.get("tags") or any(tag in bm.get("tags", []) for tag in benchmark_filters["tags"]))
            and (not benchmark_filters.get("difficulty") or bm.get("difficulty") == benchmark_filters["difficulty"])
            and (not benchmark_filters.get("type") or bm.get("type") == benchmark_filters["type"])
        ]
        if not filtered_benchmarks:
            logger.error("No benchmarks match the provided filters.")
            return []

        # Select models
        models_to_run: List[DiscoveredModel] = []
        if model_source == "discovered":
            models_to_run = discovered_models_list
        elif model_source == "state":
            try:
                raw_models = load_models_as_list(state_file)
                for raw_model in raw_models:
                    if "family" in raw_model and "id" in raw_model:
                        constructor_dict = {"id": raw_model["id"]}
                        for key in ["family", "context_window", "created", "provider"]:
                            if key in raw_model and raw_model[key] is not None:
                                constructor_dict[key] = raw_model[key]
                        models_to_run.append(ModelInfo(**constructor_dict))
                    elif "name" in raw_model and "id" in raw_model:
                        constructor_dict = {"id": raw_model["id"], "name": raw_model["name"]}
                        for key in ["version"]:
                            if key in raw_model and raw_model[key] is not None:
                                constructor_dict[key] = raw_model[key]
                        models_to_run.append(OllamaModelInfo(**constructor_dict))
                    else:
                        logger.warning(f"Skipping invalid model data from state: {raw_model}")
            except FileNotFoundError:
                logger.error("State file not found. Ensure the state file exists.")
                return []
        elif model_source == "manual":
            for mid in model_ids:
                models_to_run.append(ModelInfo(id=mid))

        if not models_to_run:
            logger.error("No models selected or found.")
            return []

        # Determine client
        client = None
        if provider_preference == "lmstudio":
            client = LMStudioClient()
        elif provider_preference == "ollama":
            client = OllamaClient()
        else:
            has_lmstudio = any(model.get("family") for model in models_to_run)
            has_ollama = any(model.get("name") and not model.get("family") for model in models_to_run)
            if has_lmstudio and not has_ollama:
                client = LMStudioClient()
            elif has_ollama and not has_lmstudio:
                client = OllamaClient()
            else:
                logger.error("Unable to determine provider. Specify provider_preference.")
                return []

        # Run benchmarks
        samples = run_options.get("samples", 20)
        verbose = run_options.get("verbose", False)
        console = Console()
        with Progress(
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeRemainingColumn(),
            console=console,
            transient=True
        ) as progress:
            results = run_standard_benchmarks(
                client=client,
                models_to_benchmark=models_to_run,
                benchmarks_to_run=filtered_benchmarks,
                progress=progress,
                num_samples=samples,
                verbose=verbose
            )
        return results

    except Exception as e:
        logger.error(f"Error during benchmark execution: {str(e)}")
        return []
