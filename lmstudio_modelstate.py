import json
import os
from typing import List, Dict, Any

def update_modelstate_json(
    benchmark_results: List[Dict[str, Any]],
    path: str = ".modelstate.json"
) -> None:
    """
    Create or update the .modelstate.json file with benchmark results.

    Args:
        benchmark_results: List of dicts, each containing model_id, context_window, scores, failures, last_updated.
        path: Path to the .modelstate.json file (default: workspace root).
    """
    # Load existing data if file exists
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                modelstate = json.load(f)
        except Exception:
            modelstate = {}
    else:
        modelstate = {}

    # Check if data is wrapped in a "models" key (from main.py's save_modelstate)
    if isinstance(modelstate, dict) and "models" in modelstate:
        # Extract the models list
        models_list = modelstate["models"]
        # Convert to dict by model_id for easy update
        modelstate_dict = {entry["model_id"] if "model_id" in entry else entry.get("id", "unknown"): entry 
                          for entry in models_list}
    # If it's already a dict mapping model_id to details
    elif isinstance(modelstate, dict) and not "models" in modelstate:
        modelstate_dict = modelstate
    # Legacy: convert list to dict
    elif isinstance(modelstate, list):
        modelstate_dict = {entry["model_id"] if "model_id" in entry else entry.get("id", "unknown"): entry 
                          for entry in modelstate if "model_id" in entry or "id" in entry}
    else:
        modelstate_dict = {}

    # Update or add entries from benchmark_results
    for result in benchmark_results:
        model_id = result.get("model_id", result.get("id"))
        if not model_id:
            continue  # skip invalid entries
        modelstate_dict[model_id] = result

    # Write back as a dict (model_id -> entry)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(modelstate_dict, f, indent=2, ensure_ascii=False)