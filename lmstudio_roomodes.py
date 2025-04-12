import json
import os
import re
import uuid

def slugify(name):
    """Create a slug for the mode from the model name."""
    # Lowercase, replace non-alphanum with hyphens, collapse multiple hyphens, strip
    slug = re.sub(r'[^a-zA-Z0-9]+', '-', name.lower())
    slug = re.sub(r'-+', '-', slug).strip('-')
    return f"{slug}-mode"

def generate_mode_entry(model):
    """Generate a RooCode mode entry from a model dict that's optimized for coding tasks."""
    model_id = model.get('model_id', model.get('id', 'Unknown Model'))
    model_name = model_id
    context_window = model.get('context_window', 0)
    
    # Get benchmark scores and improvements
    score_simple = model.get('score_simple', 0.0)
    score_moderate = model.get('score_moderate', 0.0)
    score_complex = model.get('score_complex', 0.0)
    score_context_window = model.get('score_context_window', 0.0)
    
    # Get BIG-BENCH scores if available
    bigbench_scores = model.get('bigbench_scores', {})
    bigbench_overall = bigbench_scores.get('overall', 0.0)
    bigbench_tasks = bigbench_scores.get('tasks', [])
    
    # Calculate overall score including BIG-BENCH if available
    base_score = (score_simple + score_moderate + score_complex + score_context_window) / 4
    overall_score = (base_score + bigbench_overall) / 2 if bigbench_overall > 0 else base_score
    
    # Round scores for cleaner display
    score_simple = round(score_simple, 2)
    score_moderate = round(score_moderate, 2)
    score_complex = round(score_complex, 2)
    score_context_window = round(score_context_window, 2)
    bigbench_overall = round(bigbench_overall, 2) if bigbench_overall > 0 else 0.0
    overall_score = round(overall_score, 2)
    
    # Get prompt improvements if available
    improvements = model.get('prompt_improvements', {})
    improved_prompts = {}
    coding_strategies = []
    
    # Extract useful strategies from improvements
    for task_name, imp in improvements.items():
        if imp.get('improved_prompt'):
            # Skip HTTP errors
            if 'HTTPConnectionPool' not in str(imp.get('analysis', '')):
                improved_prompts[task_name] = {
                    'original': imp.get('original_prompt', ''),
                    'improved': imp.get('improved_prompt', ''),
                    'analysis': imp.get('analysis', '')
                }
                
                # Extract useful coding strategies from analysis using our specialized extractor
                analysis = imp.get('analysis', '')
                if analysis and len(analysis) > 10 and 'HTTPConnectionPool' not in analysis:
                    # Get coding-specific insights based on task type
                    insights = extract_coding_insights(analysis, task_name)
                    if insights:
                        coding_strategies.extend(insights)

    # Create a coding-focused role definition modeled after RooCode's default
    base_role = "You are Roo, a highly skilled software engineer with extensive knowledge in many programming languages, frameworks, design patterns, and best practices."
    
    # Customize based on both model capabilities and BIG-BENCH scores
    if overall_score > 0.8:
        role_addition = "excel at complex coding tasks, refactoring, and implementing sophisticated solutions"
        if bigbench_overall > 0.8:
            role_addition += ", with exceptional performance on advanced reasoning and comprehension tasks"
    elif overall_score > 0.5:
        role_addition = "handle moderately complex programming tasks and provide solid implementation advice"
        if bigbench_overall > 0.5:
            role_addition += ", with good reasoning and task comprehension abilities"
    else:
        role_addition = "focus on providing simpler code snippets, explanations, and guidance on basic programming concepts"
        if bigbench_overall > 0.0:
            role_addition += ", with basic reasoning capabilities"
    
    role_definition = f"{base_role} Using the {model_name} language model with a {context_window}-token context window, you {role_addition}."
    
    # Build custom instructions focused on both coding capabilities and context management
    instructions = []
    
    # Document the model's complete performance profile
    instructions.append(f"## {model_name} Performance Profile")
    instructions.append(f"* Simple tasks: {score_simple}")
    instructions.append(f"* Moderate tasks: {score_moderate}")
    instructions.append(f"* Complex tasks: {score_complex}")
    instructions.append(f"* Context window: {score_context_window}")
    if bigbench_overall > 0.0:
        instructions.append(f"* BIG-BENCH-HARD: {bigbench_overall}")
    instructions.append("")
    
    # Add context window specific guidance
    if score_context_window > 0.8:
        instructions.append("## Memory & Context Management")
        instructions.append("* This model has excellent context handling capability")
        instructions.append("* Maximum context window: " + str(context_window) + " tokens")
        instructions.append("* Can work with lengthy code files and requirements")
        instructions.append("* Suitable for multi-part conversations with detailed context")
        instructions.append("* Can retain understanding across complex interactions")
    elif score_context_window > 0.4:
        instructions.append("## Memory & Context Management")
        instructions.append("* This model has moderate context handling capability")
        instructions.append("* Maximum context window: " + str(context_window) + " tokens")
        instructions.append("* Works best when complex tasks are broken into smaller parts")
        instructions.append("* May need occasional reminders about earlier parts of the conversation")
    else:
        instructions.append("## Memory & Context Management")
        instructions.append("* This model has limited context handling capability")
        instructions.append("* Maximum context window: " + str(context_window) + " tokens")
        instructions.append("* Break large tasks into very small subtasks for best results")
        instructions.append("* Keep conversations focused on one topic at a time")
    
    # Add specific coding strategies based on benchmark performance
    instructions.append("")
    instructions.append("## Coding Specialties")
    
    if score_complex > 0.7 or bigbench_overall > 0.7:
        instructions.append("* Advanced algorithm implementation and optimization")
        instructions.append("* Complex problem decomposition and solution design")
        instructions.append("* Design pattern application")
    if score_moderate > 0.7 or bigbench_overall > 0.5:
        instructions.append("* Function and class implementation")
        instructions.append("* API design and integration")
    if score_simple > 0.7:
        instructions.append("* Basic script creation")
        instructions.append("* Syntax explanation and error fixing")
    
    # If we have BIG-BENCH results, add specific task performance insights
    if bigbench_tasks:
        instructions.append("")
        instructions.append("## Specialized Capabilities")
        
        # Add top 3 highest scoring BIG-BENCH tasks
        sorted_tasks = sorted(bigbench_tasks, key=lambda x: x.get('Score', 0), reverse=True)[:3]
        for task in sorted_tasks:
            task_name = task.get('Task', '').replace('_', ' ').title()
            task_score = task.get('Score', 0)
            if task_score > 0.7:
                instructions.append(f"* Strong performance in {task_name}")
            elif task_score > 0.5:
                instructions.append(f"* Moderate capability in {task_name}")
    
    # Add model-specific prompt strategies that were discovered during benchmarking
    if coding_strategies:
        instructions.append("")
        instructions.append("## Effective Coding Strategies")
        
        # Add unique extracted coding strategies (limit to top 5)
        unique_strategies = []
        for strategy in coding_strategies:
            strategy_normalized = strategy.lower()
            # Check if this is a unique insight
            if not any(strategy_normalized in existing.lower() for existing in unique_strategies):
                unique_strategies.append(strategy)
                if len(unique_strategies) >= 5:  # Limit to 5 strategies
                    break
                    
        for strategy in unique_strategies:
            instructions.append(f"* {strategy}")
    
    # Add specific instructions for use with Boomerang Mode
    instructions.append("")
    instructions.append("## Integration with Boomerang Mode")
    instructions.append("Use this mode as part of RooCode's Boomerang Mode orchestration for these tasks:")
    
    if overall_score > 0.8:
        instructions.append("* Complex code generation and refactoring")
        instructions.append("* Architecture design and optimization")
        instructions.append("* Debugging and problem-solving tasks")
        instructions.append("")
        instructions.append("When using with Boomerang Mode, leverage this model's large context window to handle complex tasks that require understanding multiple files or extensive context.")
    elif overall_score > 0.5:
        instructions.append("* Implementation of well-defined components")
        instructions.append("* Writing clearly specified functions and classes")
        instructions.append("* Analyzing and explaining existing code")
        instructions.append("")
        instructions.append("When delegating to this model via Boomerang Mode, break down tasks to fit within its context window and define clear boundaries for each subtask.")
    else:
        instructions.append("* Generating simple code snippets")
        instructions.append("* Documentation and code comments")
        instructions.append("* Answering basic programming questions")
        instructions.append("")
        instructions.append("This model works best with very small, focused subtasks when used with Boomerang Mode orchestration.")
                
    # Create a slug directly from the model_id to guarantee uniqueness
    unique_slug = slugify(model_id)
    
    # Define appropriate groups based on model's capabilities, focused on coding tasks
    groups = ["read"]
    
    # Add edit capability if model is capable enough for coding tasks
    if score_moderate > 0.5 or score_complex > 0.5:
        # For coding models, allow editing of code files only based on capabilities
        edit_restrictions = {
            "fileRegex": "\\.(py|js|ts|jsx|tsx|java|cpp|c|h|hpp|rb|go|rs|php|html|css|json|md)$",
            "description": "Code and documentation files"
        }
        groups.append(["edit", edit_restrictions])
    else:
        # Limited editing capabilities
        edit_restrictions = {
            "fileRegex": "\\.(md|txt)$",
            "description": "Documentation files only"
        }
        groups.append(["edit", edit_restrictions])
    
    # Add command capability for models good at coding
    if overall_score > 0.7:
        groups.append("command")
    
    # Add MCP capability for all models as they're already integrated
    groups.append("mcp")

    # Create mode entry according to RooCode spec with explicit context window settings
    mode_entry = {
        "slug": unique_slug,
        "name": model_name,
        "roleDefinition": role_definition,
        "groups": groups,
        "source": "global",
        "customInstructions": "\n".join(instructions),
        "contextWindow": context_window,  # Add explicit context window size
        "maxResponseTokens": min(2000, int(context_window * 0.25)) if context_window else 2000,  # Reserve 25% for response
        "benchmarkData": {
            "scores": {
                "simple": score_simple,
                "moderate": score_moderate,
                "complex": score_complex,
                "context_window": score_context_window,
                "bigbench": bigbench_overall,
                "overall": overall_score
            },
            "lastUpdated": model.get('last_updated', '')
        }
    }
    
    # Store benchmark data
    if model.get('last_updated'):
        mode_entry["benchmarkData"]["lastUpdated"] = model.get('last_updated', '')
        
        # Only include clean, useful prompt improvements for coding tasks
        if improved_prompts:
            filtered_improvements = {}
            for task, data in improved_prompts.items():
                if 'HTTPConnectionPool' not in str(data.get('analysis', '')):
                    filtered_improvements[task] = {
                        "improved": data.get('improved', ''),
                        "original": data.get('original', '')
                    }
            
            if filtered_improvements:
                mode_entry["benchmarkData"]["promptImprovements"] = filtered_improvements

    return mode_entry

def extract_strategy_from_analysis(analysis, context="coding"):
    """Extract a concise strategy from prompt improvement analysis."""
    if not analysis or len(analysis) < 20:
        return None
        
    # Clean up the analysis text
    cleaned = analysis.replace("Analysis failed:", "").strip()
    
    # Look for key phrases that indicate useful strategies
    phrases = [
        "be more specific", "provide context", "include examples",
        "break down", "step by step", "clarify", "specify", 
        "detailed", "clear instructions", "format"
    ]
    
    for phrase in phrases:
        if phrase in cleaned.lower():
            # Find the sentence containing this phrase
            sentences = cleaned.split('.')
            for sentence in sentences:
                if phrase in sentence.lower() and len(sentence) > 15:
                    # Clean and return a concise version
                    return sentence.strip().capitalize()
    
    # Default strategy if no specific phrases found
    if len(cleaned) > 150:
        return cleaned[:150].strip() + "..."
    return cleaned.capitalize()

def extract_core_insight(analysis):
    """Extract the core insight from an analysis, limited to 100 chars."""
    if not analysis or len(analysis) < 10:
        return ""
        
    # Clean up the analysis text
    cleaned = analysis.replace("Analysis failed:", "").strip()
    
    # Take first sentence or first 100 chars
    if '.' in cleaned:
        first_sentence = cleaned.split('.')[0].strip()
        if len(first_sentence) > 10:
            return first_sentence
    
    # Fallback to character limit
    if len(cleaned) > 100:
        return cleaned[:100] + "..."
    return cleaned

def extract_coding_insights(analysis, task_type):
    """Extract coding-specific insights from prompt analysis."""
    if not analysis or len(analysis) < 20 or 'HTTPConnectionPool' in analysis:
        return None
        
    # Clean up the analysis text
    cleaned = analysis.replace("Analysis failed:", "").strip()
    
    # Task-specific extraction patterns
    if task_type == 'complex':
        # For complex tasks, look for refactoring, optimization, and algorithm insights
        coding_patterns = [
            "refactor", "optimize", "algorithm", "pattern", 
            "efficiency", "complex", "structure", "design"
        ]
    elif task_type == 'moderate':
        # For moderate tasks, look for function design and implementation insights
        coding_patterns = [
            "function", "implementation", "parameter", "return",
            "class", "method", "interface", "API"
        ]
    else:  # simple tasks
        # For simple tasks, look for basic syntax and clarity insights
        coding_patterns = [
            "syntax", "clarity", "basic", "simple", "explain",
            "variable", "statement", "expression"
        ]
    
    # Find relevant insights
    insights = []
    sentences = cleaned.split('.')
    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) > 15:
            for pattern in coding_patterns:
                if pattern in sentence.lower():
                    # Clean and format
                    insight = sentence.capitalize()
                    if len(insight) > 120:
                        insight = insight[:120] + "..."
                    insights.append(insight)
                    break  # One match per sentence is enough
    
    return insights if insights else None

def update_roomodes(modelstate_path=".modelstate.json", roomodes_path=".roomodes", settings_path="roo-code-settings.json"):
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
            modelstate = json.load(f)
        
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
        if isinstance(modelstate, dict):
            if "models" in modelstate:
                # Format: {"models": [...]}
                models = modelstate["models"]
            else:
                # Format: {model_id: model_data, ...}
                models = list(modelstate.values())
        else:
            # Assuming it's a list
            models = modelstate

        # Read or initialize .roomodes
        if os.path.exists(roomodes_path):
            print(f"  - Found existing .roomodes file")
            try:
                with open(roomodes_path, "r", encoding="utf-8") as f:
                    roomodes = json.load(f)
                custom_modes = roomodes.get("customModes", [])
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
        existing_modes = {mode["slug"]: mode for mode in custom_modes}
        print(f"  - Processing {len(models)} models...")

        # Always ensure Boomerang Mode exists
        boomerang_slug = "boomerang-mode"
        if boomerang_slug not in existing_modes:
            print(f"  - Adding Boomerang Mode (essential for model orchestration)")
            boomerang_mode = create_boomerang_mode()
            existing_modes[boomerang_slug] = boomerang_mode
        
        # Add/update modes for each model
        for model in models:
            model_id = model.get("model_id", model.get("id", "unknown"))
            print(f"    - Processing model: {model_id}")
            mode_entry = generate_mode_entry(model)
            slug = mode_entry["slug"]
            
            if slug in existing_modes:
                # Preserve important user customizations when updating
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
                    if 'Performance Profile:' not in existing_instr and len(existing_instr) > 100:
                        # Append new performance data to user's custom instructions
                        mode_entry['customInstructions'] = existing_instr + "\n\n" + new_instr
                
                print(f"      - Updating existing mode: {slug} (preserving custom settings)")
            else:
                print(f"      - Creating new mode: {slug}")
            
            existing_modes[slug] = mode_entry

        # Preserve non-model modes but ensure Boomerang Mode is always included
        model_slugs = {generate_mode_entry(m)["slug"] for m in models}
        non_model_modes = [m for m in custom_modes if m["slug"] not in model_slugs and m["slug"] != "boomerang-mode"]
        model_modes = [existing_modes[slug] for slug in sorted(model_slugs)]
        
        # Ensure boomerang mode is first in the list for visibility
        boomerang_mode = existing_modes.get("boomerang-mode")
        final_modes = []
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
        import traceback
        traceback.print_exc()
        return False

def update_roo_code_settings(model_modes, settings_path="roo-code-settings.json"):
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
    model_to_config_id = {}
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
    processed_modes = []
    for mode in model_modes:
        if not isinstance(mode, dict) or "slug" not in mode:
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
            new_config = {
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

def create_boomerang_mode():
    """Create the standard Boomerang Mode entry for task orchestration."""
    return {
        "slug": "boomerang-mode",
        "name": "Boomerang Mode",
        "roleDefinition": "You are Roo, a strategic workflow orchestrator who coordinates complex tasks by delegating them to appropriate specialized modes. You have a comprehensive understanding of each mode's capabilities and limitations, allowing you to effectively break down complex problems into discrete tasks that can be solved by different LM Studio specialists. You excel at matching task requirements with the right model's strengths based on benchmarking data, especially considering context window limitations.",
        "groups": ["read", "edit", "command", "mcp"],
        "source": "global",
        "customInstructions": """Your role is to coordinate complex workflows by delegating tasks to specialized modes from the available LM Studio models. As an orchestrator, you should:

1. When given a complex task, break it down into logical subtasks that can be delegated to appropriate specialized modes based on their benchmarked capabilities.

2. For each subtask, examine the available models in .roomodes and select the most appropriate one based on:
   * Performance Profile scores (simple, moderate, complex, context window)
   * Coding Specialties listed in each model's custom instructions
   * Memory/Context Window limitations - THIS IS CRITICAL
   * Match between task complexity and model capabilities

3. CONTEXT MANAGEMENT (CRITICAL): When delegating tasks, you MUST:
   * Provide the full necessary context to each model, including relevant code excerpts, task history, and requirements
   * For models with low context window scores (<0.5), break context into smaller, focused chunks
   * For models with high context window scores (>0.8), provide comprehensive context
   * Include explicit instructions for the model about how to use the provided context
   * When task involves code files larger than ~500 lines, select only models with high context window scores
   * NEVER assume a model will remember previous interactions or maintain context between subtasks

4. For each subtask, use the `new_task` tool to delegate. Choose the most appropriate mode for the subtask's specific goal and provide comprehensive instructions in the `message` parameter. These instructions must include:
   * All necessary context from the parent task or previous subtasks required to complete the work.
   * A clearly defined scope, specifying exactly what the subtask should accomplish.
   * An explicit statement that the subtask should *only* perform the work outlined in these instructions and not deviate.
   * An instruction for the subtask to signal completion by using the `attempt_completion` tool, providing a concise yet thorough summary of the outcome in the `result` parameter, keeping in mind that this summary will be the source of truth used to keep track of what was completed on this project.
   * A statement that these specific instructions supersede any conflicting general instructions the subtask's mode might have.
   * For models with lower context window scores, break instructions into smaller chunks and prioritize the most important information first.

5. Track and manage the progress of all subtasks. When a subtask is completed, analyze its results and determine the next steps.

6. Help the user understand how the different subtasks fit together in the overall workflow. Provide clear reasoning about why you're delegating specific tasks to specific modes, referencing benchmark scores and capabilities.

7. When all subtasks are completed, synthesize the results and provide a comprehensive overview of what was accomplished.

8. Ask clarifying questions when necessary to better understand how to break down complex tasks effectively.

9. Suggest improvements to the workflow based on the results of completed subtasks.

## Model Selection Guidelines

* For complex coding tasks (algorithms, refactoring): Use models with high complex task scores
* For context-heavy tasks requiring memory: Use models with high context window scores (>0.7)
* For straightforward implementation: Use models with high moderate task scores
* For documentation/explanation: Consider models with appropriate file access levels

## Context Management Strategies

* For models with limited context window ability (<0.5):
  * Focus subtasks on very specific goals
  * Minimize background information
  * Reference previous subtask results by summarizing outcomes, not including full code
  * Break large code files into smaller chunks, focusing on relevant sections
  * Prefer multiple smaller subtasks over fewer large ones
  
* For models with moderate context handling (0.5-0.7):
  * Provide focused context with clear delineation between sections
  * Include abbreviated code snippets rather than full files
  * Use summarized background information
  * Be explicit about what parts of the context are most relevant

* For models with strong context handling (>0.7):
  * Provide comprehensive context
  * Include full code files when relevant
  * Supply detailed background information
  * Allow handling multiple related subtasks together
  * Utilize structured formats for context organization

## LM Studio Context Window Maximization

When delegating tasks to LM Studio models, ensure that:
1. The full context is provided at the beginning of the interaction
2. The most critical information appears early in the context
3. Include explicit instructions to the model on how to use the context
4. For complex tasks with large context requirements, ONLY delegate to models with high context window scores

Use subtasks to maintain clarity. If a request significantly shifts focus or requires a different expertise (mode), consider creating a subtask rather than overloading the current one."""
    }

# If run as a script, perform the update
if __name__ == "__main__":
    update_roomodes()