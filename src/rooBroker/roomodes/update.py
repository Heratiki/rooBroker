import json
import os
import traceback
from typing import Dict, List, Any, Set, Optional, Union


from .mode_generation import generate_mode_entry, create_boomerang_mode


def update_roomodes(
    modelstate_path: str = ".modelstate.json", 
    roomodes_path: str = ".roomodes", 
    settings_path: str = "roo-code-settings.json"
) -> bool:
    """Update .roomodes with enhanced model information including benchmark data."""
    # Improved error handling and logging
    print(f"Starting roomodes update process...")
    print(f"  - Looking for modelstate at: {os.path.abspath(modelstate_path)}")
    print(f"  - Will write roomodes to: {os.path.abspath(roomodes_path)}")
    
    # Read modelstate with better error handling
    if not os.path.exists(modelstate_path):
        error_msg = f"Error: {modelstate_path} not found"
        print(error_msg)
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
        
        print(f"  - Found {model_count} models in modelstate")
        
        # Handle different possible formats for the model state
        models: List[Dict[str, Any]]
        if isinstance(modelstate, dict):
            models = modelstate.get("models", list(modelstate.values()))
        else:
            models = modelstate  # type: ignore

        # Read or initialize .roomodes
        if os.path.exists(roomodes_path):
            print(f"  - Found existing .roomodes file")
            try:
                with open(roomodes_path, "r", encoding="utf-8") as f:
                    roomodes: Dict[str, Any] = json.load(f)
                custom_modes: List[Dict[str, Any]] = roomodes.get("customModes", [])
                print(f"  - Existing file has {len(custom_modes)} custom modes")
            except json.JSONDecodeError:
                print(f"  - Warning: Existing .roomodes file is not valid JSON, creating new file")
                custom_modes = []
                roomodes = {"customModes": custom_modes}
        else:
            print(f"  - No existing .roomodes file found, will create new file")
            custom_modes = []
            roomodes = {"customModes": custom_modes}

        # Build a dict of existing modes by slug
        existing_modes: Dict[str, Dict[str, Any]] = {mode["slug"]: mode for mode in custom_modes}
        print(f"  - Processing {len(models)} models...")

        # Always ensure Boomerang Mode exists
        boomerang_slug = "boomerang-mode"
        if boomerang_slug not in existing_modes:
            print(f"  - Adding Boomerang Mode (essential for model orchestration)")
            existing_modes[boomerang_slug] = create_boomerang_mode()
        
        # Add/update modes for each model
        for model in models:
            model_id: str = model.get("model_id", model.get("id", "unknown"))  # type: ignore
            print(f"    - Processing model: {model_id}")
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
                    for group in existing['groups']:  # type: ignore
                        # group may be Union[str, List[Any]]
                        if isinstance(group, list) and len(group) > 1 and group[0] == 'edit':  # type: ignore
                            # Found a file restriction configuration for edit
                            has_file_restrictions = True
                            break
                    
                    if has_file_restrictions:
                        # If user has set custom file restrictions, preserve them entirely
                        mode_entry['groups'] = existing['groups']
                    else:
                        # Only update if no custom restrictions exist
                        for key in preserve_fields:
                            if key in existing and key != 'groups':
                                mode_entry[key] = existing[key]
                else:
                    # No groups in existing, preserve other fields
                    for key in preserve_fields:
                        if key in existing:
                            mode_entry[key] = existing[key]
                
                # Merge customInstructions intelligently if they've been manually edited
                if 'customInstructions' in existing:
                    existing_instr = existing['customInstructions']
                    new_instr = mode_entry['customInstructions']
                    
                    # If the existing instructions don't contain our standard performance profile
                    # and are over 100 chars, it suggests the user has customized them
                    if 'Performance Profile' not in existing_instr and len(existing_instr) > 100:
                        # Append new performance data to user's custom instructions
                        mode_entry['customInstructions'] = existing_instr + "\n\n" + new_instr
                
                print(f"      - Updating existing mode: {slug} (preserving custom settings)")
            else:
                print(f"      - Creating new mode: {slug}")
            
            existing_modes[slug] = mode_entry

        # Preserve non-model modes but ensure Boomerang Mode is always included
        model_slugs: Set[str] = {generate_mode_entry(m)["slug"] for m in models}
        non_model_modes: List[Dict[str, Any]] = [m for m in custom_modes if m["slug"] not in model_slugs and m["slug"] != "boomerang-mode"]
        model_modes: List[Dict[str, Any]] = [existing_modes[s] for s in sorted(model_slugs)]
        
        # Ensure boomerang mode is first in the list for visibility
        final_modes: List[Dict[str, Any]] = []
        boomerang_mode: Optional[Dict[str, Any]] = existing_modes.get("boomerang-mode")
        if boomerang_mode:
            final_modes.append(boomerang_mode)
        final_modes.extend(non_model_modes)
        final_modes.extend(model_modes)
        
        print(f"  - Adding Boomerang Mode for orchestration")
        print(f"  - Preserving {len(non_model_modes)} other non-model modes")
        print(f"  - Adding {len(model_modes)} model modes")
        
        # Set the final modes list
        roomodes["customModes"] = final_modes

        # Write back to .roomodes
        try:
            with open(roomodes_path, "w", encoding="utf-8") as f:
                json.dump(roomodes, f, indent=4, ensure_ascii=False)
            print(f"  - Successfully wrote to {roomodes_path}")
            print(f"  - Total modes in file: {len(roomodes['customModes'])}")
            
            # After successfully updating .roomodes, also update roo-code-settings.json
            if settings_path:
                update_success = update_roo_code_settings(final_modes, settings_path)
                if update_success:
                    print(f"  - Successfully updated API configurations in {settings_path}")
                else:
                    print(f"  - Warning: Failed to update API configurations in {settings_path}")
            
            return True
        except Exception as e:
            print(f"  - Error writing to {roomodes_path}: {str(e)}")
            raise
            
    except Exception as e:
        print(f"Error updating roomodes: {str(e)}")
        traceback.print_exc()
        return False


def update_roo_code_settings(model_modes: List[Dict[str, Any]], settings_path: str = "roo-code-settings.json") -> bool:
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
