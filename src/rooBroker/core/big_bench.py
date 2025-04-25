"""Core BIG-BENCH-HARD benchmarking functionality.

This module provides functionality for running BIG-BENCH-HARD benchmarks
against language models using the ModelProviderClient interface.
"""

from typing import Any, Dict, List, Optional, Tuple
import json
import time
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn, TimeRemainingColumn

from rooBroker.interfaces.base import ModelProviderClient
from rooBroker.roo_types.discovery import DiscoveredModel, ChatMessage

# BIG-BENCH-HARD task definitions
# These are simplified versions of the tasks from the original BIG-BENCH-HARD benchmark
BIGBENCH_TASKS = [
    # Logical reasoning tasks
    {
        "category": "logical",
        "name": "logical_deduction",
        "description": "Solve logical deduction puzzles",
        "examples": [
            {
                "input": "There are five houses in a row, each with a different color. The owners of these houses all have a different nationality, drink a different drink, smoke a different brand of cigarettes, and keep a different pet. Given the following clues, determine who owns the fish.\n\n1. The British man lives in the red house.\n2. The Swedish man has dogs.\n3. The Danish man drinks tea.\n4. The green house is on the left of the white house.\n5. The owner of the green house drinks coffee.\n6. The person who smokes Pall Mall keeps birds.\n7. The owner of the yellow house smokes Dunhill.\n8. The man in the center house drinks milk.\n9. The Norwegian lives in the first house.\n10. The man who smokes Blends lives next to the one who keeps cats.\n11. The man who keeps horses lives next to the one who smokes Dunhill.\n12. The man who smokes Blue Master drinks beer.\n13. The German smokes Prince.\n14. The Norwegian lives next to the blue house.\n15. The man who smokes Blends has a neighbor who drinks water.\n\nWho owns the fish?",
                "expected": "The German owns the fish."
            },
        ]
    },
    {
        "category": "logical",
        "name": "boolean_expressions",
        "description": "Evaluate boolean expressions",
        "examples": [
            {
                "input": "Evaluate the following boolean expression:\nNOT (True AND (False OR (NOT True)))",
                "expected": "True"
            },
        ]
    },
    
    # Algorithmic tasks
    {
        "category": "algorithmic",
        "name": "sorting",
        "description": "Sort lists of numbers or strings",
        "examples": [
            {
                "input": "Sort the following list in ascending order: [5, 2, 9, 1, 7, 3]",
                "expected": "[1, 2, 3, 5, 7, 9]"
            },
        ]
    },
    {
        "category": "algorithmic",
        "name": "algorithms",
        "description": "Implement simple algorithms",
        "examples": [
            {
                "input": "Describe the steps to find the greatest common divisor (GCD) of two numbers using Euclidean algorithm.",
                "expected": "1. Let a and b be the two numbers.\n2. If b = 0, return a as the GCD.\n3. Otherwise, calculate a % b (a modulo b).\n4. Replace a with b and b with the remainder calculated in step 3.\n5. Repeat steps 2-4 until b becomes 0."
            },
        ]
    },
    
    # Knowledge tasks
    {
        "category": "knowledge",
        "name": "general_knowledge",
        "description": "Answer general knowledge questions",
        "examples": [
            {
                "input": "What is the capital of France?",
                "expected": "Paris"
            },
        ]
    }
]


def _score_response(response: str, expected: str) -> float:
    """Score a model response against the expected answer.
    
    This is a simple scoring function that computes the approximate similarity
    between the response and expected answer. In a real implementation, this
    would use more sophisticated methods like semantic similarity.
    
    Args:
        response: The model's response text.
        expected: The expected answer text.
        
    Returns:
        A score between 0.0 and 1.0, where 1.0 is a perfect match.
    """
    # Simple implementation based on string overlap
    # In a real implementation, this would use more sophisticated methods
    response = response.lower().strip()
    expected = expected.lower().strip()
    
    # Check for exact match
    if response == expected:
        return 1.0
    
    # Check for partial match - if expected is entirely contained in response
    if expected in response:
        return 0.8
    
    # Count word overlap
    response_words = set(response.split())
    expected_words = set(expected.split())
    
    if not expected_words:
        return 0.0
    
    overlap = response_words.intersection(expected_words)
    score = len(overlap) / len(expected_words)
    
    return max(0.0, min(0.7, score))  # Cap partial matches at 0.7


def run_bigbench_benchmarks(
    client: ModelProviderClient,
    models: List[Dict[str, Any]],
    existing_results: List[Dict[str, Any]],
    console: Optional[Console] = None
) -> List[Dict[str, Any]]:
    """Run BIG-BENCH-HARD benchmarks for the specified models.
    
    Args:
        client: The model provider client to use for completions.
        models: The list of models to benchmark.
        existing_results: Existing benchmark results to merge with.
        console: Optional Console instance for rich output formatting.
        
    Returns:
        Updated list of benchmark results with BIG-BENCH-HARD scores added.
    """
    if console is None:
        console = Console()
        
    console.print("\n[bold cyan]Starting BIG-BENCH-HARD benchmarks[/bold cyan]")
    console.print("[yellow]Note: These benchmarks test complex reasoning tasks and may take longer to complete.[/yellow]")

    # Create a map of existing results for easy lookup and update
    results_map = {r.get("model_id"): r for r in existing_results}
    
    # Setup main progress tracker for all models
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console
    ) as progress:
        overall_task = progress.add_task(
            f"[cyan]Running BIG-BENCH-HARD for {len(models)} models...", 
            total=len(models)
        )
        
        # Process each model
        for model_index, model in enumerate(models):
            model_id = model.get("id")
            if not model_id:
                console.print("[yellow]Skipping model with no ID for BIG-BENCH-HARD.[/yellow]")
                progress.update(overall_task, advance=1)
                continue

            # Update progress description to show current model
            progress.update(
                overall_task, 
                description=f"[cyan]BIG-BENCH-HARD [{model_index+1}/{len(models)}]: {model_id}"
            )
            
            try:
                # Run the benchmark
                console.print(f"\n[bold cyan]═════ BIG-BENCH-HARD: {model_id} ═════[/bold cyan]")
                bb_results = _run_single_model_benchmarks(client, model, progress, console)

                # Handle results
                if model_id in results_map and bb_results:
                    results_map[model_id].update(bb_results)
                    console.print(f"[green]✓ Results merged successfully for {model_id}[/green]")
                elif model_id in results_map:
                    console.print(f"[yellow]⚠ No valid results returned for {model_id}[/yellow]")
                    results_map[model_id]["bigbench_status"] = "No results returned"
                else:
                    console.print(f"[yellow]⚠ No standard benchmark result found to merge BBH results into.[/yellow]")
            except Exception as e:
                console.print(f"[bold red]✗ Error running BIG-BENCH-HARD for {model_id}: {e}[/bold red]")
                if model_id in results_map:
                    results_map[model_id]["bigbench_error"] = str(e)
            
            # Update overall progress
            progress.update(overall_task, advance=1)
    
    # Final summary
    bb_models_count = len([r for r in existing_results if "bigbench_scores" in r])
    if bb_models_count > 0:
        console.print(f"\n[bold green]✓ BIG-BENCH-HARD completed for {bb_models_count} of {len(models)} models[/bold green]")
    else:
        console.print("\n[yellow]⚠ No models completed BIG-BENCH-HARD successfully[/yellow]")

    # The existing_results list has been modified in-place through the map
    return existing_results


def _run_single_model_benchmarks(
    client: ModelProviderClient,
    model: Dict[str, Any],
    progress: Progress,
    console: Console
) -> Dict[str, Any]:
    """Run BIG-BENCH-HARD benchmarks for a single model.
    
    Args:
        client: The model provider client to use for completions.
        model: The model information dictionary.
        progress: The progress tracker for UI updates.
        console: Console instance for rich output formatting.
        
    Returns:
        Dictionary with BIG-BENCH-HARD benchmark results.
    """
    model_id = model.get("id")
    if not model_id:
        return {}
    
    # Dictionary to store category scores
    category_scores: Dict[str, List[float]] = {}
    
    # Dictionary to store individual task results
    task_results = []
    
    # Add a task for this model's progress
    model_task = progress.add_task(
        f"[cyan]Tasks for {model_id}...",
        total=len(BIGBENCH_TASKS)
    )
    
    # Run each task
    for task in BIGBENCH_TASKS:
        task_name = task.get("name", "unnamed_task")
        category = task.get("category", "uncategorized")
        
        progress.update(
            model_task,
            description=f"[cyan]Task: {task_name}"
        )
        
        console.print(f"  [blue]Running task: {task_name} ({category})[/blue]")
        
        # Initialize category if not present
        if category not in category_scores:
            category_scores[category] = []
        
        # Process each example in the task
        example_scores = []
        examples = task.get("examples", [])
        
        for example_idx, example in enumerate(examples):
            input_text = example.get("input", "")
            expected = example.get("expected", "")
            
            console.print(f"    Example {example_idx+1}/{len(examples)}: ", end="")
            
            try:
                # Create chat message from input
                messages = [ChatMessage(role="user", content=input_text)]
                
                # Get model response
                start_time = time.time()
                response = client.run_completion(
                    messages=messages,
                    model_id=model_id,
                    temperature=0.2,  # Low temperature for more deterministic responses
                    max_tokens=1024
                )
                end_time = time.time()
                
                # Score the response
                score = _score_response(response, expected)
                example_scores.append(score)
                
                # Record the result
                example_result = {
                    "input": input_text,
                    "expected": expected,
                    "response": response,
                    "score": score,
                    "latency": end_time - start_time
                }
                
                console.print(f"[{'green' if score >= 0.7 else 'yellow' if score >= 0.3 else 'red'}]Score: {score:.2f}[/{'green' if score >= 0.7 else 'yellow' if score >= 0.3 else 'red'}]")
                
            except Exception as e:
                console.print(f"[red]Error: {str(e)}[/red]")
                example_result = {
                    "input": input_text,
                    "expected": expected,
                    "error": str(e)
                }
            
            task_results.append({
                "task": task_name,
                "category": category,
                "example_idx": example_idx,
                "result": example_result
            })
        
        # Calculate average score for this task
        if example_scores:
            task_avg_score = sum(example_scores) / len(example_scores)
            category_scores[category].append(task_avg_score)
            console.print(f"  [{'green' if task_avg_score >= 0.7 else 'yellow' if task_avg_score >= 0.3 else 'red'}]Task average: {task_avg_score:.2f}[/{'green' if task_avg_score >= 0.7 else 'yellow' if task_avg_score >= 0.3 else 'red'}]")
        else:
            console.print(f"  [red]No valid examples completed for this task[/red]")
        
        # Update progress
        progress.update(model_task, advance=1)
    
    # Complete the task
    progress.update(model_task, completed=True)
    
    # Calculate category averages
    category_averages = {}
    all_scores = []
    
    for category, scores in category_scores.items():
        if scores:
            category_avg = sum(scores) / len(scores)
            category_averages[category] = category_avg
            all_scores.extend(scores)
    
    # Calculate overall average
    overall_avg = sum(all_scores) / len(all_scores) if all_scores else 0.0
    
    # Prepare the final result
    bigbench_scores = {
        "overall": overall_avg,
        "categories": category_averages
    }
    
    # Timestamp the results
    timestamp = datetime.now().isoformat()
    
    return {
        "bigbench_scores": bigbench_scores,
        "bigbench_details": task_results,
        "bigbench_timestamp": timestamp,
        "bigbench_status": "completed"
    }
