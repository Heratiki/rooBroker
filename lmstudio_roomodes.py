import json
import os
import re

def slugify(name):
    """Create a slug for the mode from the model name."""
    # Lowercase, replace non-alphanum with hyphens, collapse multiple hyphens, strip
    slug = re.sub(r'[^a-zA-Z0-9]+', '-', name.lower())
    slug = re.sub(r'-+', '-', slug).strip('-')
    return f"{slug}-mode"

def generate_mode_entry(model):
    """Generate a RooCode mode entry from a model dict that's optimized for coding tasks."""
    model_id = model.get('model_id', model.get('id', 'Unknown Model'))
    # Use model_id directly as the name to ensure uniqueness
    model_name = model_id
    
    # Get benchmark scores and improvements
    score_simple = model.get('score_simple', 0.0)
    score_moderate = model.get('score_moderate', 0.0)
    score_complex = model.get('score_complex', 0.0)
    overall_score = (score_simple + score_moderate + score_complex) / 3
    
    # Round scores for cleaner display
    score_simple = round(score_simple, 2)
    score_moderate = round(score_moderate, 2)
    score_complex = round(score_complex, 2)
    overall_score = round(overall_score, 2)
    
    # Get prompt improvements if available
    improvements = model.get('prompt_improvements', {})
    improved_prompts = {}
    coding_strategies = []
    
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
    
    # Customize based on the model's capabilities
    if overall_score > 0.8:
        role_definition = f"{base_role} Using the {model_name} language model, you excel at complex coding tasks, refactoring, and implementing sophisticated solutions."
    elif overall_score > 0.5:
        role_definition = f"{base_role} With the {model_name} language model, you can handle moderately complex programming tasks and provide solid implementation advice."
    else:
        role_definition = f"{base_role} Powered by the {model_name} language model, you focus on providing simpler code snippets, explanations, and guidance on basic programming concepts."

    # Build custom instructions focused on the model's coding capabilities
    instructions = []
    
    # First document the model's performance profile
    instructions.append(f"## {model_name} Performance Profile")
    instructions.append(f"* Simple tasks: {score_simple}")
    instructions.append(f"* Moderate tasks: {score_moderate}")
    instructions.append(f"* Complex tasks: {score_complex}")
    instructions.append("")
    
    # Add specific coding strategies based on benchmark performance
    instructions.append("## Coding Specialties")
    
    if score_complex > 0.7:
        instructions.append("* Code refactoring and optimization")
        instructions.append("* Complex algorithm implementation")
        instructions.append("* Design pattern application")
    if score_moderate > 0.7:
        instructions.append("* Function and class implementation")
        instructions.append("* API design and integration")
    if score_simple > 0.7:
        instructions.append("* Basic script creation")
        instructions.append("* Syntax explanation and error fixing")
    
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
        instructions.append("When using with Boomerang Mode, provide this model with very specific subtasks and clear context about how its work fits into the larger project.")
    elif overall_score > 0.5:
        instructions.append("* Implementation of well-defined components")
        instructions.append("* Writing clearly specified functions and classes")
        instructions.append("* Analyzing and explaining existing code")
        instructions.append("")
        instructions.append("When delegating to this model via Boomerang Mode, define clear boundaries and success criteria for each subtask.")
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

    # Create mode entry according to RooCode spec
    mode_entry = {
        "slug": unique_slug,
        "name": model_name,
        "roleDefinition": role_definition,
        "groups": groups,
        "source": "global",
        "customInstructions": "\n".join(instructions)
    }
    
    # Store minimal benchmark data
    if model.get('last_updated'):
        mode_entry["benchmarkData"] = {
            "scores": {
                "simple": score_simple,
                "moderate": score_moderate,
                "complex": score_complex,
                "overall": overall_score
            },
            "lastUpdated": model.get('last_updated', '')
        }
        
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

def update_roomodes(modelstate_path=".modelstate.json", roomodes_path=".roomodes"):
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

        # Preserve non-model modes (e.g., boomerang-mode)
        model_slugs = {generate_mode_entry(m)["slug"] for m in models}
        non_model_modes = [m for m in custom_modes if m["slug"] not in model_slugs]
        model_modes = [existing_modes[slug] for slug in sorted(model_slugs)]
        print(f"  - Preserving {len(non_model_modes)} non-model modes")
        print(f"  - Adding {len(model_modes)} model modes")
        
        # Maintain order with non-model modes first
        roomodes["customModes"] = non_model_modes + model_modes

        # Write back to .roomodes
        try:
            with open(roomodes_path, "w", encoding="utf-8") as f:
                json.dump(roomodes, f, indent=4, ensure_ascii=False)
            print(f"  - Successfully wrote to {roomodes_path}")
            print(f"  - Total modes in file: {len(roomodes['customModes'])}")
            return True
        except Exception as e:
            print(f"  - Error writing to {roomodes_path}: {str(e)}")
            raise
            
    except Exception as e:
        print(f"Error updating roomodes: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

# If run as a script, perform the update
if __name__ == "__main__":
    update_roomodes()