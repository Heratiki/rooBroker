from typing import List, Dict, Any, Optional
import requests
from deepeval import DeepEvalBaseLLM
from deepeval.benchmarks import BIGBENCH, BIGBENCHTask

class LMStudioLLM(DeepEvalBaseLLM):
    """LM Studio model wrapper for DeepEval benchmarking."""
    
    def __init__(self, model_id: str, api_endpoint: str = "http://localhost:1234/v1/chat/completions", timeout: int = 30):
        """Initialize the LM Studio model wrapper.
        
        Args:
            model_id: The ID of the model in LM Studio
            api_endpoint: The endpoint URL for LM Studio's API
            timeout: Timeout in seconds for API calls
        """
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
    tasks: Optional[List[BIGBENCHTask]] = None
) -> Dict[str, Any]:
    """Run BIG-BENCH-HARD benchmarks on an LM Studio model.
    
    Args:
        model: The model information dictionary
        api_endpoint: The LM Studio API endpoint
        timeout: API call timeout in seconds
        tasks: Optional list of specific BIG-BENCH tasks to run
        
    Returns:
        Dictionary containing benchmark results
    """
    model_id = model.get("id", "unknown")
    llm = LMStudioLLM(model_id=model_id, api_endpoint=api_endpoint, timeout=timeout)
    
    # Create BIGBENCH benchmark instance with specified tasks
    benchmark = BIGBENCH(llm=llm, tasks=tasks)
    
    # Run the benchmark
    benchmark.run()
    
    # Convert scores to our format
    results = {
        "bigbench_scores": {
            "overall": benchmark.overall_score,
            "tasks": benchmark.task_scores.to_dict('records')
        },
        "predictions": benchmark.predictions.to_dict('records')
    }
    
    return results