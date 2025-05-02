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
                    has_file_restrictions = any(
                        isinstance(group, list) and len(group) > 1 and group[0] == 'edit'
                        for group in existing['groups']
                    )
                    if has_file_restrictions:
                        mode_entry['groups'] = existing['groups']

                # Preserve other important fields
                for field in preserve_fields:
                    if field in existing and field not in mode_entry:
                        mode_entry[field] = existing[field]

                # Merge customInstructions intelligently
                if 'customInstructions' in existing and 'customInstructions' in mode_entry:
                    existing_instructions = existing['customInstructions']
                    new_instructions = mode_entry['customInstructions']

                    if (
                        "Performance Profile" not in existing_instructions
                        and len(existing_instructions) > 100
                    ):
                        mode_entry['customInstructions'] = f"{existing_instructions}\n\n{new_instructions}"

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
        
        # Call the private function to update roo-code-settings.json
        _update_roo_code_settings(list(existing_modes.values()), settings_path)

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


def _update_roo_code_settings(model_modes: List[Dict[str, Any]], settings_path: str = "roo-code-settings.json") -> bool:
    """
    Update roo-code-settings.json to add or update API configurations for model modes.
    
    Args:
        model_modes: List of model mode entries from .roomodes
        settings_path: Path to the roo-code-settings.json file
    """
    print(f"Updating API configurations in {os.path.abspath(settings_path)}...")
    
    # Read existing settings file
    if not os.path.exists(settings_path):
        print(f"\n[WARNING] {settings_path} not found. You need to export it from Roo Code first.")
        print("\nTo export your settings from Roo Code:")
        print("1. Open Roo Code in VS Code")
        print("2. Click on the Settings icon in the sidebar")
        print("3. Scroll down to the bottom of the settings page")
        print("4. Click 'Export' and save the file as 'roo-code-settings.json' in the root directory of this project")
        print("\nAfter exporting, run this script again to update the settings.\n")
        return False
    
    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            settings = json.load(f)
        print(f"  - Loaded existing settings file")
    except Exception as e:
        print(f"  - Error reading {settings_path}: {str(e)}")
        return False
    
    # Ensure the required structure exists
    if "providerProfiles" not in settings:
        settings["providerProfiles"] = {}
    if "apiConfigs" not in settings["providerProfiles"]:
        settings["providerProfiles"]["apiConfigs"] = {}
    if "modeApiConfigs" not in settings["providerProfiles"]:
        settings["providerProfiles"]["modeApiConfigs"] = {}
    
    api_configs = settings["providerProfiles"]["apiConfigs"]
    mode_api_configs = settings["providerProfiles"]["modeApiConfigs"]
    
    # Create a mapping from model_id to config_id for easy lookup
    model_to_config_id: Dict[str, str] = {}
    for config_id, config in api_configs.items():
        if "lmStudioModelId" in config and config.get("apiProvider") == "lmstudio":
            model_to_config_id[config["lmStudioModelId"]] = config_id
    
    # First pass: Identify and fix any existing mappings that are incorrect
    fixed_mappings = 0
    for mode_slug, config_ref in list(mode_api_configs.items()):
        # Check if this is a mapping to a non-existent config ID
        is_invalid = False
        
        # Case 1: Mapping points to a non-existent config ID
        if config_ref not in api_configs:
            is_invalid = True
            print(f"  - Found invalid mapping for {mode_slug}: points to '{config_ref}' which is not a valid config ID")
        
        # Case 2: Mapping points to the mode slug itself (circular reference)
        elif config_ref == mode_slug:
            is_invalid = True
            print(f"  - Found circular reference in mapping for {mode_slug}: points to itself")
        
        # Case 3: Mapping points to a config that doesn't match the expected model
        elif mode_slug.endswith("-mode"):
            expected_model = mode_slug[:-5]  # Remove "-mode" suffix to get expected model name
            actual_model = api_configs.get(config_ref, {}).get("lmStudioModelId", "")
            
            if actual_model and actual_model != expected_model:
                is_invalid = True
                print(f"  - Found mismatched mapping for {mode_slug}: expected model '{expected_model}' but config points to '{actual_model}'")
        
        if is_invalid:
            # Try to find a correct config for this mode
            if mode_slug.endswith("-mode"):
                expected_model = mode_slug[:-5]  # Remove "-mode" suffix to get expected model name
                
                # Check if we already have a config for this model
                if expected_model in model_to_config_id:
                    correct_config_id = model_to_config_id[expected_model]
                    mode_api_configs[mode_slug] = correct_config_id
                    print(f"    - Fixed by mapping to existing config ID: {correct_config_id}")
                    fixed_mappings += 1
                else:
                    # This will be fixed in the second pass when processing all modes
                    print(f"    - Will create new config in second pass")
    
    # Process each model mode
    processed_modes: List[str] = []
    for mode in model_modes:
        # mode is Dict[str, Any] by type signature
        if "slug" not in mode:
            continue
        
        slug = mode["slug"]
        model_id = mode.get("name", "Unknown Model")
        
        # Skip non-model modes (like boomerang-mode)
        if not slug.endswith("-mode") or slug == "boomerang-mode":
            continue
        
        processed_modes.append(slug)
        print(f"  - Processing mode: {slug}")
        
        # Check if this model already has a valid config
        has_valid_config = False
        if model_id in model_to_config_id:
            config_id = model_to_config_id[model_id]
            # Map the mode to this existing config
            mode_api_configs[slug] = config_id
            print(f"    - Mapped to existing config: {config_id}")
            has_valid_config = True
        
        # If there's no valid config, create a new one
        if not has_valid_config:
            # Use the mode slug as the config ID instead of generating a random ID
            new_config_id = slug
            
            # Determine if this model uses thinking mode
            thinking_mode = False
            
            # Check if the model name indicates thinking
            if "thinking" in model_id.lower():
                thinking_mode = True
                
            # Check if there's a thinking flag in the mode data
            if "benchmarkData" in mode and "thinking" in mode["benchmarkData"]:
                thinking_mode = mode["benchmarkData"]["thinking"]
                
            # Create standardized API config
            new_config: Dict[str, Any] = {
                "apiProvider": "lmstudio",
                "openRouterModelId": "anthropic/claude-3.7-sonnet:beta",
                "openRouterModelInfo": {
                    "maxTokens": 16384,
                    "contextWindow": 200000,
                    "supportsImages": True,
                    "supportsComputerUse": True,
                    "supportsPromptCache": True,
                    "inputPrice": 3,
                    "outputPrice": 15,
                    "cacheWritesPrice": 3.75,
                    "cacheReadsPrice": 0.3,
                    "description": "Claude 3.7 Sonnet is an advanced large language model with improved reasoning, coding, and problem-solving capabilities. It introduces a hybrid reasoning approach, allowing users to choose between rapid responses and extended, step-by-step processing for complex tasks. The model demonstrates notable improvements in coding, particularly in front-end development and full-stack updates, and excels in agentic workflows, where it can autonomously navigate multi-step processes. \n\nClaude 3.7 Sonnet maintains performance parity with its predecessor in standard mode while offering an extended reasoning mode for enhanced accuracy in math, coding, and instruction-following tasks.\n\nRead more at the [blog post here](https://www.anthropic.com/news/claude-3-7-sonnet)",
                    "thinking": thinking_mode
                },
                "vsCodeLmModelSelector": {
                    "vendor": "copilot",
                    "family": "gpt-4o-mini"
                },
                "lmStudioModelId": model_id,
                "lmStudioDraftModelId": "",
                "lmStudioSpeculativeDecodingEnabled": True,
                "modelTemperature": None,
                "rateLimitSeconds": 10,
                "id": slug  # Also set the id field to the slug for consistency
            }
            
            # Add to api_configs and map in mode_api_configs
            api_configs[new_config_id] = new_config
            mode_api_configs[slug] = new_config_id
            model_to_config_id[model_id] = new_config_id
            print(f"    - Created new config with ID: {new_config_id}")
    
    # Final pass: Ensure all mode mappings point to valid config IDs
    for mode_slug, config_ref in list(mode_api_configs.items()):
        if config_ref not in api_configs:
            print(f"  - Warning: Mapping for {mode_slug} still points to invalid config ID: {config_ref}")
            if mode_slug.endswith("-mode"):
                model_name = mode_slug[:-5]
                if model_name in model_to_config_id:
                    mode_api_configs[mode_slug] = model_to_config_id[model_name]
                    print(f"    - Fixed in final pass by mapping to: {model_to_config_id[model_name]}")
                    fixed_mappings += 1
    
    # Write back to file
    try:
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
        print(f"  - Successfully wrote to {settings_path}")
        print(f"  - Updated {len(processed_modes)} mode mappings")
        if fixed_mappings > 0:
            print(f"  - Fixed {fixed_mappings} incorrect mappings that were pointing to invalid values")
        print("\n[IMPORTANT] To apply these changes to Roo Code:")
        print("1. Open Roo Code in VS Code")
        print("2. Click on the Settings icon in the sidebar")
        print("3. Scroll down to the bottom of the settings page")
        print("4. Click 'Import' and select the updated 'roo-code-settings.json' file from this project's directory")
        return True
    except Exception as e:
        print(f"  - Error writing to {settings_path}: {str(e)}")
        return False
