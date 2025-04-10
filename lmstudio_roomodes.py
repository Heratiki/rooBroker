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
    """Generate a RooCode mode entry from a model dict."""
    model_name = model.get('name', model.get('id', 'Unknown Model'))
    model_id = model.get('model_id', model.get('id', 'unknown'))
    
    # Get benchmark scores and improvements
    score_simple = model.get('score_simple', 0.0)
    score_moderate = model.get('score_moderate', 0.0)
    score_complex = model.get('score_complex', 0.0)
    overall_score = (score_simple + score_moderate + score_complex) / 3
    
    # Get prompt improvements if available
    improvements = model.get('prompt_improvements', {})
    improved_prompts = {}
    for task_name, imp in improvements.items():
        if imp.get('improved_prompt'):
            improved_prompts[task_name] = {
                'original': imp.get('original_prompt', ''),
                'improved': imp.get('improved_prompt', ''),
                'analysis': imp.get('analysis', '')
            }

    # Build custom instructions based on model's performance
    instructions = [
        f"Use this mode for tasks within {model_name}'s capabilities.",
        f"Model ID: {model_id}",
        f"Overall Score: {overall_score:.2f}",
        "",
        "Performance Profile:",
        f"- Simple tasks: {score_simple:.2f}",
        f"- Moderate tasks: {score_moderate:.2f}",
        f"- Complex tasks: {score_complex:.2f}",
    ]

    # Add prompt improvement strategies if available
    if improved_prompts:
        instructions.append("")
        instructions.append("Prompt Strategies:")
        for task, data in improved_prompts.items():
            if data.get('analysis'):
                instructions.append(f"- {task}: {data['analysis'][:200]}...")

    instructions.append("")
    instructions.append("Note: Update .modelstate.json with task results for continuous improvement.")

    return {
        "slug": slugify(model_name),
        "name": model_name,
        "groups": ["read", "edit", "command", "mcp"],
        "source": "global",
        "customInstructions": "\n".join(instructions),
        "benchmarkData": {
            "scores": {
                "simple": score_simple,
                "moderate": score_moderate,
                "complex": score_complex,
                "overall": overall_score
            },
            "promptImprovements": improved_prompts,
            "lastUpdated": model.get('last_updated', '')
        }
    }

def update_roomodes(modelstate_path=".modelstate.json", roomodes_path=".roomodes"):
    """Update .roomodes with enhanced model information including benchmark data."""
    # Read modelstate
    if not os.path.exists(modelstate_path):
        raise FileNotFoundError(f"{modelstate_path} not found")
    with open(modelstate_path, "r", encoding="utf-8") as f:
        modelstate = json.load(f)
    
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
        with open(roomodes_path, "r", encoding="utf-8") as f:
            roomodes = json.load(f)
        custom_modes = roomodes.get("customModes", [])
    else:
        custom_modes = []
        roomodes = {"customModes": custom_modes}

    # Build a dict of existing modes by slug
    existing_modes = {mode["slug"]: mode for mode in custom_modes}

    # Add/update modes for each model
    for model in models:
        mode_entry = generate_mode_entry(model)
        slug = mode_entry["slug"]
        if slug in existing_modes:
            # Preserve any existing custom fields while updating
            existing = existing_modes[slug]
            for key in ['groups', 'source']:
                if key in existing:
                    mode_entry[key] = existing[key]
        existing_modes[slug] = mode_entry

    # Preserve non-model modes (e.g., boomerang-mode)
    model_slugs = {generate_mode_entry(m)["slug"] for m in models}
    non_model_modes = [m for m in custom_modes if m["slug"] not in model_slugs]
    model_modes = [existing_modes[slug] for slug in sorted(model_slugs)]
    roomodes["customModes"] = non_model_modes + model_modes

    # Write back to .roomodes
    with open(roomodes_path, "w", encoding="utf-8") as f:
        json.dump(roomodes, f, indent=4, ensure_ascii=False)

# If run as a script, perform the update
if __name__ == "__main__":
    update_roomodes()