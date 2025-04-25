"""Core state management functionality.

This module provides functions for saving and loading application state,
particularly model state information (discovered models, benchmark results).
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console


def save_model_state(
    data: List[Dict[str, Any]],
    file_path: str = ".modelstate.json",
    message: str = "Model state saved",
    console: Optional[Console] = None
) -> None:
    """Save model state information to a JSON file.
    
    Args:
        data: List of model information dictionaries to save.
        file_path: Path to the state file. Defaults to ".modelstate.json".
        message: Success message to display. Defaults to "Model state saved".
        console: Optional Rich console for formatted output. If None, a new console is created.
        
    Raises:
        IOError: If there's an error writing to the file.
    """
    if console is None:
        console = Console()
        
    try:
        # Convert list of models to a dictionary keyed by model_id for consistency
        data_dict = {}
        for model in data:
            model_id = model.get("model_id", model.get("id"))
            if model_id:
                data_dict[model_id] = model
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data_dict, f, indent=2, ensure_ascii=False)
        console.print(f"[green]{message}[/green]")
    except Exception as e:
        console.print(f"[red]Error saving model state: {e}[/red]")


def load_model_state(
    file_path: str = ".modelstate.json",
    console: Optional[Console] = None
) -> Dict[str, Dict[str, Any]]:
    """Load model state information from a JSON file.
    
    Args:
        file_path: Path to the state file. Defaults to ".modelstate.json".
        console: Optional Rich console for formatted output. If None, a new console is created.
        
    Returns:
        Dictionary mapping model IDs to model information dictionaries.
        Returns an empty dictionary if the file doesn't exist or cannot be parsed.
    """
    if console is None:
        console = Console()
        
    state_path = Path(file_path)
    if not state_path.exists():
        console.print(f"[yellow]No saved state found at {file_path}[/yellow]")
        return {}
    
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception as e:
        console.print(f"[red]Error loading model state: {e}[/red]")
        return {}


def load_models_as_list(
    file_path: str = ".modelstate.json",
    console: Optional[Console] = None
) -> List[Dict[str, Any]]:
    """Load model state and convert to a list format.
    
    This is a convenience function that loads the model state dictionary
    and converts it to a list format, which is often more convenient for
    passing to UI formatting functions.
    
    Args:
        file_path: Path to the state file. Defaults to ".modelstate.json".
        console: Optional Rich console for formatted output.
        
    Returns:
        List of model information dictionaries.
        Returns an empty list if the file doesn't exist or cannot be parsed.
    """
    state_dict = load_model_state(file_path, console)
    return list(state_dict.values())
