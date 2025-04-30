"""Core benchmarking functionality for model evaluation.

This module provides the core benchmarking infrastructure used to evaluate
language models across different providers. It includes standard benchmark
definitions, evaluation metrics, and execution logic.
"""

from typing import List, Dict, Any, Optional, cast
from datetime import datetime, timezone
import sys
import re
from math import comb
from pathlib import Path
import json
from pydantic import ValidationError
from rich.console import Console
import textwrap
from textwrap import dedent

from rooBroker.roo_types.discovery import DiscoveredModel, ChatMessage
from rooBroker.interfaces.base import ModelProviderClient
from rooBroker.roo_types.benchmarking import BenchmarkTask

# Benchmark metadata types
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

def calculate_test_pass_rate(test_results: List[bool]) -> float:
    """Calculate the test pass rate (TPR) metric."""
    if not test_results:
        return 0.0
    return sum(1 for result in test_results if result) / len(test_results)

def evaluate_response(response: str, bench: Dict[str, Any], verbose: bool = False) -> Dict[str, Any]:
    """Evaluate a model response against test cases with enhanced metrics."""
    results = {
        "pass_all": False,
        "test_results": [],
        "test_pass_rate": 0.0,
        "error": None
    }

    # Pre-processing: Remove <think>...</think> blocks
    response = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL).strip()

    try:
        print(f"DEBUG: Evaluating benchmark: {bench.get('name')}, Method: {bench.get('evaluation_method')}")
        print(f"DEBUG: Bench data: {bench}")

        # Extract code block or use raw response
        code_block_pattern = r"```(?:python)?\s*([\s\S]*?)\s*```"
        code_match = re.search(code_block_pattern, response)
        code_to_execute = code_match.group(1).strip() if code_match else response.strip()

        if verbose:
            print("Processed response:", code_to_execute)

        # Evaluation logic based on evaluation_method
        if bench["evaluation_method"] == "string_contains":
            print(f"DEBUG: String Contains - Starting evaluation for {bench.get('name')}")
            
            # Get the primary expected value
            expected = bench.get("expected")
            
            # If no primary expected value, try to get from variants
            if expected is None:
                variants = bench.get("expected_response_variants")
                if variants and isinstance(variants, list) and len(variants) > 0:
                    expected = variants[0]
            
            # If we still don't have an expected value, record error
            if expected is None:
                results["error"] = "No expected value found in benchmark definition"
                results["pass_all"] = False
                results["test_pass_rate"] = 0.0
                if verbose:
                    print("Error: No expected value found in benchmark definition")
                return results
            
            print(f"DEBUG: String Contains - Expected Type: {type(expected)}, Expected Value: {repr(expected)}")
            print(f"DEBUG: String Contains - Response Type: {type(response)}, Response Value: {repr(response)}")
            print("DEBUG: String Contains - About to perform 'expected in response'")
            
            # Ensure both expected and response are strings before comparison
            expected_str = str(expected)
            response_str = str(response)
            
            results["pass_all"] = expected_str in response_str
            results["test_pass_rate"] = 1.0 if results["pass_all"] else 0.0
            print(f"DEBUG: String Contains - Check completed. Result: {results['pass_all']}")

        elif bench["evaluation_method"] == "exec_check_state":
            test_results = []
            for test_case in bench["test_cases"]:
                # Safely handle optional 'expected' values
                expected_keys = list(test_case["expected"].keys()) if isinstance(test_case.get("expected"), dict) else []

                local_env = test_case["input"].copy()
                # Indent the code to be executed
                indented_code = '\n'.join([' ' * 4 + line for line in code_to_execute.splitlines()])

                func_def_str = dedent(f"""
                def temp_func():
                    {indented_code}
                    # Return the dictionary of expected state variables
                    return {{k: v for k, v in locals().items() if k in {expected_keys}}}
                """)
                try:
                    exec(func_def_str, local_env)
                    result = local_env["temp_func"]()
                    test_results.append(result == test_case.get("expected", {}))
                except Exception as e:
                    test_results.append(False)
                    if verbose:
                        print("Execution error:", e)

            results["test_results"] = test_results
            results["test_pass_rate"] = sum(test_results) / len(test_results) if test_results else 0.0
            results["pass_all"] = all(test_results)

        elif bench["evaluation_method"] == "exec_call_func":
            test_results = []
            for test_case in bench["test_cases"]:
                local_env = {}
                try:
                    exec(code_to_execute, {"__builtins__": __builtins__}, local_env)
                    if "sequence" in test_case:
                        class_name = next((name for name, obj in local_env.items() if isinstance(obj, type)), None)
                        if class_name:
                            instance = local_env[class_name]()
                            result = None
                            for op in test_case["sequence"]:
                                result = eval(f"instance.{op}")
                            test_results.append(result == test_case["expected"])
                        else:
                            test_results.append(False)
                    else:
                        func_name = next((name for name in local_env if callable(local_env[name])), None)
                        if func_name:
                            result = local_env[func_name](**test_case["input"])
                            test_results.append(result == test_case["expected"])
                        else:
                            test_results.append(False)
                except Exception as e:
                    test_results.append(False)
                    if verbose:
                        print("Execution error:", e)

            results["test_results"] = test_results
            results["test_pass_rate"] = sum(test_results) / len(test_results) if test_results else 0.0
            results["pass_all"] = all(test_results)

        elif bench["evaluation_method"] == "eval_expression":
            test_results = []
            for test_case in bench["test_cases"]:
                try:
                    result = eval(code_to_execute, {"__builtins__": __builtins__}, test_case["input"])
                    test_results.append(result == test_case["expected"])
                except Exception as e:
                    test_results.append(False)
                    if verbose:
                        print("Eval error:", e)

            results["test_results"] = test_results
            results["test_pass_rate"] = sum(test_results) / len(test_results) if test_results else 0.0
            results["pass_all"] = all(test_results)

        else:
            results["error"] = f"Unrecognized evaluation method: {bench['evaluation_method']}"
            if verbose:
                print(f"Unrecognized evaluation method: {bench['evaluation_method']}")

    except Exception as e:
        results["error"] = f"General evaluation error: {str(e)}"
        if verbose:
            print("General evaluation error:", e)

    print(f"DEBUG: Evaluation Results before return: {results}")
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

def run_standard_benchmarks(
    client: ModelProviderClient,
    models_to_benchmark: List[DiscoveredModel],
    benchmarks_to_run: List[Dict[str, Any]],
    num_samples: int = 20,  # Number of samples to generate per task for pass@k
    verbose: bool = False  # Enable verbose output
) -> List[Dict[str, Any]]:
    """Run standard benchmarks on the provided models using the given client.
    
    This function executes the standard benchmark suite against each model,
    using the provided ModelProviderClient for interactions. It generates
    multiple samples per task to calculate pass@k metrics.
    
    Args:
        client: The model provider client to use for completions
        models_to_benchmark: List of models to benchmark
        benchmarks_to_run: List of benchmark tasks to execute
        num_samples: Number of samples to generate per task for pass@k calculation
        verbose: Enable verbose output during benchmarking
        
    Returns:
        List[Dict[str, Any]]: List of benchmark results per model, including
            metrics like test pass rate and pass@k scores
    """
    results: List[Dict[str, Any]] = []

    for model in models_to_benchmark:
        model_id: str = model["id"]

        # Skip embedding models
        if "embed" in model_id.lower() or "embedding" in model_id.lower():
            if verbose:
                print(f"Skipping embedding model: {model_id}")
            continue

        if verbose:
            print(f"\nStarting benchmark for model: {model_id}")

        model_result = {
            "model_id": model_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "task_results": [],
            "failures": 0
        }

        # Run each benchmark multiple times for pass@k calculation
        for bench in benchmarks_to_run:
            if verbose:
                print(f"\nRunning benchmark: {bench['name']}")
                print(f"Type: {bench['type']}, Difficulty: {bench['difficulty']}")

            consecutive_failures = 0  # Track consecutive failures for the same task

            for sample in range(num_samples):
                if verbose:
                    print(f"\nGenerating sample {sample + 1}/{num_samples}")

                try:
                    # Construct messages for the model
                    messages = [
                        {"role": "system", "content": bench["system_prompt"]},
                        {"role": "user", "content": bench["prompt"]}
                    ]

                    if verbose:
                        print("Sending request to model:")
                        print(f"System prompt: {bench['system_prompt']}")
                        print(f"User prompt: {bench['prompt']}")

                    # Get completion from the model
                    response = client.run_completion(
                        model_id=model_id,
                        messages=cast(List[ChatMessage], messages),
                        temperature=bench.get("temperature", 0.2)
                    )

                    if verbose:
                        print("\nReceived response:")
                        print(response)

                    # Evaluate the response
                    eval_result = evaluate_response(response, bench, verbose)

                    if verbose:
                        print("\nEvaluation results:")
                        print(f"Pass all tests: {eval_result['pass_all']}")
                        print(f"Test pass rate: {eval_result['test_pass_rate']}")
                        if eval_result['error']:
                            print(f"Error: {eval_result['error']}")

                    model_result["task_results"].append({
                        "benchmark": bench["name"],
                        "type": bench["type"],
                        "difficulty": bench["difficulty"],
                        "sample_index": sample,
                        **eval_result
                    })

                    # Reset consecutive failures on success
                    consecutive_failures = 0

                except (TimeoutError, ConnectionError) as network_error:
                    consecutive_failures += 1
                    model_result["failures"] += 1
                    if verbose:
                        print(f"Network error during benchmark: {network_error}")

                    # Break the loop if too many consecutive failures occur
                    if consecutive_failures >= 3:
                        if verbose:
                            print(f"Too many consecutive failures for benchmark: {bench['name']}. Skipping remaining samples.")
                        break

                except Exception as e:
                    model_result["failures"] += 1
                    if verbose:
                        print(f"General error during benchmark: {e}")

        if verbose:
            print(f"\nCompleted benchmark for model: {model_id}")
            print(f"Total tasks completed: {len(model_result['task_results'])}")
            print(f"Failures: {model_result['failures']}")

        results.append(model_result)

    return results

def load_benchmarks_from_directory(directory_path: str) -> List[Dict[str, Any]]:
    """Load and validate benchmark JSON files from a directory."""
    console = Console()
    loaded_benchmarks = []

    for json_file in Path(directory_path).rglob('*.json'):
        try:
            with open(json_file, 'r', encoding='utf-8') as file:
                content = json.load(file)

            # Validate using Pydantic model
            benchmark = BenchmarkTask(**content)

            # Convert to dictionary and assign unique ID if not present
            benchmark_dict = benchmark.model_dump()
            if 'id' not in benchmark_dict:
                benchmark_dict['id'] = str(json_file)

            loaded_benchmarks.append(benchmark_dict)

        except json.JSONDecodeError as e:
            console.print(f"[red]Failed to decode JSON in file {json_file}: {e}[/red]")
        except ValidationError as e:
            console.print(f"[red]Validation error in file {json_file}: {e}[/red]")

    return loaded_benchmarks