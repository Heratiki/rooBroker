"""Core mode management functionality.

This module provides functions for updating room modes based on model state information.
It handles the generation, updating, and management of custom modes for the rooBroker system.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Union

from rich.console import Console

from rooBroker.roomodes.mode_generation import generate_mode_entry, create_boomerang_mode


def update_room_modes(
    modelstate_path: str = ".modelstate.json", 
    roomodes_path: str = ".roomodes", 
    settings_path: str = "roo-code-settings.json",
    console: Optional[Console] = None
) -> bool:
    """Update room modes with enhanced model information including benchmark data.
    
    This function reads model information from the model state file and generates
    or updates corresponding room modes in the .roomodes file. It preserves any
    existing custom configurations while updating model-specific information.
    
    Args:
        modelstate_path: Path to the model state JSON file.
        roomodes_path: Path to the .roomodes file.
        settings_path: Path to the roo-code-settings.json file.
        console: Optional Rich console for formatted output. If None, a new console is created.
        
    Returns:
        True if the room modes were successfully updated, False otherwise.
        
    Raises:
        FileNotFoundError: If the model state file doesn't exist.
    """
    if console is None:
        console = Console()
    
    console.print("[bold]Starting room modes update process...[/bold]")
    console.print(f"  - Looking for modelstate at: {os.path.abspath(modelstate_path)}")
    console.print(f"  - Will write roomodes to: {os.path.abspath(roomodes_path)}")
    
    # Read modelstate with error handling
    if not os.path.exists(modelstate_path):
        error_msg = f"Error: {modelstate_path} not found"
        console.print(f"[red]{error_msg}[/red]")
        raise FileNotFoundError(error_msg)
    
    try:
        with open(modelstate_path, "r", encoding="utf-8") as f:
            modelstate: Union[Dict[str, Any], List[Dict[str, Any]]] = json.load(f)
        
        # Count models to process
        model_count = 0
        if isinstance(modelstate, dict):
            if "models" in modelstate:
                model_count = len(modelstate["models"])
            else:
                model_count = len(modelstate)
        else:
            model_count = len(modelstate)
        
        console.print(f"  - Found {model_count} models in modelstate")
        
        # Handle different possible formats for the model state
        models: List[Dict[str, Any]]
        if isinstance(modelstate, dict):
            models = modelstate.get("models", list(modelstate.values()))
        else:
            models = modelstate  # type: ignore

        # Read or initialize .roomodes
        if os.path.exists(roomodes_path):
            console.print(f"  - Found existing .roomodes file")
            try:
                with open(roomodes_path, "r", encoding="utf-8") as f:
                    roomodes: Dict[str, Any] = json.load(f)
                custom_modes: List[Dict[str, Any]] = roomodes.get("customModes", [])
                console.print(f"  - Existing file has {len(custom_modes)} custom modes")
            except json.JSONDecodeError:
                console.print(f"[yellow]  - Warning: Existing .roomodes file is not valid JSON, creating new file[/yellow]")
                custom_modes = []
                roomodes = {"customModes": custom_modes}
        else:
            console.print(f"  - No existing .roomodes file found, will create new file")
            custom_modes = []
            roomodes = {"customModes": custom_modes}

        # Build a dict of existing modes by slug
        existing_modes: Dict[str, Dict[str, Any]] = {mode["slug"]: mode for mode in custom_modes}
        console.print(f"  - Processing {len(models)} models...")

        # Always ensure Boomerang Mode exists
        boomerang_slug = "boomerang-mode"
        if boomerang_slug not in existing_modes:
            console.print(f"  - Adding Boomerang Mode (essential for model orchestration)")
            existing_modes[boomerang_slug] = create_boomerang_mode()
        
        # Add/update modes for each model
        for model in models:
            model_id: str = model.get("model_id", model.get("id", "unknown"))  # type: ignore
            console.print(f"    - Processing model: {model_id}")
            mode_entry = generate_mode_entry(model)
            slug = mode_entry["slug"]
            
            if slug in existing_modes:
                existing = existing_modes[slug]
                
                # Fields to carefully preserve from existing configurations
                preserve_fields = [
                    'groups',            # Preserve custom tool permissions
                    'source',            # Preserve whether it's global or project-specific
                    'roleDefinition',    # Preserve custom role definitions if set by user
                    'apiConfiguration'   # Preserve any custom API configurations
                ]
                
                # Special handling for groups to preserve file restrictions
                if 'groups' in existing:
                    # Check if the existing mode has any custom file restrictions
                    has_file_restrictions = False
                    for group in existing['groups']:
                        if isinstance(group, list) and len(group) > 1 and group[0] == 'edit':
                            has_file_restrictions = True
                            break
                    
                    # If there are custom file restrictions, preserve them
                    if has_file_restrictions:
                        mode_entry['groups'] = existing['groups']
                
                # Preserve other important fields
                for field in preserve_fields:
                    if field in existing and field not in mode_entry:
                        mode_entry[field] = existing[field]
                
                # Update the existing mode with new fields
                existing_modes[slug] = mode_entry
                console.print(f"      - Updated existing mode: {slug}")
            else:
                existing_modes[slug] = mode_entry
                console.print(f"      - Added new mode: {slug}")
        
        # Rebuild customModes list from our dictionary
        roomodes["customModes"] = list(existing_modes.values())
        
        # Write updated roomodes file
        with open(roomodes_path, "w", encoding="utf-8") as f:
            json.dump(roomodes, f, indent=2)
        
        console.print(f"[green]✓ Successfully updated .roomodes with {len(roomodes['customModes'])} modes[/green]")
        return True
        
    except Exception as e:
        console.print(f"[red]Error updating room modes: {str(e)}[/red]")
        return False


def get_mode_info(
    mode_slug: str,
    roomodes_path: str = ".roomodes",
    console: Optional[Console] = None
) -> Optional[Dict[str, Any]]:
    """Get information about a specific room mode.
    
    Args:
        mode_slug: The slug identifier of the mode to retrieve.
        roomodes_path: Path to the .roomodes file.
        console: Optional Rich console for formatted output.
        
    Returns:
        The mode information as a dictionary, or None if not found.
    """
    if console is None:
        console = Console()
        
    if not os.path.exists(roomodes_path):
        console.print(f"[yellow]Room modes file not found at {roomodes_path}[/yellow]")
        return None
        
    try:
        with open(roomodes_path, "r", encoding="utf-8") as f:
            roomodes = json.load(f)
            
        custom_modes = roomodes.get("customModes", [])
        for mode in custom_modes:
            if mode.get("slug") == mode_slug:
                return mode
                
        console.print(f"[yellow]Mode '{mode_slug}' not found in room modes[/yellow]")
        return None
        
    except Exception as e:
        console.print(f"[red]Error retrieving mode information: {str(e)}[/red]")
        return None
