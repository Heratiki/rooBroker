# import json
# import os
from typing import Dict, List, Tuple, Any, Union, cast

from .utils import slugify


def generate_mode_entry(model: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a RooCode mode entry from a model dict that's optimized for coding tasks."""
    model_id: str = cast(str, model.get("model_id", model.get("id", "Unknown Model")))
    model_name: str = model_id
    context_window: int = cast(int, model.get("context_window", 0))

    # Get benchmark scores and improvements
    score_simple: float = cast(float, model.get("score_simple", 0.0))
    score_moderate: float = cast(float, model.get("score_moderate", 0.0))
    score_complex: float = cast(float, model.get("score_complex", 0.0))
    score_context_window: float = cast(float, model.get("score_context_window", 0.0))

    # Get BIG-BENCH scores if available
    bigbench_scores: Dict[str, Any] = cast(
        Dict[str, Any], model.get("bigbench_scores", {})
    )
    bigbench_overall: float = cast(float, bigbench_scores.get("overall", 0.0))
    bigbench_raw: float = cast(
        float, bigbench_scores.get("raw_overall", bigbench_overall)
    )
    bigbench_tasks: List[Dict[str, Any]] = cast(
        List[Dict[str, Any]], bigbench_scores.get("tasks", [])
    )

    # Calculate overall score with heavy BIG-BENCH weighting (60% BIG-BENCH, 40% standard)
    base_score = (
        score_simple + score_moderate + score_complex + score_context_window
    ) / 4
    overall_score = (
        (base_score * 0.4 + bigbench_overall * 0.6)
        if bigbench_overall > 0
        else base_score
    )

    # Extract complexity-specific capabilities
    complexity_scores: Dict[str, List[Dict[str, Any]]] = {
        "logical_reasoning": [],
        "algorithmic_thinking": [],
        "abstract_reasoning": [],
        "mathematics": [],
        "code_generation": [],
        "problem_solving": [],
        "other": [],
    }

    # Group task scores by complexity category
    for task in bigbench_tasks:
        category = task.get("complexity_category", "other")
        if category in complexity_scores:
            complexity_scores[category].append(
                {
                    "name": task.get("task", ""),
                    "score": task.get("weighted_score", task.get("raw_score", 0.0)),
                    "metrics": task.get("metrics", {}),
                }
            )

    # Calculate average scores per category
    category_averages: Dict[str, float] = {
        cat: sum(t["score"] for t in tasks) / len(tasks) if tasks else 0.0
        for cat, tasks in complexity_scores.items()
    }

    # Create a coding-focused role definition modeled after RooCode's default
    base_role = "You are Roo, a highly skilled software engineer with extensive knowledge in many programming languages, frameworks, design patterns, and best practices."

    # Customize based heavily on BIG-BENCH-HARD performance
    if bigbench_overall > 0.8:
        role_addition: str = "excel at complex reasoning tasks, particularly in"
        top_categories = sorted(
            [(cat, score) for cat, score in category_averages.items() if score > 0.7],
            key=lambda x: x[1],
            reverse=True,
        )[:3]
        if top_categories:
            top_categories: List[Tuple[str, float]] = top_categories
            role_addition += " " + ", ".join(
                cat.replace("_", " ") for cat, _ in top_categories
            )
    elif bigbench_overall > 0.6:
        role_addition: str = "handle moderately complex tasks with good performance in"
        top_categories = sorted(
            [(cat, score) for cat, score in category_averages.items() if score > 0.5],
            key=lambda x: x[1],
            reverse=True,
        )[:2]
        if top_categories:
            top_categories: List[Tuple[str, float]] = top_categories
            role_addition += " " + " and ".join(
                cat.replace("_", " ") for cat, _ in top_categories
            )
    else:
        role_addition: str = "focus on well-defined tasks with clear requirements"

    role_definition = f"{base_role} Using the {model_name} language model with a {context_window}-token context window, you {role_addition}."

    # Build custom instructions focusing heavily on reasoning capabilities
    instructions: List[str] = []

    # Document the model's complete performance profile
    instructions.append(f"## {model_name} Performance Profile")
    instructions.append("### BIG-BENCH-HARD Scores (Primary Capabilities)")
    for category, avg_score in category_averages.items():
        if avg_score > 0:
            instructions.append(
                f"* {category.replace('_', ' ').title()}: {avg_score:.2f}"
            )
    instructions.append("")
    instructions.append("### Standard Benchmark Scores (Secondary Capabilities)")
    instructions.append(f"* Simple tasks: {score_simple:.2f}")
    instructions.append(f"* Moderate tasks: {score_moderate:.2f}")
    instructions.append(f"* Complex tasks: {score_complex:.2f}")
    instructions.append(f"* Context window: {score_context_window:.2f}")
    instructions.append("")

    # Add specific task delegation guidance based on complexity scores
    instructions.append("## Task Delegation Priorities")
    instructions.append("This model should be preferentially used for:")

    # Sort categories by score and add specific task types
    sorted_categories: List[Tuple[str, float]] = sorted(
        [(cat, score) for cat, score in category_averages.items()],
        key=lambda x: x[1],
        reverse=True,
    )

    for category, score in sorted_categories:
        if score > 0.7:
            priority = "High Priority"
        elif score > 0.5:
            priority = "Medium Priority"
        elif score > 0.3:
            priority = "Low Priority"
        else:
            continue

        cat_name = category.replace("_", " ").title()
        instructions.append(f"\n### {cat_name} Tasks ({priority})")

        # Add specific task types based on category
        if category == "logical_reasoning":
            instructions.append("* Complex conditional logic implementation")
            instructions.append("* Decision tree development")
            instructions.append("* Logic optimization tasks")
        elif category == "algorithmic_thinking":
            instructions.append("* Algorithm design and optimization")
            instructions.append("* Data structure implementation")
            instructions.append("* Performance optimization")
        elif category == "abstract_reasoning":
            instructions.append("* System architecture design")
            instructions.append("* Design pattern application")
            instructions.append("* Interface design")
        elif category == "mathematics":
            instructions.append("* Numerical computation")
            instructions.append("* Mathematical algorithm implementation")
            instructions.append("* Formula translation to code")
        elif category == "code_generation":
            instructions.append("* Complete function implementation")
            instructions.append("* Class structure generation")
            instructions.append("* API endpoint development")
        elif category == "problem_solving":
            instructions.append("* Bug fixing and debugging")
            instructions.append("* Code refactoring")
            instructions.append("* Feature implementation")

    # Add context window management guidance
    if score_context_window > 0.8:
        instructions.append("\n## Context Management")
        instructions.append(
            "* Maximum context window: " + str(context_window) + " tokens"
        )
        instructions.append("* Excellent at handling large, complex tasks")
        instructions.append("* Can process multiple files simultaneously")
        instructions.append("* Maintains coherent understanding across large codebases")
    elif score_context_window > 0.4:
        instructions.append("\n## Context Management")
        instructions.append(
            "* Maximum context window: " + str(context_window) + " tokens"
        )
        instructions.append("* Best with focused, well-scoped tasks")
        instructions.append("* Process one file at a time")
        instructions.append("* May need context refreshing for complex tasks")
    else:
        instructions.append("\n## Context Management")
        instructions.append(
            "* Maximum context window: " + str(context_window) + " tokens"
        )
        instructions.append("* Requires very focused, minimal-context tasks")
        instructions.append("* Process small code segments")
        instructions.append("* Frequent context refreshing needed")

    # Add learned prompt improvements if available
    if model.get("prompt_improvements"):
        instructions.append("\n## Effective Prompting Strategies")
        for improvement in model.get("prompt_improvements", {}).values():
            if "analysis" in improvement:
                analysis = improvement["analysis"]
                if len(analysis) > 20 and "error" not in analysis.lower():
                    key_point = analysis.split(".")[0].strip()
                    if len(key_point) > 10:
                        instructions.append(f"* {key_point}")

    # Define appropriate groups based heavily on BIG-BENCH-HARD performance
    groups: List[Union[str, List[Any]]] = ["read"]

    # Add edit capability based on weighted scores
    if bigbench_overall > 0.7 or (
        bigbench_overall > 0.5 and category_averages.get("code_generation", 0) > 0.6
    ):
        # Full code editing capabilities for high-performing models
        edit_restrictions = {
            "fileRegex": "\\.(py|js|ts|jsx|tsx|java|cpp|c|h|hpp|rb|go|rs|php|html|css|json|md)$",
            "description": "All code and documentation files",
        }
        groups.append(["edit", edit_restrictions])
    elif bigbench_overall > 0.5 or score_complex > 0.7:
        # Limited code editing for moderately capable models
        edit_restrictions = {
            "fileRegex": "\\.(py|js|ts|md|txt)$",
            "description": "Python, JavaScript, and documentation files",
        }
        groups.append(["edit", edit_restrictions])
    else:
        # Documentation-only editing for lower-performing models
        edit_restrictions = {
            "fileRegex": "\\.(md|txt)$",
            "description": "Documentation files only",
        }
        groups.append(["edit", edit_restrictions])

    # Add command capability for models with strong reasoning abilities
    if bigbench_overall > 0.7 or category_averages.get("problem_solving", 0) > 0.7:
        groups.append("command")

    # Add MCP capability for all models
    groups.append("mcp")

    # Create unique slug
    unique_slug: str = slugify(model_id)

    # Create mode entry
    mode_entry: Dict[str, Any] = {
        "slug": unique_slug,
        "name": model_name,
        "roleDefinition": role_definition,
        "groups": groups,
        "source": "global",
        "customInstructions": "\n".join(instructions),
        "contextWindow": context_window,
        "maxResponseTokens": (
            min(2000, int(context_window * 0.25)) if context_window else 2000
        ),
        "benchmarkData": {
            "scores": {
                "bigbench": {
                    "overall": bigbench_overall,
                    "raw": bigbench_raw,
                    "categories": category_averages,
                },
                "standard": {
                    "simple": score_simple,
                    "moderate": score_moderate,
                    "complex": score_complex,
                    "context_window": score_context_window,
                },
                "overall": overall_score,
            },
            "lastUpdated": model.get("last_updated", ""),
        },
    }

    return mode_entry


def create_boomerang_mode() -> Dict[str, Any]:
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

Use subtasks to maintain clarity. If a request significantly shifts focus or requires a different expertise (mode), consider creating a subtask rather than overloading the current one.""",
    }
