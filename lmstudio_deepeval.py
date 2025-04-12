from typing import List, Dict, Any, Optional
import requests
from deepeval.models.base_model import DeepEvalBaseLLM
from deepeval.metrics import HallucinationMetric, AnswerRelevancyMetric
from deepeval.benchmarks.big_bench_hard.big_bench_hard import BigBenchHard

class LMStudioLLM(DeepEvalBaseLLM):
    """LM Studio model wrapper for DeepEval benchmarking."""
    
    def __init__(self, model_id: str, api_endpoint: str = "http://localhost:1234/v1/chat/completions", timeout: int = 30):
        """Initialize the LM Studio model wrapper.
        
        Args:
            model_id: The ID of the model in LM Studio
            api_endpoint: The endpoint URL for LM Studio's API
            timeout: Timeout in seconds for API calls
        """
        super().__init__()
        self.model_id = model_id
        self.api_endpoint = api_endpoint
        self.timeout = timeout

    def generate(self, prompt: str, **kwargs) -> str:
        """Generate a response from the LM Studio model.
        
        Args:
            prompt: The input prompt
            **kwargs: Additional arguments (temperature, max_tokens, etc.)
        
        Returns:
            The model's response as a string
        """
        try:
            payload = {
                "model": self.model_id,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "temperature": kwargs.get("temperature", 0.7),
                "max_tokens": kwargs.get("max_tokens", 2000)
            }
            
            response = requests.post(self.api_endpoint, json=payload, timeout=self.timeout)
            response.raise_for_status()
            
            return response.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"Error generating response: {str(e)}")
            return ""

def benchmark_with_bigbench(
    model: Dict[str, Any],
    api_endpoint: str = "http://localhost:1234/v1/chat/completions",
    timeout: int = 30,
    num_samples: int = 20  # Increased samples for better accuracy
) -> Dict[str, Any]:
    """Run BIG-BENCH-HARD benchmarks focusing on complex reasoning tasks.
    
    Args:
        model: The model information dictionary
        api_endpoint: The LM Studio API endpoint
        timeout: API call timeout in seconds
        num_samples: Number of samples to test per task
        
    Returns:
        Dictionary containing benchmark results with focus on complex tasks
    """
    model_id = model.get("id", "unknown")
    llm = LMStudioLLM(model_id=model_id, api_endpoint=api_endpoint, timeout=timeout)
    
    # Create BigBenchHard benchmark instance with focus on complex tasks
    benchmark = BigBenchHard(
        model=llm,
        num_samples=num_samples,
        metrics=[
            HallucinationMetric(threshold=0.9),  # Stricter hallucination checking
            AnswerRelevancyMetric(threshold=0.85)  # Higher relevancy requirement
        ],
        max_parallel_requests=1,  # Force sequential execution
        task_categories=[
            "logical_reasoning",
            "algorithmic_thinking",
            "abstract_reasoning",
            "mathematics",
            "code_generation",
            "problem_solving"
        ]
    )
    
    # Run the benchmark synchronously
    results = benchmark.run()
    
    # Calculate complexity-weighted scores
    complexity_weights = {
        "logical_reasoning": 1.5,
        "algorithmic_thinking": 1.5,
        "abstract_reasoning": 1.4,
        "mathematics": 1.3,
        "code_generation": 1.2,
        "problem_solving": 1.1,
        "default": 1.0
    }
    
    weighted_tasks = []
    total_weight = 0
    weighted_sum = 0
    
    for task in results.task_results:
        # Determine the weight based on task category
        weight = 1.0
        for category, w in complexity_weights.items():
            if category in task.name.lower():
                weight = w
                break
        
        # Calculate weighted score
        weighted_score = task.score * weight
        weighted_sum += weighted_score
        total_weight += weight
        
        weighted_tasks.append({
            "task": task.name,
            "raw_score": task.score,
            "weighted_score": weighted_score,
            "weight": weight,
            "complexity_category": next(
                (cat for cat in complexity_weights.keys() if cat in task.name.lower()),
                "other"
            ),
            "metrics": {
                metric.name: metric.score 
                for metric in task.metrics
            }
        })
    
    # Calculate weighted overall score
    weighted_overall = weighted_sum / total_weight if total_weight > 0 else 0.0
    
    return {
        "bigbench_scores": {
            "overall": weighted_overall,
            "raw_overall": results.overall_score,
            "tasks": weighted_tasks,
            "complexity_focus": True,  # Flag indicating this is using complexity-weighted scoring
            "weights_used": complexity_weights
        },
        "raw_results": results.to_dict()
    }