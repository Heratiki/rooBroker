import json
import os
from json.decoder import JSONDecodeError
from typing import TypedDict, cast, Union

from roo_types.models import ModelState

class ModelStateFile(TypedDict, total=False):
    models: list[ModelState]

ModelStateDict = dict[str, ModelState]
LoadedModelState = Union[ModelStateFile, ModelStateDict, list[ModelState]]

def update_modelstate_json(
    benchmark_results: list[ModelState],
    path: str = ".modelstate.json"
) -> None:
    """
    Create or update the .modelstate.json file with benchmark results.

    Args:
        benchmark_results: List of model states with benchmark results.
        path: Path to the .modelstate.json file (default: workspace root).
    """
    # Load existing data if file exists
    modelstate: LoadedModelState = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                modelstate = cast(LoadedModelState, json.load(f))
        except (JSONDecodeError, OSError) as e:
            print(f"Error reading modelstate file: {e}")
            modelstate = {}

    # Initialize the output dictionary
    modelstate_dict: ModelStateDict = {}

    # Check if data is wrapped in a "models" key (from main.py's save_modelstate)
    if isinstance(modelstate, dict) and "models" in modelstate:
        # Extract the models list
        models_list = cast(list[ModelState], modelstate["models"])
        # Convert to dict by model_id for easy update
        modelstate_dict.update({
            entry.get("model_id", entry.get("id", "unknown")): entry 
            for entry in models_list 
            if ("model_id" in entry or "id" in entry)
        })
    # If it's already a dict mapping model_id to details
    elif isinstance(modelstate, dict) and "models" not in modelstate:
        modelstate_dict = cast(ModelStateDict, modelstate)
    # Legacy: convert list to dict
    elif isinstance(modelstate, list):
        modelstate_dict.update({
            entry.get("model_id", entry.get("id", "unknown")): entry 
            for entry in modelstate 
            if ("model_id" in entry or "id" in entry)
        })

    # Update or add entries from benchmark_results
    for result in benchmark_results:
        model_id = result.get("model_id") or result.get("id")
        if not model_id:
            continue  # skip invalid entries
        modelstate_dict[model_id] = result

    # Write back as a dict (model_id -> entry)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(modelstate_dict, f, indent=2, ensure_ascii=False)