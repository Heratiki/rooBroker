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

from rooBroker.roo_types.discovery import DiscoveredModel, ChatMessage
from rooBroker.interfaces.base import ModelProviderClient

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

# Standard benchmarks
benchmarks: List[Dict[str, Any]] = [
    # Statement level tasks
    {"name": "simple_statement", 
     "type": "statement",
     "difficulty": "basic",
     "prompt": "Write a Python statement to swap two variables x and y without using a temporary variable.", 
     "system_prompt": "You are a Python expert. Provide the Python code solution for the user's request. Please enclose the code within markdown code blocks (```python ... ```).",
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
     "system_prompt": "You are a Python expert. Provide the Python code solution for the user's request. Please enclose the code within markdown code blocks (```python ... ```).",
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
     "system_prompt": "You are a Python expert. Provide the Python code solution for the user's request. Please enclose the code within markdown code blocks (```python ... ```).",
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
     "system_prompt": "You are a Python expert. Provide the Python code solution for the user's request. Please enclose the code within markdown code blocks (```python ... ```).",
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
    
    try:
        if verbose:
            print(f"Evaluating response:\n{response}\n")
            
        # If there are test cases, run them
        if "test_cases" in bench:
            test_results = []
            
            # Extract code from the response if it's in a code block
            code_block_pattern = r"```(?:python)?\s*([\s\S]*?)\s*```"
            code_match = re.search(code_block_pattern, response)
            
            if code_match:
                code_to_execute = code_match.group(1).strip()
                if verbose:
                    print("Extracted code block:")
                    print(code_to_execute)
            else:
                code_to_execute = response.strip()
                if verbose:
                    print("No code block found, using raw response.")
            
            # Create a safe execution environment
            local_env = {}
            try:
                # Execute the generated code in isolated environment
                if verbose:
                    print("Executing generated code in isolated environment...")
                exec(code_to_execute, {"__builtins__": __builtins__}, local_env)
                
                for i, test_case in enumerate(bench["test_cases"], 1):
                    if verbose:
                        print(f"\nRunning test case {i}/{len(bench['test_cases'])}...")

                    # Handle context benchmark type
                    if bench["type"] == "context":
                        response_stripped = response.strip()
                        test_pass = str(test_case["expected"]) in response_stripped
                        test_results.append(test_pass)
                        if verbose:
                            print(f"Response: {response_stripped}")
                            print(f"Expected: {test_case['expected']}")
                            print(f"Test passed: {test_pass}")
                        continue

                    if "sequence" in test_case:
                        # For class testing, create instance and run sequence
                        class_name = next((name for name, obj in local_env.items() 
                                     if isinstance(obj, type)), None)
                        if class_name:
                            instance = local_env[class_name]()
                            result = None
                            for op in test_case["sequence"]:
                                if verbose:
                                    print(f"Executing operation: {op}")
                                result = eval(f"instance.{op}")
                            test_pass = result == test_case["expected"]
                            test_results.append(test_pass)
                            if verbose:
                                print(f"Result: {result}")
                                print(f"Expected: {test_case['expected']}")
                                print(f"Test passed: {test_pass}")
                        else:
                            test_results.append(False)
                            results["error"] = "No class definition found"
                            if verbose:
                                print("Error: No class definition found")
                    elif "verification" in test_case:
                        # For structural/type verification
                        if verbose:
                            print(f"Running verification: {test_case['verification']}")
                        verification_context = {"response": code_to_execute, **local_env}
                        test_pass = eval(test_case["verification"], verification_context)
                        test_results.append(test_pass)
                        if verbose:
                            print(f"Test passed: {test_pass}")
                    else:
                        # For function testing
                        func_name = code_to_execute.split("def ")[1].split("(")[0] if "def " in code_to_execute else None
                        if func_name and func_name in local_env:
                            if verbose:
                                print(f"Testing function {func_name} with input: {test_case['input']}")
                            result = local_env[func_name](**test_case["input"])
                            test_pass = result == test_case["expected"]
                            test_results.append(test_pass)
                            if verbose:
                                print(f"Result: {result}")
                                print(f"Expected: {test_case['expected']}")
                                print(f"Test passed: {test_pass}")
                        else:
                            # For single statement evaluation using function-wrapping
                            if verbose:
                                print(f"Evaluating statement with input: {test_case['input']}")

                            temp_func_name = f"temp_exec_func_{i}"
                            func_def_str = f"""
def {temp_func_name}({', '.join(test_case['input'].keys())}):
    {code_to_execute}
    return {{ {', '.join(f'\'{key}\': {key}' for key in test_case['expected'].keys())} }}
"""

                            if verbose:
                                print("Generated function definition:")
                                print(func_def_str)
                                
                            try:
                                exec(func_def_str, local_env)
                                result_dict = local_env[temp_func_name](**test_case['input'])
                                test_pass = result_dict == test_case['expected']
                                test_results.append(test_pass)

                                if verbose:
                                    print(f"Result: {result_dict}")
                                    print(f"Expected: {test_case['expected']}")
                                    print(f"Test passed: {test_pass}")
                            except Exception as e:
                                test_results.append(False)
                                if verbose:
                                    print(f"Execution error: {str(e)}")
            except Exception as e:
                results["error"] = f"Execution error: {str(e)}"
                if verbose:
                    print(f"Execution error: {str(e)}")

            results["test_results"] = test_results
            results["test_pass_rate"] = calculate_test_pass_rate(test_results)
            results["pass_all"] = all(test_results)
            
            if verbose:
                print(f"\nFinal results:")
                print(f"Test pass rate: {results['test_pass_rate']}")
                print(f"All tests passed: {results['pass_all']}")
            
        # Fallback to exact match if no test cases
        else:
            results["pass_all"] = bench["expected"] in response
            results["test_pass_rate"] = 1.0 if results["pass_all"] else 0.0
            if verbose:
                print(f"No test cases, using exact match.")
                print(f"Match found: {results['pass_all']}")
            
    except Exception as e:
        results["error"] = f"Evaluation error: {str(e)}"
        if verbose:
            print(f"Evaluation error: {str(e)}")
        
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
        for bench in benchmarks:
            if verbose:
                print(f"\nRunning benchmark: {bench['name']}")
                print(f"Type: {bench['type']}, Difficulty: {bench['difficulty']}")
            
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
                    
                except Exception as e:
                    if verbose:
                        print(f"Failed to run benchmark: {str(e)}")
                    model_result["failures"] += 1
        
        if verbose:
            print(f"\nCompleted benchmark for model: {model_id}")
            print(f"Total tasks completed: {len(model_result['task_results'])}")
            print(f"Failures: {model_result['failures']}")
        
        results.append(model_result)
        
    return results