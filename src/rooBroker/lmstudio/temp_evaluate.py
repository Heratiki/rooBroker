"""
Temporary evaluation script to test code quality metrics implementation.
"""
from typing import Dict, Any, List
import json
from .code_quality import CodeQualityMetrics
from .client import call_lmstudio_with_max_context

# Test cases that exercise different aspects of code quality
TEST_CASES = [
    {
        "name": "Simple function",
        "prompt": "Write a function to calculate the factorial of a number",
        "reference": """def factorial(n: int) -> int:
    \"\"\"Calculate the factorial of a number.
    
    Args:
        n: The number to calculate factorial for
        
    Returns:
        The factorial of n
    \"\"\"
    if n == 0:
        return 1
    return n * factorial(n - 1)"""
    },
    {
        "name": "Class implementation",
        "prompt": "Create a Stack class with push and pop methods",
        "reference": """class Stack:
    \"\"\"A simple stack implementation using a list.\"\"\"
    
    def __init__(self):
        \"\"\"Initialize an empty stack.\"\"\"
        self._items: List[Any] = []
    
    def push(self, item: Any) -> None:
        \"\"\"Push an item onto the stack.\"\"\"
        self._items.append(item)
    
    def pop(self) -> Any:
        \"\"\"Remove and return the top item from the stack.\"\"\"
        if not self._items:
            raise IndexError("pop from empty stack")
        return self._items.pop()"""
    }
]

def run_evaluation(model_id: str, api_endpoint: str = "http://localhost:1234/v1/chat/completions") -> Dict[str, Any]:
    """Run code quality evaluation tests."""
    results = {}
    
    for test in TEST_CASES:
        try:
            # Generate code using the model
            response = call_lmstudio_with_max_context(
                model_id,
                [
                    {"role": "system", "content": "You are an expert Python programmer. Write clean, well-documented code."},
                    {"role": "user", "content": test["prompt"]}
                ],
                temperature=0.2
            )
            
            if response and isinstance(response, dict):
                generated_code = response["choices"][0]["message"]["content"].strip()
                
                # Evaluate code quality
                quality_metrics = CodeQualityMetrics.evaluate_code_quality(
                    generated_code,
                    reference=test["reference"]
                )
                
                results[test["name"]] = {
                    "generated_code": generated_code,
                    "metrics": quality_metrics
                }
            
        except Exception as e:
            results[test["name"]] = {"error": str(e)}
    
    return results

def print_evaluation_report(results: Dict[str, Any]) -> None:
    """Print a formatted evaluation report."""
    print("\nCode Quality Evaluation Report")
    print("=" * 50)
    
    for test_name, test_results in results.items():
        print(f"\nTest: {test_name}")
        print("-" * 30)
        
        if "error" in test_results:
            print(f"Error: {test_results['error']}")
            continue
            
        metrics = test_results["metrics"]
        
        print("\nGenerated Code:")
        print("-" * 20)
        print(test_results["generated_code"])
        
        print("\nMetrics:")
        print("-" * 20)
        print(f"BLEU Score: {metrics.get('bleu_score', 'N/A'):.3f}")
        print(f"Overall Quality Score: {metrics.get('overall_score', 'N/A'):.3f}")
        
        complexity = metrics.get("complexity", {})
        print("\nComplexity Metrics:")
        print(f"- Cyclomatic Complexity: {complexity.get('cyclomatic_complexity', 'N/A')}")
        print(f"- Maintainability Index: {complexity.get('maintainability_index', 'N/A')}")
        print(f"- Lines of Code: {complexity.get('loc', 'N/A')}")
        
        style = metrics.get("style", {})
        print("\nStyle Conformance:")
        print(f"- Style Score: {style.get('style_score', 'N/A'):.3f}")
        print(f"- Needs Formatting: {style.get('requires_formatting', 'N/A')}")
        
        errors = metrics.get("errors", {})
        if errors.get("error_count", 0) > 0:
            print("\nDetected Issues:")
            for error in errors.get("errors", []):
                print(f"- {error['type']}: {error['details']}")
        
        print("\n" + "=" * 50)

if __name__ == "__main__":
    # Example usage
    results = run_evaluation("stable-code-3b")
    print_evaluation_report(results)
    
    # Save detailed results to file
    with open("code_quality_evaluation.json", "w") as f:
        json.dump(results, f, indent=2)
