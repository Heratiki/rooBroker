from typing import List, Dict, Any, Optional
import requests
import time
import traceback
from rich.console import Console
from rich.progress import Progress, TextColumn, BarColumn, TimeElapsedColumn, TimeRemainingColumn, SpinnerColumn
from rich.table import Table
from rich.panel import Panel
from rich import box
from deepeval.models.base_model import DeepEvalBaseLLM
from deepeval.metrics import HallucinationMetric, AnswerRelevancyMetric
from deepeval.benchmarks.big_bench_hard.big_bench_hard import BigBenchHard

# Define task categories and their display names
TASK_CATEGORIES = {
    "logical_reasoning": "Logical Reasoning",
    "algorithmic_thinking": "Algorithmic Thinking", 
    "abstract_reasoning": "Abstract Reasoning",
    "mathematics": "Mathematics",
    "code_generation": "Code Generation",
    "problem_solving": "Problem Solving"
}

# Define complexity weights for scoring
COMPLEXITY_WEIGHTS = {
    "logical_reasoning": 1.5,
    "algorithmic_thinking": 1.5,
    "abstract_reasoning": 1.4,
    "mathematics": 1.3,
    "code_generation": 1.2,
    "problem_solving": 1.1,
    "default": 1.0
}

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
    
    # Use console if provided, otherwise create a new one
    if not console:
        console = Console()
    
    # Create a progress display for initialization steps
    init_progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console
    )
    
    with init_progress as progress:
        init_task = progress.add_task("[cyan]Initializing BIG-BENCH-HARD benchmark...", total=3)
        
        # Step 1: Initialize model wrapper
        console.print(f"\n[bold cyan]Preparing BIG-BENCH-HARD benchmarks for {model_id}[/bold cyan]")
        llm = LMStudioLLM(model_id=model_id, api_endpoint=api_endpoint, timeout=timeout)
        progress.update(init_task, advance=1, description="[cyan]Initializing LM Studio model wrapper...")
        
        # Step 2: Setup benchmark tasks
        progress.update(init_task, advance=1, description="[cyan]Configuring benchmark tasks...")
        benchmark = BigBenchHard(
            model=llm,
            num_samples=num_samples,
            metrics=[
                HallucinationMetric(threshold=0.9),  # Stricter hallucination checking
                AnswerRelevancyMetric(threshold=0.85)  # Higher relevancy requirement
            ],
            max_parallel_requests=1,  # Force sequential execution
            task_categories=list(TASK_CATEGORIES.keys())  # Use predefined task categories
        )
        
        # Step 3: Ready to run
        progress.update(init_task, advance=1, description="[cyan]Setup complete, ready to run...")
    
    # Show detailed information about what will be tested
    info_table = Table(title="BIG-BENCH-HARD Benchmark Configuration", box=box.SIMPLE)
    info_table.add_column("Setting", style="cyan")
    info_table.add_column("Value", style="yellow")
    
    info_table.add_row("Model ID", model_id)
    info_table.add_row("Samples per task", str(num_samples))
    info_table.add_row("API Timeout", f"{timeout}s")
    info_table.add_row("Categories", ", ".join([TASK_CATEGORIES[cat] for cat in TASK_CATEGORIES]))
    
    console.print(info_table)
    console.print("\n[yellow]Running BIG-BENCH-HARD tasks (this may take several minutes)...[/yellow]")
    console.print("[yellow]Note: The benchmark will run various reasoning tasks to evaluate the model's capabilities.[/yellow]")
    
    try:
        # Use simple status instead of live display to avoid nesting issues
        console.print("[bold cyan]Running benchmark tasks...[/bold cyan]")
        start_time = time.time()
        
        # Run the benchmark (this is a blocking call)
        console.print("[bold yellow]Executing benchmark.run() - please wait...[/bold yellow]")
        results = benchmark.run()
        end_time = time.time()
        
        # Signal completion
        console.print("[bold green]Benchmark execution complete![/bold green]")
        
        # Process results with a progress display
        console.print("\n[cyan]Processing and analyzing benchmark results...[/cyan]")
        
        # Initialize results table
        results_table = Table(
            title=f"BIG-BENCH-HARD Results for {model_id}",
            box=box.SIMPLE,
            highlight=True
        )
        results_table.add_column("Category", style="cyan")
        results_table.add_column("Task", style="yellow")
        results_table.add_column("Raw Score", style="green")
        results_table.add_column("Weight", style="magenta")
        results_table.add_column("Weighted", style="red")
        
        # Track category scores and weights for final calculation
        category_scores = {cat: [] for cat in TASK_CATEGORIES}
        weighted_tasks = []
        total_weight = 0
        weighted_sum = 0
        
        # Process each task result with simple progress output, not using Live display
        console.print("[cyan]Processing benchmark results...[/cyan]")
        for i, task in enumerate(results.task_results):
            task_name = task.name
            console.print(f"[cyan]Processing task {i+1}/{len(results.task_results)}: {task_name}[/cyan]")
            
            # Determine the category and weight
            category = 'other'
            for cat in COMPLEXITY_WEIGHTS:
                if cat != 'default' and cat.replace('_', '') in task_name.lower():
                    category = cat
                    break
            
            # Get the display name for the category
            display_category = TASK_CATEGORIES.get(category, "Other")
            
            # Get the weight for this task based on category
            weight = COMPLEXITY_WEIGHTS.get(category, COMPLEXITY_WEIGHTS['default'])
            
            # Calculate weighted score
            weighted_score = task.score * weight
            weighted_sum += weighted_score
            total_weight += weight
            
            # Add to category scores for averaging
            if category in category_scores:
                category_scores[category].append(weighted_score)
            
            # Collect metrics
            metric_scores = {
                metric.name: metric.score 
                for metric in task.metrics
            }
            
            # Add to results table
            results_table.add_row(
                display_category,
                task_name,
                f"{task.score:.2f}",
                f"{weight:.1f}x",
                f"{weighted_score:.2f}"
            )
            
            # Store task result
            weighted_tasks.append({
                "task": task_name,
                "raw_score": task.score,
                "weighted_score": weighted_score,
                "weight": weight,
                "complexity_category": category,
                "metrics": metric_scores
            })
        
        # Calculate final weighted score
        weighted_overall = weighted_sum / total_weight if total_weight > 0 else 0.0
        
        # Print the results table
        console.print(results_table)
        
        # Create and print a summary table
        summary_table = Table(title="Category Summary", box=box.SIMPLE)
        summary_table.add_column("Category", style="cyan")
        summary_table.add_column("Avg Score", style="green")
        summary_table.add_column("Weight", style="yellow")
        summary_table.add_column("Tasks", style="magenta")
        
        for category, scores in category_scores.items():
            if scores:  # Only show categories with scores
                avg_score = sum(scores) / len(scores)
                display_name = TASK_CATEGORIES.get(category, category)
                weight = COMPLEXITY_WEIGHTS.get(category, 1.0)
                summary_table.add_row(
                    display_name,
                    f"{avg_score:.2f}",
                    f"{weight:.1f}x",
                    str(len(scores))
                )
        
        # Add overall score row
        summary_table.add_row(
            "[bold]Overall[/bold]",
            f"[bold]{weighted_overall:.2f}[/bold]",
            "-",
            str(len(weighted_tasks))
        )
        
        # Print summary and benchmark duration
        console.print(summary_table)
        benchmark_duration = end_time - start_time
        console.print(f"\n[bold green]Benchmark completed in {benchmark_duration:.1f} seconds[/bold green]")
        
        # Return the structured results
        return {
            "bigbench_scores": {
                "overall": weighted_overall,
                "raw_overall": results.overall_score,
                "tasks": weighted_tasks,
                "complexity_focus": True,
                "weights_used": COMPLEXITY_WEIGHTS,
                "benchmark_duration": benchmark_duration
            },
            "predictions": results.predictions,
            "raw_results": results.to_dict()
        }
    except Exception as e:
        # Use standard print for critical errors to ensure visibility
        print(f"\nCRITICAL ERROR in BIG-BENCH-HARD benchmark for {model_id}: {str(e)}")
        traceback.print_exc()  # Print full traceback
        console.print(f"[bold red]Error during BIG-BENCH-HARD execution: {str(e)}[/bold red]")
        return None