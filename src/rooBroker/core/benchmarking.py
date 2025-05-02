"""Core benchmarking functionality for model evaluation.

This module provides the core benchmarking infrastructure used to evaluate
language models across different providers. It includes standard benchmark
definitions, evaluation metrics, and execution logic.
"""

from typing import List, Dict, Any, Optional, cast
from datetime import datetime, timezone
from math import comb
from pathlib import Path
import re
import inspect
from pydantic import ValidationError
from rich.console import Console
from rich.progress import Progress
from textwrap import dedent
import time
import io
import contextlib

from rooBroker.roo_types.discovery import DiscoveredModel, ChatMessage
from rooBroker.interfaces.base import ModelProviderClient
from rooBroker.roo_types.benchmarking import BenchmarkTask
from rooBroker.core.log_config import logger

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
    logger.debug(f"Raw response received: {repr(response)}") # Log raw response

    try:
        logger.debug(f"Evaluating benchmark: {bench.get('name')}, Method: {bench.get('evaluation_method')}")
        # logger.debug(f"DEBUG: Bench data: {bench}") # Keep this if needed, but can be verbose

        # Extract code block or use raw response
        code_block_pattern = r"""
        ```(?:python)?\s*([\s\S]*?)\s*```
        """
        code_match = re.search(code_block_pattern, response, re.VERBOSE)
        code_to_execute = code_match.group(1).strip() if code_match else response.strip()
        logger.debug(f"Code to execute: {repr(code_to_execute)}") # Log processed code

        if verbose:
            print("Processed response:", code_to_execute)

        # Evaluation logic based on evaluation_method
        if bench["evaluation_method"] == "string_contains":
            logger.debug(f"String Contains - Starting evaluation for {bench.get('name')}")
            
            # Get the expected value from test cases first
            if bench.get("test_cases") and len(bench["test_cases"]) > 0:
                expected = bench["test_cases"][0].get("expected")
            else:
                # Fallback to top-level expected or variants
                expected = bench.get("expected")
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
            
            logger.debug(f"DEBUG: String Contains - Expected Type: {type(expected)}, Expected Value: {repr(expected)}")
            logger.debug(f"DEBUG: String Contains - Response Type: {type(response)}, Response Value: {repr(response)}")
            logger.debug("DEBUG: String Contains - About to perform 'expected in response'")
            
            # Ensure both expected and response are strings before comparison
            expected_str = str(expected)
            response_str = str(response)
            
            results["pass_all"] = expected_str in response_str
            results["test_pass_rate"] = 1.0 if results["pass_all"] else 0.0
            logger.debug(f"DEBUG: String Contains - Check completed. Result: {results['pass_all']}")
            return results

        elif bench["evaluation_method"] == "exec_check_state":
            test_results = []
            for i, test_case in enumerate(bench["test_cases"]):
                # Safely handle optional 'expected' values
                expected_keys = list(test_case["expected"].keys()) if isinstance(test_case.get("expected"), dict) else []

                local_env = test_case["input"].copy()
                # Initialize input variables at the start of the function
                input_init = "\n".join(f"    {k} = {repr(v)}" for k, v in test_case["input"].items())
                
                # Build function string with explicit indentation control
                func_def_str = (
                    "def temp_func():\n" + 
                    input_init + "\n" +
                    "    " + code_to_execute + "\n" +
                    "    return {" +
                    f"k: v for k, v in locals().items() if k in {expected_keys}" +
                    "}"
                )

                if verbose:
                    print("Generated function:", func_def_str)

                try:
                    # Redirect stdout during exec
                    with contextlib.redirect_stdout(io.StringIO()):
                        exec(func_def_str, local_env)
                    result = local_env["temp_func"]()
                    passed = result == test_case.get("expected", {})
                    test_results.append(passed)
                    logger.debug(f"Exec_check_state - Test Case {i+1}: {'Pass' if passed else 'Fail'} (Expected: {test_case.get('expected', {})}, Got: {result})")
                except Exception as e:
                    passed = False
                    test_results.append(passed)
                    error_msg = f"Exec_check_state - Test Case {i+1}: Execution error: {e}"
                    logger.debug(error_msg) # Log error at debug level
                    if verbose:
                        print(error_msg)

            results["test_results"] = test_results
            results["test_pass_rate"] = sum(test_results) / len(test_results) if test_results else 0.0
            results["pass_all"] = all(test_results)
            logger.debug(f"Exec_check_state - Final Results: {results}") # Log final results
            return results

        elif bench["evaluation_method"] == "exec_call_func":
            test_results = []
            for i, test_case in enumerate(bench["test_cases"]):
                local_env = {}
                passed = False # Default to False
                try:
                    # Redirect stdout during the initial exec to define the function/class
                    with contextlib.redirect_stdout(io.StringIO()):
                        exec(code_to_execute, {"__builtins__": __builtins__}, local_env)

                    if "sequence" in test_case:
                        class_name = next((name for name, obj in local_env.items() if isinstance(obj, type)), None)
                        if class_name:
                            # Execute sequence of class method calls
                            instance = local_env[class_name]()
                            result = None
                            # Redirect stdout during eval for method calls
                            with contextlib.redirect_stdout(io.StringIO()):
                                for call in test_case["sequence"]:
                                    result = eval(f"instance.{call}", {"instance": instance})
                            passed = result == test_case.get("expected")
                            logger.debug(f"Exec_call_func (Class Seq) - Test Case {i+1}: {'Pass' if passed else 'Fail'} (Expected: {test_case.get('expected')}, Got: {result})")
                        else:
                            logger.debug(f"Exec_call_func (Class Seq) - Test Case {i+1}: Fail - No class definition found")
                            # passed remains False
                    else:
                        # Find the first callable that's not a builtin
                        func_name = next((name for name in local_env if callable(local_env[name])), None)
                        if func_name:
                            # Get the function's parameter names
                            params = inspect.signature(local_env[func_name]).parameters
                            param_names = list(params.keys())
                            
                            # Map test case input keys to function parameter names
                            if param_names:
                                # If we have a single parameter and input doesn't match, use first value
                                if len(param_names) == 1 and not any(k in test_case["input"] for k in param_names):
                                    first_value = next(iter(test_case["input"].values()))
                                    result = local_env[func_name](first_value)
                                else:
                                    # Map input keys to parameter names
                                    kwargs = {
                                        k: v for k, v in test_case["input"].items()
                                        if k in param_names
                                    }
                                    # Redirect stdout during function call
                                    with contextlib.redirect_stdout(io.StringIO()):
                                        result = local_env[func_name](**kwargs)
                                passed = result == test_case["expected"]
                                logger.debug(f"Exec_call_func (Func) - Test Case {i+1}: {'Pass' if passed else 'Fail'} (Expected: {test_case['expected']}, Got: {result})")
                            else:
                                logger.debug(f"Exec_call_func (Func) - Test Case {i+1}: Fail - Function has no parameters")
                                # passed remains False
                        else:
                            logger.debug(f"Exec_call_func (Func) - Test Case {i+1}: Fail - No function definition found")
                            # passed remains False
                except Exception as e:
                    # passed remains False
                    error_msg = f"Exec_call_func - Test Case {i+1}: Execution error: {e}"
                    logger.debug(error_msg) # Log error at debug level
                    if verbose:
                        print(error_msg)
                finally:
                    test_results.append(passed) # Append final pass/fail status

            results["test_results"] = test_results
            results["test_pass_rate"] = sum(test_results) / len(test_results) if test_results else 0.0
            results["pass_all"] = all(test_results)
            logger.debug(f"Exec_call_func - Final Results: {results}") # Log final results
            return results

        elif bench["evaluation_method"] == "eval_expression":
            test_results = []
            for i, test_case in enumerate(bench["test_cases"]):
                passed = False  # Default to False
                try:
                    # Create a local environment for execution
                    local_env = {"__builtins__": {"range": range, "len": len}}

                    # Execute the entire code block
                    exec(code_to_execute, {"__builtins__": __builtins__}, local_env)

                    # Retrieve the result variable from the local environment
                    result = local_env.get("result")

                    # Compare the result with the expected value
                    passed = result == test_case["expected"]

                    logger.debug(f"Eval_expression - Test Case {i+1}: {'Pass' if passed else 'Fail'} (Expected: {test_case['expected']}, Got: {result})")

                    if verbose:
                        print(f"Executed code block:\n{code_to_execute}")
                        print(f"Result: {result}")
                        print(f"Expected: {test_case['expected']}")
                        print(f"Test passed: {passed}")

                except Exception as e:
                    # Log and handle execution errors
                    error_msg = f"Eval_expression - Test Case {i+1}: Execution error: {str(e)}"
                    logger.debug(error_msg)  # Log error at debug level
                    if verbose:
                        print(error_msg)

                finally:
                    test_results.append(passed)  # Append final pass/fail status

            results["test_results"] = test_results
            results["test_pass_rate"] = sum(test_results) / len(test_results) if test_results else 0.0
            results["pass_all"] = all(test_results)
            logger.debug(f"Eval_expression - Final Results: {results}")  # Log final results
            return results

        elif bench["evaluation_method"] == "class_eval":
            logger.debug("Entering class_eval logic block.")
            test_results = []
            try:
                # Execute the provided code to define the class in a local environment
                local_env = {}
                exec(code_to_execute, local_env)
                logger.debug(f"Executed code. local_env keys: {list(local_env.keys())}")

                # Find the class definition in the local environment
                class_name = next((name for name, obj in local_env.items() if isinstance(obj, type)), None)
                if not class_name:
                    logger.debug("No class definition found in the provided code.")
                    raise ValueError("No class definition found in the provided code.")

                logger.debug(f"Found class definition: {class_name}")
                class_def = local_env[class_name]

                logger.debug(f"Starting test case loop for {len(bench['test_cases'])} cases.")
                for i, test_case in enumerate(bench["test_cases"]):
                    logger.debug(f"Test Case {i+1}: Instantiating class {class_name}")
                    instance = class_def()  # Instantiate the class
                    result = None

                    try:
                        for call in test_case["sequence"]:
                            logger.debug(f"Test Case {i+1}: Executing step: {call}")
                            try:
                                # Attempt to execute the method call
                                result = eval(f"instance.{call}", {"instance": instance})
                            except AttributeError as e:
                                # Handle potential method name mismatches (e.g., camelCase to snake_case)
                                snake_case_call = re.sub(r'(?<!^)(?=[A-Z])', '_', call).lower()
                                result = eval(f"instance.{snake_case_call}", {"instance": instance})

                        logger.debug(f"Test Case {i+1}: Sequence result: {result}")
                        # Compare the result of the last operation with the expected value
                        passed = result == test_case["expected"]
                        logger.debug(f"Test Case {i+1}: Comparison result: {passed}")
                        test_results.append(passed)
                    except Exception as e:
                        logger.debug(f"Test Case {i+1}: Error during execution: {e}")
                        test_results.append(False)

                # Calculate pass rate and overall pass status
                results["test_results"] = test_results
                results["test_pass_rate"] = sum(test_results) / len(test_results) if test_results else 0.0
                results["pass_all"] = all(test_results)

            except Exception as e:
                logger.exception(f"class_eval - General Error: {e}")
                results["error"] = str(e)

            return results

        else:
            logger.error(f"Unrecognized evaluation method: {bench['evaluation_method']}") # Log as error
            results["error"] = f"Unrecognized evaluation method: {bench['evaluation_method']}"
            return results

    except Exception as e:
        logger.exception(f"General evaluation error for benchmark '{bench.get('name')}': {str(e)}") # Use logger.exception
        results["error"] = f"General evaluation error: {str(e)}"
        if verbose:
            print("General evaluation error:", e)

    logger.debug(f"Evaluation Results before return for '{bench.get('name')}': {results}")
    return results

def calculate_pass_at_k(n_samples: int, n_correct: int, k: int) -> float:
    """
    Calculate unbiased pass@k metric as per Chen et al. 2021:
    Probability of getting at least one correct solution in k attempts
    """
    if n_samples < k or k <= 0:
        return 0.0
    if n_correct == n_samples:
        return 1.0

    failures = n_samples - n_correct
    if failures < k:
        return 1.0

    try:
        prob_all_failures = comb(failures, k) / comb(n_samples, k)
        return 1.0 - prob_all_failures
    except ValueError as e:
        logger.error(f"Error calculating pass@k: {e}")
        return 0.0

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
    progress: Progress,  # Progress object for tracking (required)
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
        progress: Progress object for tracking progress
        num_samples: Number of samples to generate per task for pass@k calculation
        verbose: Enable verbose output during benchmarking
        
    Returns:
        List[Dict[str, Any]]: List of benchmark results per model, including
            metrics like test pass rate and pass@k scores
    """
    results: List[Dict[str, Any]] = []
    total_benchmarks = len(models_to_benchmark) * len(benchmarks_to_run)
    
    # Add overall progress task
    overall_task = progress.add_task(
        "[cyan]Overall Progress",
        total=total_benchmarks * num_samples
    )

    for model in models_to_benchmark:
        model_id = str(model["id"])  # Ensure model_id is a string
        provider_name = client.__class__.__name__.replace('Client', '')

        # Skip embedding models
        if "embed" in model_id.lower() or "embedding" in model_id.lower():
            if verbose:
                print(f"Skipping embedding model: {model_id}")
            continue

        model_result = {
            "model_id": model_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "task_results": [],
            "failures": 0
        }

        # Add progress task for the model
        model_task = progress.add_task(
            f"[blue]{provider_name} - Model: {model_id}",
            total=len(benchmarks_to_run)
        )

        for bench in benchmarks_to_run:
            task_desc = f"{bench['name']} ({bench['difficulty']})"
            bench_task = progress.add_task(
                f"[green]{task_desc}",
                total=num_samples
            )

            try:
                bench_result = {
                    "benchmark_id": bench["id"],
                    "name": bench["name"],
                    "type": bench["type"],
                    "difficulty": bench["difficulty"],
                    "samples": []
                }

                # Run the benchmark num_samples times
                for sample_num in range(num_samples):
                    # Construct messages for the client
                    messages = [
                        ChatMessage(role="system", content=bench.get("system_prompt", "You are a helpful coding assistant.")),
                        ChatMessage(role="user", content=bench["prompt"])
                    ]
                    
                    # Execute the benchmark by calling the client
                    try: # Add try/except around client call
                        response_data: str = client.run_completion(
                            model_id=model_id,
                            messages=messages,
                            max_tokens=bench.get("max_tokens", 1024),
                            temperature=bench.get("temperature", 0.7)
                        )
                        response_content = response_data
                        logger.debug(f"Model '{model_id}', Benchmark '{bench['name']}', Sample {sample_num+1} - Response received: {repr(response_content)}")

                        # Evaluate the response - MODIFY THIS LINE
                        # Don't pass verbose to evaluate_response even when verbose flag is on
                        evaluation = evaluate_response(response_content, bench, False)

                        # Store sample result
                        bench_result["samples"].append({
                            "sample_num": sample_num + 1,
                            "response": response_content,
                            "evaluation": evaluation
                        })
                    except Exception as client_err:
                        error_msg = f"Model '{model_id}', Benchmark '{bench['name']}', Sample {sample_num+1} - Error during client.run_completion or evaluation: {client_err}"
                        logger.error(error_msg) # Log client/eval errors as ERROR
                        # Store error information in sample result
                        bench_result["samples"].append({
                            "sample_num": sample_num + 1,
                            "response": None,
                            "evaluation": {"error": error_msg, "pass_all": False, "test_results": [], "test_pass_rate": 0.0}
                        })
                        model_result["failures"] += 1 # Increment failures for this specific sample error

                    # Update progress
                    progress.update(bench_task, advance=1)
                    progress.update(overall_task, advance=1)

                # Aggregate results for the benchmark *after* all samples are run
                # Calculate average TPR across samples for this benchmark
                sample_evals = [s['evaluation'] for s in bench_result['samples'] if s['evaluation']]
                if sample_evals:
                    bench_result['avg_test_pass_rate'] = sum(e.get('test_pass_rate', 0.0) for e in sample_evals) / len(sample_evals)
                    bench_result['pass_all_count'] = sum(1 for e in sample_evals if e.get('pass_all', False))

                    # Calculate pass@k metrics
                    n_samples = len(sample_evals)
                    n_correct = bench_result['pass_all_count']
                    k_values = [1, 5, 10]  # Define desired k values
                    pass_at_k_scores = {}

                    for k in k_values:
                        pass_at_k_scores[f"pass@{k}"] = calculate_pass_at_k(n_samples, n_correct, k)

                    bench_result['pass_at_k'] = pass_at_k_scores
                    bench_result['successful_samples'] = n_correct
                    bench_result['total_samples'] = n_samples

                else:
                    bench_result['avg_test_pass_rate'] = 0.0
                    bench_result['pass_all_count'] = 0
                    bench_result['pass_at_k'] = {}
                    bench_result['successful_samples'] = 0
                    bench_result['total_samples'] = 0

                logger.debug(f"Benchmark '{bench['name']}' completed. Avg TPR: {bench_result['avg_test_pass_rate']:.2f}, Pass All Count: {bench_result['pass_all_count']}/{num_samples}, Pass@K: {bench_result['pass_at_k']}")

                model_result["task_results"].append(bench_result)

            except Exception as e: # Catch errors during the benchmark loop itself (less likely now)
                error_msg = f"Error processing benchmark {bench['name']} for model {model_id}: {str(e)}"
                logger.exception(error_msg) # Use exception to get traceback
                # We might not have sample results here, so just note the failure
                model_result["failures"] += num_samples # Count all samples as failed if the whole bench loop fails

            progress.update(model_task, advance=1)

        results.append(model_result)

    progress.stop() # Explicitly stop the progress display before exiting the context
    return results

def load_benchmarks_from_directory(directory_path: str) -> List[Dict[str, Any]]:
    """Load and validate benchmark JSON files from a directory.
    
    This function loads benchmark definitions from JSON files and validates them
    against the appropriate schema based on their evaluation method. It provides
    detailed error messages when validation fails.
    
    Args:
        directory_path: Path to the directory containing benchmark JSON files
        
    Returns:
        List of validated benchmark definitions
        
    Raises:
        ValidationError: If any benchmark file fails validation
        JSONDecodeError: If any file contains invalid JSON
    """
    from pathlib import Path
    from rich.console import Console
    import json
    from pydantic import ValidationError
    from ..roo_types.benchmark_schemas import BenchmarkTask
    
    console = Console()
    loaded_benchmarks = []
    failed_benchmarks = []

    # Load and validate each JSON file
    for json_file in Path(directory_path).rglob('*.json'):
        try:
            with open(json_file, 'r', encoding='utf-8') as file:
                content = json.load(file)

            # Add file path to content for better error messages
            if 'id' not in content:
                content['id'] = json_file.stem

            # Validate using Pydantic model
            benchmark = BenchmarkTask(**content)
            loaded_benchmarks.append(benchmark.model_dump())

        except json.JSONDecodeError as e:
            failed_benchmarks.append({
                'file': str(json_file),
                'error': f"JSON decode error: {str(e)}",
                'line': e.lineno,
                'column': e.colno
            })
        except ValidationError as e:
            failed_benchmarks.append({
                'file': str(json_file),
                'error': "Validation errors:\n" + "\n".join(
                    f"  - {error['loc']}: {error['msg']}"
                    for error in e.errors()
                )
            })
        except Exception as e:
            failed_benchmarks.append({
                'file': str(json_file),
                'error': f"Unexpected error: {str(e)}"
            })

    # Report any validation failures
    if failed_benchmarks:
        console.print("\n[red]Benchmark Validation Errors:[/red]")
        for failure in failed_benchmarks:
            console.print(f"\n[yellow]File:[/yellow] {failure['file']}")
            console.print(f"[red]Error:[/red] {failure['error']}")
            if 'line' in failure and 'column' in failure:
                console.print(f"[yellow]Location:[/yellow] Line {failure['line']}, Column {failure['column']}")
        console.print(f"\n[yellow]Successfully loaded {len(loaded_benchmarks)} of {len(loaded_benchmarks) + len(failed_benchmarks)} benchmarks[/yellow]\n")

    return loaded_benchmarks