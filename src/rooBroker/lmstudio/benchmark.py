"""
Benchmarking LM Studio models with Rich UI and adaptive prompting.

DEPRECATED: This module is deprecated and will be removed in a future version.
The standard benchmarking functionality has been moved to rooBroker.core.benchmarking.
Use that module instead, which provides a provider-agnostic implementation using
the ModelProviderClient interface.

This module is kept temporarily for backward compatibility during the refactoring
process and will be removed once all dependencies have been updated to use the
new core implementation.
"""
from typing import List, Dict, Any, cast, Optional
from roo_types.models import ModelState
import time
from datetime import datetime, timezone
import threading
import sys

# Local relative imports to resolve missing module errors
from .client import call_lmstudio_with_max_context
from .analysis import analyze_response, improve_prompt
from .timeout import get_model_timeout
from .modelstate import update_modelstate_json
from .config import console, rich_available, Prompt, Progress, TextColumn, BarColumn, TimeElapsedColumn, TimeRemainingColumn, SpinnerColumn, Live, Layout, Table, Text, box, CHAT_COMPLETIONS_ENDPOINT
from rich.console import Console  # import class for fallback
from .promptwizard import PromptWizard

# Define benchmark metadata types
TASK_TYPES = {
    "statement": "Single line or statement-level code generation",
    "function": "Complete function implementation",
    "class": "Full class implementation",
    "algorithm": "Algorithm or data structure implementation",
    "context": "Context window testing"
}

DIFFICULTY_LEVELS = {
    "basic": "Entry level tasks requiring basic programming knowledge",
    "intermediate": "Tasks requiring good programming practices",
    "advanced": "Complex tasks requiring expert knowledge"
}

# Update benchmarks with metadata
benchmarks: List[Dict[str, Any]] = [
    # Statement level tasks
    {"name": "simple_statement", 
     "type": "statement",
     "difficulty": "basic",
     "prompt": "Write a Python statement to swap two variables x and y without using a temporary variable.", 
     "system_prompt": "You are a Python expert. Provide a single line solution.",
     "expected": "x, y = y, x",
     "test_cases": [
         {"input": {"x": 5, "y": 10}, "expected": {"x": 10, "y": 5}},
         {"input": {"x": -1, "y": 1}, "expected": {"x": 1, "y": -1}},
         {"input": {"x": 0, "y": 0}, "expected": {"x": 0, "y": 0}}
     ],
     "metrics": {
         "conciseness": True,  # Should be a single line
         "readability": True   # Should be easily understandable
     },
     "temperature": 0.1},

    # Function level tasks
    {"name": "moderate",
     "type": "function",
     "difficulty": "intermediate",
     "prompt": "Write a Python function that returns the square of a number.",
     "system_prompt": "You are a Python programmer. Write clean, efficient code.",
     "expected": "def square(n):\n    return n * n",
     "test_cases": [
         {"input": {"n": 5}, "expected": 25},
         {"input": {"n": -2}, "expected": 4},
         {"input": {"n": 0}, "expected": 0},
         {"input": {"n": 10}, "expected": 100}
     ],
     "metrics": {
         "documentation": True,  # Should have docstring
         "type_hints": True,    # Should use type hints
         "error_handling": False  # Not required for this task
     },
     "temperature": 0.2},

    # Class level tasks
    {"name": "class_implementation",
     "type": "class",
     "difficulty": "advanced",
     "prompt": "Create a Stack class implementing push, pop, and isEmpty methods using a list.",
     "system_prompt": "You are a Python expert. Implement a complete class with proper error handling.",
     "expected": "class Stack:\n    def __init__(self):\n        self.items = []\n    \n    def push(self, item):\n        self.items.append(item)\n    \n    def pop(self):\n        if not self.isEmpty():\n            return self.items.pop()\n        raise IndexError('pop from empty stack')\n    \n    def isEmpty(self):\n        return len(self.items) == 0",
     "test_cases": [
         {"sequence": ["push(1)", "push(2)", "pop()"], "expected": 2},
         {"sequence": ["isEmpty()"], "expected": True},
         {"sequence": ["push(1)", "isEmpty()"], "expected": False}
     ],
     "metrics": {
         "documentation": True,
         "error_handling": True,
         "encapsulation": True
     },
     "temperature": 0.2},

    # Algorithm tasks
    {"name": "complex",
     "type": "algorithm",
     "difficulty": "advanced",
     "prompt": "Refactor this code to use a list comprehension:\nresult=[]\nfor x in range(10):\n    if x%2==0: result.append(x*x)",
     "system_prompt": "You are a Python expert. Provide the most concise, readable solution.",
     "expected": "[x*x for x in range(10) if x%2==0]",
     "test_cases": [
         {"input": {}, "expected": [0, 4, 16, 36, 64]},
         {"verification": "isinstance(eval(response), list)"}
     ],
     "metrics": {
         "conciseness": True,
         "readability": True,
         "performance": True
     },
     "temperature": 0.2},

    # Context window testing
    {"name": "context_window",
     "type": "context",
     "difficulty": "basic",
     "prompt": "".join([f"Para {i} number={i*10+7}.\n" for i in range(1,21)]) + "Q: number in para 7?",
     "system_prompt": "You are a helpful assistant. Answer accurately.",
     "expected": "77",
     "test_cases": [{"input": {}, "expected": "77"}],
     "metrics": {
         "context_retention": True
     },
     "temperature": 0.1}
]


def ask_continue_with_timeout(timeout_seconds: int = 15) -> bool:
    """Ask user to continue with timeout defaulting to True after timeout."""
    user_choice: List[bool] = [True]
    expired: List[bool] = [False]

    def read_input() -> None:
        if console:
            resp = Prompt.ask(f"Continue? [Y/n] (timeout {timeout_seconds}s)", default="y").lower()
        else:
            resp = input(f"Continue? [Y/n] (timeout {timeout_seconds}s): ").lower()
        user_choice[0] = (resp != 'n')
        expired[0] = True

    def countdown() -> None:
        for sec in range(timeout_seconds, 0, -1):
            if expired[0]:
                return
            sys.stdout.write(f"\rContinuing in {sec}s... ")
            sys.stdout.flush()
            time.sleep(1)
        expired[0] = True

    t_input = threading.Thread(target=read_input, daemon=True)
    t_timer = threading.Thread(target=countdown, daemon=True)
    t_timer.start(); t_input.start()
    t_input.join(timeout_seconds)
    return user_choice[0]


def benchmark_lmstudio_models(
    models: List[Dict[str, Any]],
    max_retries: int = 2,
    num_samples: int = 20,  # Number of samples to generate per task for pass@k
    analyze_scenarios: bool = True  # Whether to perform scenario analysis
) -> Dict[str, Any]:
    """Run comprehensive benchmarks on LM Studio models with enhanced metrics and scenario analysis."""
    local_console = console if console is not None else Console()
    
    # Run the benchmarks
    results: List[Dict[str, Any]] = []
    all_ids = [m["id"] for m in models]
    
    # Setup display
    total_tasks = len(models) * len(benchmarks)
    completed_tasks = 0
    
    layout = Layout()
    header = Text(f"Progress: {completed_tasks}/{total_tasks} tasks", style="bold magenta")
    
    # Enhanced results table
    table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold")
    table.add_column("Model ID", style="cyan", no_wrap=True)
    table.add_column("Task", style="green")
    table.add_column("TPR", style="yellow")  # Test Pass Rate
    table.add_column("pass@1", style="blue")
    table.add_column("pass@10", style="blue")
    table.add_column("Status", style="white")
    
    layout.split(
        Layout(header, name="header", ratio=1),
        Layout(table, name="main", ratio=4)
    )
    
    with Live(layout, console=local_console, refresh_per_second=4) as live:
        for idx, model in enumerate(models):
            model_id: str = model["id"]
            timeout_sec = get_model_timeout(model)
            
            model_result: Dict[str, Any] = {
                "model_id": model_id,
                "context_window": model.get("context_window", None),
                "failures": 0,
                "last_updated": datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
                "timeout_used": timeout_sec,
                "task_results": []
            }

            for bench in benchmarks:
                try:
                    local_console.print(f"[cyan]Running '{bench['name']}' on {model_id}[/cyan]")
                    
                    # Collect samples for pass@k metric
                    successful_samples = 0
                    all_responses = []
                    
                    for sample_idx in range(num_samples):
                        try:
                            # Generate response
                            response = call_lmstudio_with_max_context(
                                model_id,
                                [
                                    {"role": "system", "content": bench["system_prompt"]},
                                    {"role": "user", "content": bench["prompt"]}
                                ],
                                timeout=timeout_sec,
                                temperature=bench["temperature"],
                                max_tokens=500
                            )
                            
                            if response and isinstance(response, dict):
                                text = response["choices"][0]["message"]["content"].strip()
                                # Evaluate the response
                                eval_result = evaluate_response(text, bench)
                                all_responses.append(eval_result)
                                
                                if eval_result["pass_all"]:
                                    successful_samples += 1
                                    
                        except Exception as e:
                            local_console.print(f"[red]Sample {sample_idx} error: {str(e)}[/red]")
                    
                    # Calculate metrics
                    tpr = sum(r["test_pass_rate"] for r in all_responses) / len(all_responses) if all_responses else 0
                    pass_at_1 = calculate_pass_at_k(len(all_responses), successful_samples, 1)
                    pass_at_10 = calculate_pass_at_k(len(all_responses), successful_samples, 10)
                    
                    # Store results
                    task_result = {
                        "task_name": bench["name"],
                        "samples": len(all_responses),
                        "successful_samples": successful_samples,
                        "test_pass_rate": tpr,
                        "pass@1": pass_at_1,
                        "pass@10": pass_at_10
                    }
                    model_result["task_results"].append(task_result)
                    
                    # Update display
                    table.add_row(
                        model_id,
                        bench["name"],
                        f"{tpr:.2f}",
                        f"{pass_at_1:.2f}",
                        f"{pass_at_10:.2f}",
                        "✓" if successful_samples > 0 else "✗"
                    )
                    
                    completed_tasks += 1
                    layout["header"].update(Text(f"Progress: {completed_tasks}/{total_tasks} tasks", 
                                               style="bold magenta"))
                    live.refresh()
                    
                except Exception as e:
                    local_console.print(f"[red]Error in benchmark '{bench['name']}': {str(e)}[/red]")
                    model_result["failures"] += 1
                    completed_tasks += 1
            
            # Aggregate and store final results
            final_metrics = aggregate_benchmark_results(model_result)
            model_result["aggregated_metrics"] = final_metrics
            results.append(model_result)
            
            # Update model state
            update_modelstate_json(cast(List[ModelState], [model_result]))
            
            if idx < len(models)-1 and not ask_continue_with_timeout(5):
                break
    
    # After all benchmarks complete, perform scenario analysis if requested
    if analyze_scenarios:
        analyses = {
            "by_difficulty": analyze_by_scenario(results, "difficulty"),
            "by_task_type": analyze_by_scenario(results, "task_type"),
            "by_metrics": analyze_by_scenario(results, "metrics")
        }
        
        # Print scenario analyses
        local_console.print("\n[bold cyan]Scenario-Based Analysis[/bold cyan]")
        for scenario, analysis in analyses.items():
            print_scenario_analysis(analysis, scenario.replace("by_", ""), local_console)
        
        # Include analyses in results
        return {
            "raw_results": results,
            "scenario_analyses": analyses
        }
    
    return {"raw_results": results}


def calculate_test_pass_rate(test_results: List[bool]) -> float:
    """Calculate the test pass rate (TPR) metric."""
    if not test_results:
        return 0.0
    return sum(1 for result in test_results if result) / len(test_results)

def evaluate_response(response: str, bench: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate a model response against test cases with enhanced metrics."""
    results = {
        "pass_all": False,
        "test_results": [],
        "test_pass_rate": 0.0,
        "error": None
    }
    
    try:
        # If there are test cases, run them
        if "test_cases" in bench:
            test_results = []
            
            # Create a safe execution environment
            local_env = {}
            try:
                # Execute the generated code in isolated environment
                exec(response, {"__builtins__": __builtins__}, local_env)
                
                for test_case in bench["test_cases"]:
                    try:
                        if "sequence" in test_case:
                            # For class testing, create instance and run sequence
                            class_name = next((name for name, obj in local_env.items() 
                                            if isinstance(obj, type)), None)
                            if class_name:
                                instance = local_env[class_name]()
                                result = None
                                for op in test_case["sequence"]:
                                    # Execute operation and capture last result
                                    result = eval(f"instance.{op}")
                                test_results.append(result == test_case["expected"])
                            else:
                                test_results.append(False)
                                results["error"] = "No class definition found"
                                
                        elif "verification" in test_case:
                            # For structural/type verification
                            test_results.append(eval(test_case["verification"], 
                                                  {"response": response, **local_env}))
                        else:
                            # For function testing
                            func_name = response.split("def ")[1].split("(")[0] if "def " in response else None
                            if func_name and func_name in local_env:
                                result = local_env[func_name](**test_case["input"])
                                test_results.append(result == test_case["expected"])
                            else:
                                # For single statement evaluation
                                result = eval(response, {"__builtins__": __builtins__}, 
                                           {**test_case["input"], **local_env})
                                test_results.append(result == test_case["expected"])
                                
                    except Exception as e:
                        test_results.append(False)
                        results["error"] = f"Test case execution error: {str(e)}"
                
            except Exception as e:
                results["error"] = f"Code execution error: {str(e)}"
                return results
            
            results["test_results"] = test_results
            results["test_pass_rate"] = calculate_test_pass_rate(test_results)
            results["pass_all"] = all(test_results)
            
        # Fallback to exact match if no test cases
        else:
            results["pass_all"] = bench["expected"] in response
            results["test_pass_rate"] = 1.0 if results["pass_all"] else 0.0
            
    except Exception as e:
        results["error"] = f"Evaluation error: {str(e)}"
        
    return results

def calculate_pass_at_k(n_samples: int, n_correct: int, k: int) -> float:
    """
    Calculate unbiased pass@k metric as per Chen et al. 2021:
    Probability of getting at least one correct solution in k attempts
    """
    if n_samples < k:
        return 0.0
    if n_correct == 0:
        return 0.0
    
    # Calculate probability using combinations
    def n_choose_r(n: int, r: int) -> float:
        from math import comb
        return comb(n, r)
    
    # Probability of having at least 1 success in k trials
    p = 1.0
    for r in range(k):
        p_r = (n_choose_r(n_samples - n_correct, r) * 
               n_choose_r(n_correct, k - r) / n_choose_r(n_samples, k))
        p -= p_r
    
    return p

def aggregate_benchmark_results(
    model_result: Dict[str, Any],
    k_values: List[int] = [1, 10, 100]
) -> Dict[str, Any]:
    """Aggregate benchmark results with multiple metrics including pass@k."""
    aggregated = {
        "model_id": model_result["model_id"],
        "total_tasks": len(model_result.get("task_results", [])),
        "failures": model_result.get("failures", 0),
        "metrics": {}
    }
    
    # Calculate pass@k for different k values
    task_results = model_result.get("task_results", [])
    if task_results:
        n_samples = len(task_results)
        n_correct = sum(1 for t in task_results if t.get("pass_all", False))
        
        for k in k_values:
            aggregated["metrics"][f"pass@{k}"] = calculate_pass_at_k(n_samples, n_correct, k)
    
    # Calculate average test pass rate
    if task_results:
        tpr_values = [t.get("test_pass_rate", 0.0) for t in task_results]
        aggregated["metrics"]["avg_test_pass_rate"] = sum(tpr_values) / len(tpr_values)
    
    return aggregated

def analyze_by_scenario(results: List[Dict[str, Any]], scenario: str = "difficulty") -> Dict[str, Any]:
    """
    Analyze benchmark results by different scenarios (difficulty, task type, metrics).
    As recommended by the paper section V for scenario-based evaluation.
    """
    analysis = {}
    
    if scenario == "difficulty":
        categories = DIFFICULTY_LEVELS.keys()
        grouping_key = lambda x: x.get("difficulty", "unknown")
    elif scenario == "task_type":
        categories = TASK_TYPES.keys()
        grouping_key = lambda x: x.get("type", "unknown")
    elif scenario == "metrics":
        # Collect all unique metrics across tasks
        categories = set()
        for bench in benchmarks:
            categories.update(bench.get("metrics", {}).keys())
        grouping_key = lambda x: list(x.get("metrics", {}).keys())
    else:
        raise ValueError(f"Unknown scenario: {scenario}")
    
    for model_result in results:
        model_id = model_result["model_id"]
        if model_id not in analysis:
            analysis[model_id] = {}
        
        # Group task results by category
        for category in categories:
            category_results = [
                task for task in model_result.get("task_results", [])
                if category in (grouping_key(next((b for b in benchmarks if b["name"] == task["task_name"]), {})))
            ]
            
            if category_results:
                analysis[model_id][category] = {
                    "test_pass_rate": sum(t.get("test_pass_rate", 0) for t in category_results) / len(category_results),
                    "pass@1": sum(t.get("pass@1", 0) for t in category_results) / len(category_results),
                    "pass@10": sum(t.get("pass@10", 0) for t in category_results) / len(category_results),
                    "sample_count": sum(t.get("samples", 0) for t in category_results),
                }
    
    return analysis

def print_scenario_analysis(analysis: Dict[str, Any], scenario: str, console: Optional[Console] = None) -> None:
    """Pretty print scenario-based analysis results."""
    if console is None:
        console = Console()
    
    table = Table(
        title=f"Performance Analysis by {scenario.title()}", 
        box=box.SIMPLE_HEAVY,
        show_header=True,
        header_style="bold"
    )
    
    table.add_column("Model ID", style="cyan")
    table.add_column("Category", style="green")
    table.add_column("TPR", style="yellow")
    table.add_column("pass@1", style="blue")
    table.add_column("pass@10", style="blue")
    table.add_column("Samples", style="magenta")
    
    for model_id, categories in analysis.items():
        for category, metrics in categories.items():
            table.add_row(
                model_id,
                str(category),
                f"{metrics['test_pass_rate']:.2f}",
                f"{metrics['pass@1']:.2f}",
                f"{metrics['pass@10']:.2f}",
                str(metrics['sample_count'])
            )
    
    console.print(table)
    console.print()
