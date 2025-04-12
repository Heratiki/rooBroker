from typing import List, Dict, Any, Optional
import requests
import time
import traceback
from rich.console import Console  # Import Console
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

    def load_model(self):
        """Placeholder for the abstract method. LM Studio handles loading externally."""
        # Since LM Studio manages loading, we just return the instance.
        # Alternatively, could add a check here to see if the model is available via API.
        return self

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
    num_samples: int = 20,  # Increased samples for better accuracy
    console: Optional[Console] = None  # Add console parameter
) -> Dict[str, Any]:
    """Run BIG-BENCH-HARD benchmarks focusing on complex reasoning tasks."""
    model_id = model.get("id", "unknown")
    model_timeout = timeout  # Explicitly define model_timeout for DeepEval 2.7.1+ compatibility
    
    # Use console.print if available, otherwise use standard print
    print_func = console.print if console else print
    
    print_func(f"\n[cyan]Starting BIG-BENCH-HARD benchmarks for {model_id}...[/cyan]")
    llm = LMStudioLLM(model_id=model_id, api_endpoint=api_endpoint, timeout=timeout)
    
    # Add warning about potential dataset download
    print_func("[yellow]Initializing BIG-BENCH-HARD. This may download datasets if run for the first time...[/yellow]")
    
    # Create BigBenchHard benchmark instance with focus on complex tasks
    print_func("[cyan]Initializing benchmark tasks...[/cyan]")
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
    try:
        print_func("[yellow]Running BIG-BENCH-HARD tasks (this may take several minutes)...[/yellow]")
        start_time = time.time()
        # Add a print right before the blocking call
        print_func("[yellow]Invoking benchmark.run()...[/yellow]")
        results = benchmark.run()
        end_time = time.time()
        # Add a clear success message
        print_func(f"[bold green]>>> BIG-BENCH-HARD benchmark.run() completed successfully for {model_id} in {end_time - start_time:.1f} seconds <<<[/bold green]")
        
        print_func("[cyan]Processing results...[/cyan]")
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
            # Print progress for each task
            print_func(f"  Evaluating task: {task.name}")
            
            # Determine the weight based on task category
            weight = complexity_weights.get('default', 1.0)
            task_name = task.name.lower()
            for category, w in complexity_weights.items():
                if category.replace('_', '') in task_name:
                    weight = w
                    break
            
            # Calculate weighted score
            weighted_score = task.score * weight
            weighted_sum += weighted_score
            total_weight += weight
            
            # Get metrics scores
            metric_scores = {
                metric.name: metric.score 
                for metric in task.metrics
            }
            
            # Determine task category
            category = 'other'
            for cat in complexity_weights.keys():
                if cat.replace('_', '') in task_name:
                    category = cat
                    break
            
            weighted_tasks.append({
                "task": task.name,
                "raw_score": task.score,
                "weighted_score": weighted_score,
                "weight": weight,
                "complexity_category": category,
                "metrics": metric_scores
            })
            
            # Print task results
            print_func(f"    Score: {task.score:.2f} (weighted: {weighted_score:.2f})")
        
        # Calculate weighted overall score
        weighted_overall = weighted_sum / total_weight if total_weight > 0 else 0.0
        print_func(f"\n[bold green]BIG-BENCH-HARD Overall Score: {weighted_overall:.2f}[/bold green]")
        
        return {
            "bigbench_scores": {
                "overall": weighted_overall,
                "raw_overall": results.overall_score,
                "tasks": weighted_tasks,
                "complexity_focus": True,
                "weights_used": complexity_weights,
                "benchmark_duration": end_time - start_time
            },
            "predictions": results.predictions,
            "raw_results": results.to_dict()
        }
    except Exception as e:
        # Use standard print for critical errors to ensure visibility
        print(f"\nCRITICAL ERROR in BIG-BENCH-HARD benchmark for {model_id}: {str(e)}")
        traceback.print_exc()  # Print full traceback
        print_func(f"[bold red]Error during BIG-BENCH-HARD execution. Check logs.[/bold red]")
        return None