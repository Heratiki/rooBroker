import requests
from typing import List, Dict, Any, Optional
import json
import time
from datetime import datetime
import threading
import sys
from lmstudio_modelstate import update_modelstate_json

# Enhanced rich imports for better console output
try:
    from rich.console import Console
    from rich.prompt import Prompt
    from rich.progress import Progress, TextColumn, BarColumn, TaskID
    from rich.progress import TimeElapsedColumn, TimeRemainingColumn, SpinnerColumn
    from rich.live import Live
    from rich.panel import Panel
    from rich.layout import Layout
    from rich.table import Table
    from rich.text import Text
    from rich import box
    from rich.status import Status
    console = Console()
    RICH_AVAILABLE = True
except ImportError:
    # Fallback if rich is not available
    console = None
    RICH_AVAILABLE = False

LM_STUDIO_MODELS_ENDPOINT = "http://localhost:1234/v1/models"
CHAT_COMPLETIONS_ENDPOINT = "http://localhost:1234/v1/chat/completions"

def discover_lmstudio_models(
    endpoint: str = LM_STUDIO_MODELS_ENDPOINT,
    timeout: int = 5
) -> List[Dict[str, Any]]:
    """
    Queries LM Studio for all available local models and extracts relevant metadata.

    Args:
        endpoint (str): The LM Studio models API endpoint.
        timeout (int): Timeout for the HTTP request in seconds.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries, each containing:
            - 'id' (str): Model ID or name
            - 'family' (Optional[str]): Model family, if available
            - 'context_window' (Optional[int]): Context window size, if available
    """
    try:
        response = requests.get(endpoint, timeout=timeout)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        raise RuntimeError(f"Failed to query LM Studio models endpoint: {e}")

    models = []
    for model in data.get("data", []):
        model_info = {
            "id": model.get("id") or model.get("name"),
            "family": model.get("family"),
            "context_window": model.get("context_length") or model.get("context_window"),
        }
        models.append(model_info)
    return models

def analyze_response(
    response: str,
    expected: str,
    analyzer_model: str,
    api_endpoint: str = CHAT_COMPLETIONS_ENDPOINT,
    timeout: int = 10
) -> Dict[str, Any]:
    """Analyze a model's response using another model to suggest improvements."""
    analysis_prompt = f"""Analyze this model response and suggest improvements:

Original Task Expected: {expected}
Model Response: {response}

Analyze:
1. What's missing or incorrect?
2. How could the prompt be improved?
3. Rate accuracy (0-100%)
"""
    
    try:
        payload = {
            "model": analyzer_model,
            "messages": [
                {"role": "system", "content": "You are an AI response analyst. Analyze model outputs and suggest improvements."},
                {"role": "user", "content": analysis_prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 500
        }
        resp = requests.post(api_endpoint, json=payload, timeout=timeout)
        resp.raise_for_status()
        analysis = resp.json()["choices"][0]["message"]["content"]
        
        return {
            "analysis": analysis,
            "original_response": response,
            "expected": expected
        }
    except Exception as e:
        return {
            "analysis": f"Analysis failed: {str(e)}",
            "original_response": response,
            "expected": expected
        }

def improve_prompt(
    benchmark: Dict[str, Any],
    analysis: Dict[str, Any],
    improver_model: str,
    api_endpoint: str = CHAT_COMPLETIONS_ENDPOINT,
    timeout: int = 10
) -> str:
    """Generate an improved prompt based on analysis."""
    improvement_prompt = f"""Original prompt: {benchmark['prompt']}
Expected output: {benchmark['expected']}
Previous response: {analysis['original_response']}
Analysis: {analysis['analysis']}

Generate an improved version of the original prompt that will lead to better results.
Focus on clarity, specificity, and guiding the model to the expected format.
Return only the improved prompt, no explanations."""
    
    try:
        payload = {
            "model": improver_model,
            "messages": [
                {"role": "system", "content": "You are a prompt engineer. Improve prompts to get better results."},
                {"role": "user", "content": improvement_prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 500
        }
        resp = requests.post(api_endpoint, json=payload, timeout=timeout)
        resp.raise_for_status()
        improved_prompt = resp.json()["choices"][0]["message"]["content"].strip()
        return improved_prompt
    except Exception:
        return benchmark["prompt"]  # Fall back to original prompt on error

def get_model_timeout(model: Dict[str, Any]) -> int:
    """Determine appropriate timeout based on model size/type.
    
    Args:
        model: Model information dictionary
        
    Returns:
        Timeout in seconds
    """
    model_id = model.get("id", "").lower()
    context_size = model.get("context_window", 0)
    
    # Set longer timeouts for known large models based on name
    if any(marker in model_id for marker in ["32b", "70b", "13b", "7b", "llama-3", "qwen2.5", "codellama", "mistral", "wizardcoder"]):
        return 120  # 2 minutes for large models
    
    # Or base timeout on context window size if available
    # Ensure context_size is not None before comparison
    if isinstance(context_size, (int, float)) and context_size > 8000:
        return 120  # 2 minutes for models with large context windows
    elif isinstance(context_size, (int, float)) and context_size > 4000:
        return 60   # 1 minute for medium context windows
    
    # Default timeout for smaller models
    return 30  # 30 seconds

def benchmark_lmstudio_models(
    models: List[Dict[str, Any]],
    api_endpoint: str = CHAT_COMPLETIONS_ENDPOINT,
    default_timeout: int = 30,
    max_retries: int = 2
) -> List[Dict[str, Any]]:
    """Enhanced benchmarking with adaptive prompting, state management, detailed visual feedback and user continuation prompts."""
    benchmarks = [
        {
            "name": "simple",
            "display_name": "Simple Arithmetic",
            "prompt": "What is the result of 7 * 8?",
            "system_prompt": "You are a precise calculator. Provide only the numeric result.",
            "expected": "56",
            "score_fn": lambda resp: 1.0 if "56" in resp else 0.0,
            "temperature": 0.1
        },
        {
            "name": "moderate",
            "display_name": "Function Creation",
            "prompt": "Write a Python function that returns the square of a number.",
            "system_prompt": "You are a Python programmer. Write clean, efficient code.",
            "expected": "def square(n):\n    return n * n",
            "score_fn": lambda resp: 1.0 if "def square" in resp and "return" in resp else 0.0,
            "temperature": 0.2
        },
        {
            "name": "complex",
            "display_name": "Code Refactoring",
            "prompt": "Refactor this code to use a list comprehension:\nresult = []\nfor x in range(10):\n    if x % 2 == 0:\n        result.append(x*x)",
            "system_prompt": "You are a Python expert. Provide the most concise, readable solution.",
            "expected": "[x*x for x in range(10) if x % 2 == 0]",
            "score_fn": lambda resp: 1.0 if any(
                variant in resp.replace(" ", "").replace("\n", "")
                for variant in [
                    "[x*xforxinrange(10)ifx%2==0]",
                    "[x**2forxinrange(10)ifx%2==0]",
                    "result=[x*xforxinrange(10)ifx%2==0]",
                    "result=[x**2forxinrange(10)ifx%2==0]"
                ]
            ) else 0.0,
            "temperature": 0.2
        }
    ]

    results = []
    models_to_process = models.copy()
    
    # Select analyzer and improver models
    all_model_ids = [m["id"] for m in models]
    
    if not RICH_AVAILABLE:
        # Fallback to basic console output if rich is not available
        print(f"Benchmarking {len(models)} models...")
        for i, model in enumerate(models_to_process):
            model_id = model["id"]
            context_window = model.get("context_window")
            scores = {}
            failures = 0
            prompt_improvements = {}
            
            # Get appropriate timeout for this model
            model_timeout = get_model_timeout(model)
            print(f"\nBenchmarking model {i+1}/{len(models)}: {model_id} (timeout: {model_timeout}s)")
            
            # Find suitable analyzer and improver models
            other_models = [m for m in all_model_ids if m != model_id]
            analyzer_model = other_models[0] if other_models else model_id
            improver_model = other_models[-1] if len(other_models) > 1 else analyzer_model
            
            # Run benchmarks
            for bench_idx, bench in enumerate(benchmarks):
                print(f"  Task: {bench['display_name']}")
                current_prompt = bench["prompt"]
                best_score = 0.0
                best_response = ""
                
                for attempt in range(max_retries + 1):
                    try:
                        print(f"    Attempt {attempt+1}/{max_retries+1}...")
                        
                        payload = {
                            "model": model_id,
                            "messages": [
                                {"role": "system", "content": bench["system_prompt"]},
                                {"role": "user", "content": current_prompt}
                            ],
                            "max_tokens": 500,
                            "temperature": bench["temperature"]
                        }
                        
                        resp = requests.post(api_endpoint, json=payload, timeout=model_timeout)
                        resp.raise_for_status()
                        content = resp.json()["choices"][0]["message"]["content"].strip()
                        
                        if not content:
                            score = 0.0
                            print("      Empty response")
                        else:
                            score = bench["score_fn"](content)
                            print(f"      Score: {score:.2f}")
                        
                        if score > best_score:
                            best_score = score
                            best_response = content

                        # If not perfect score and not last attempt, try to improve
                        if score < 1.0 and attempt < max_retries:
                            print("      Optimizing prompt...")
                            analysis = analyze_response(content, bench["expected"], analyzer_model, api_endpoint)
                            current_prompt = improve_prompt(bench, analysis, improver_model, api_endpoint)
                            prompt_improvements[bench["name"]] = {
                                "original_prompt": bench["prompt"],
                                "improved_prompt": current_prompt,
                                "analysis": analysis["analysis"]
                            }
                        elif score < 1.0:
                            failures += 1
                        
                    except Exception as e:
                        print(f"      Error: {str(e)}")
                        score = 0.0
                        failures += 1
                        break
                    
                    if score == 1.0:
                        print("      Perfect score achieved!")
                        break
                
                # Store final score
                scores[bench["name"]] = best_score
                print(f"    Final score: {best_score:.2f}")
            
            # Construct result for this model
            result = {
                "model_id": model_id,
                "context_window": context_window,
                "score_simple": scores.get("simple", 0.0),
                "score_moderate": scores.get("moderate", 0.0),
                "score_complex": scores.get("complex", 0.0),
                "failures": failures,
                "last_updated": datetime.utcnow().isoformat() + "Z",
                "prompt_improvements": prompt_improvements,
                "timeout_used": model_timeout  # Store the timeout used for future reference
            }
            
            # Add to results
            results.append(result)
            
            # Update state after each model
            try:
                print("  Saving model state...")
                update_modelstate_json([result])
                print(f"  State updated for {model_id}")
            except Exception as e:
                print(f"  Warning: Failed to update model state: {str(e)}")
            
            # Print summary
            print("\nSummary:")
            print(f"  Simple Arithmetic: {scores.get('simple', 0.0):.2f}")
            print(f"  Function Creation: {scores.get('moderate', 0.0):.2f}")
            print(f"  Code Refactoring: {scores.get('complex', 0.0):.2f}")
            overall = (scores.get('simple', 0.0) + scores.get('moderate', 0.0) + scores.get('complex', 0.0))/3
            print(f"  Overall: {overall:.2f}")
            
            # If this is not the last model, ask user if they want to continue
            if i < len(models_to_process) - 1:
                continue_benchmarking = ask_continue_with_timeout(5)
                if not continue_benchmarking:
                    print("Stopping benchmarking at user's request")
                    break
            
    else:
        # Enhanced rich UI with a SINGLE live display for everything
        # Create a layout to hold all UI components
        layout = Layout()
        layout.split(
            Layout(name="header", size=1),
            Layout(name="progress", size=3),
            Layout(name="content", ratio=1),
            Layout(name="footer", size=1)
        )
        
        # Setup progress display
        progress_table = Table.grid()
        progress_table.add_row("[bold cyan]Overall Progress[/bold cyan]")
        overall_progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            TimeRemainingColumn()
        )
        overall_task_id = overall_progress.add_task(f"[bold cyan]Benchmarking {len(models)} models...", total=len(models))
        
        model_progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn()
        )
        progress_table.add_row(overall_progress)
        progress_table.add_row(model_progress)
        layout["progress"].update(progress_table)
        
        # Prepare benchmark table placeholder
        bench_table = Table(title="Waiting to start benchmarks...", box=box.ROUNDED)
        layout["content"].update(bench_table)
        
        # Status message placeholder
        layout["footer"].update(Text("Initializing..."))
        
        # Start the live display with our layout
        with Live(layout, console=console, refresh_per_second=4) as live:
            for i, model in enumerate(models_to_process):
                model_id = model["id"]
                context_window = model.get("context_window")
                scores = {}
                failures = 0
                prompt_improvements = {}
                
                # Update header
                layout["header"].update(f"[bold blue]Model {i+1}/{len(models)}: {model_id}[/bold blue]")
                
                # Create task for this specific model
                model_task_id = model_progress.add_task(
                    f"Current model progress", 
                    total=len(benchmarks)
                )
                
                # Get appropriate timeout for this model
                model_timeout = get_model_timeout(model)
                
                # Find suitable analyzer and improver models
                other_models = [m for m in all_model_ids if m != model_id]
                analyzer_model = other_models[0] if other_models else model_id
                improver_model = other_models[-1] if len(other_models) > 1 else analyzer_model
                
                # Initialize bench_rows to track state
                bench_rows = []
                for bench in benchmarks:
                    bench_rows.append([
                        bench["display_name"], 
                        "Pending", 
                        "0.0", 
                        "0", 
                        "Waiting to start..."
                    ])
                
                # Create initial benchmark table
                bench_table = Table(title=f"Benchmarking {model_id}", box=box.ROUNDED)
                bench_table.add_column("Task", style="cyan")
                bench_table.add_column("Status", style="yellow")
                bench_table.add_column("Score", style="green")
                bench_table.add_column("Attempts", style="magenta")
                bench_table.add_column("Details", style="blue")
                
                # Add all rows to the table
                for row in bench_rows:
                    bench_table.add_row(*row)
                
                # Update the display with our table
                layout["content"].update(bench_table)
                
                # Run each benchmark for this model
                for bench_idx, bench in enumerate(benchmarks):
                    current_prompt = bench["prompt"]
                    best_score = 0.0
                    best_response = ""
                    
                    # Update table to show we're starting this benchmark
                    bench_rows[bench_idx][1] = "Running"
                    bench_rows[bench_idx][4] = "Starting benchmark..."
                    
                    # Create new table with updated data
                    new_table = Table(title=f"Benchmarking {model_id}", box=box.ROUNDED)
                    new_table.add_column("Task", style="cyan")
                    new_table.add_column("Status", style="yellow")
                    new_table.add_column("Score", style="green")
                    new_table.add_column("Attempts", style="magenta")
                    new_table.add_column("Details", style="blue")
                    
                    for row in bench_rows:
                        new_table.add_row(*row)
                    
                    layout["content"].update(new_table)
                    bench_table = new_table
                    
                    attempt_start_time = time.time()
                    for attempt in range(max_retries + 1):
                        try:
                            # Update table to show current attempt
                            bench_rows[bench_idx][3] = f"{attempt+1}/{max_retries+1}"
                            bench_rows[bench_idx][4] = "Sending request..."
                            
                            # Create new table with updated data
                            new_table = Table(title=f"Benchmarking {model_id}", box=box.ROUNDED)
                            new_table.add_column("Task", style="cyan")
                            new_table.add_column("Status", style="yellow")
                            new_table.add_column("Score", style="green")
                            new_table.add_column("Attempts", style="magenta")
                            new_table.add_column("Details", style="blue")
                            
                            for row in bench_rows:
                                new_table.add_row(*row)
                            
                            layout["content"].update(new_table)
                            bench_table = new_table
                            
                            payload = {
                                "model": model_id,
                                "messages": [
                                    {"role": "system", "content": bench["system_prompt"]},
                                    {"role": "user", "content": current_prompt}
                                ],
                                "max_tokens": 500,
                                "temperature": bench["temperature"]
                            }
                            
                            # Update status while waiting for response
                            bench_rows[bench_idx][4] = "Waiting for response..."
                            
                            # Create new table with updated data
                            new_table = Table(title=f"Benchmarking {model_id}", box=box.ROUNDED)
                            new_table.add_column("Task", style="cyan")
                            new_table.add_column("Status", style="yellow")
                            new_table.add_column("Score", style="green")
                            new_table.add_column("Attempts", style="magenta")
                            new_table.add_column("Details", style="blue")
                            
                            for row in bench_rows:
                                new_table.add_row(*row)
                            
                            layout["content"].update(new_table)
                            bench_table = new_table
                            
                            resp = requests.post(api_endpoint, json=payload, timeout=model_timeout)
                            resp.raise_for_status()
                            content = resp.json()["choices"][0]["message"]["content"].strip()
                            
                            # Calculate score
                            if not content:
                                score = 0.0
                                bench_rows[bench_idx][4] = "Empty response"
                            else:
                                score = bench["score_fn"](content)
                                response_preview = content.replace("\n", "\\n")[:30] + ("..." if len(content) > 30 else "")
                                bench_rows[bench_idx][4] = f"Response: {response_preview}"
                            
                            bench_rows[bench_idx][2] = f"{score:.2f}"
                            
                            # Create new table with updated data
                            new_table = Table(title=f"Benchmarking {model_id}", box=box.ROUNDED)
                            new_table.add_column("Task", style="cyan")
                            new_table.add_column("Status", style="yellow")
                            new_table.add_column("Score", style="green")
                            new_table.add_column("Attempts", style="magenta")
                            new_table.add_column("Details", style="blue")
                            
                            for row in bench_rows:
                                new_table.add_row(*row)
                            
                            layout["content"].update(new_table)
                            bench_table = new_table
                            
                            if score > best_score:
                                best_score = score
                                best_response = content

                            # If not perfect score and not last attempt, try to improve
                            if score < 1.0 and attempt < max_retries:
                                bench_rows[bench_idx][1] = "Optimizing"
                                bench_rows[bench_idx][4] = "Analyzing response for improvements..."
                                
                                # Create new table with updated data
                                new_table = Table(title=f"Benchmarking {model_id}", box=box.ROUNDED)
                                new_table.add_column("Task", style="cyan")
                                new_table.add_column("Status", style="yellow")
                                new_table.add_column("Score", style="green")
                                new_table.add_column("Attempts", style="magenta")
                                new_table.add_column("Details", style="blue")
                                
                                for row in bench_rows:
                                    new_table.add_row(*row)
                                
                                layout["content"].update(new_table)
                                bench_table = new_table
                                
                                analysis = analyze_response(content, bench["expected"], analyzer_model, api_endpoint)
                                bench_rows[bench_idx][4] = "Generating improved prompt..."
                                
                                # Create new table with updated data
                                new_table = Table(title=f"Benchmarking {model_id}", box=box.ROUNDED)
                                new_table.add_column("Task", style="cyan")
                                new_table.add_column("Status", style="yellow")
                                new_table.add_column("Score", style="green")
                                new_table.add_column("Attempts", style="magenta")
                                new_table.add_column("Details", style="blue")
                                
                                for row in bench_rows:
                                    new_table.add_row(*row)
                                
                                layout["content"].update(new_table)
                                bench_table = new_table
                                
                                current_prompt = improve_prompt(bench, analysis, improver_model, api_endpoint)
                                prompt_improvements[bench["name"]] = {
                                    "original_prompt": bench["prompt"],
                                    "improved_prompt": current_prompt,
                                    "analysis": analysis["analysis"]
                                }
                                
                                # Extract a short analysis preview
                                analysis_preview = analysis["analysis"].replace("\n", " ")[:50] + "..."
                                bench_rows[bench_idx][4] = f"Optimizing: {analysis_preview}"
                                
                                # Create new table with updated data
                                new_table = Table(title=f"Benchmarking {model_id}", box=box.ROUNDED)
                                new_table.add_column("Task", style="cyan")
                                new_table.add_column("Status", style="yellow")
                                new_table.add_column("Score", style="green")
                                new_table.add_column("Attempts", style="magenta")
                                new_table.add_column("Details", style="blue")
                                
                                for row in bench_rows:
                                    new_table.add_row(*row)
                                
                                layout["content"].update(new_table)
                                bench_table = new_table
                            elif score < 1.0:
                                failures += 1
                            
                        except Exception as e:
                            error_msg = str(e)[:50] + ("..." if len(str(e)) > 50 else "")
                            bench_rows[bench_idx][1] = "Error"
                            bench_rows[bench_idx][2] = "0.0"
                            bench_rows[bench_idx][4] = f"Error: {error_msg}"
                            
                            # Create new table with updated data
                            new_table = Table(title=f"Benchmarking {model_id}", box=box.ROUNDED)
                            new_table.add_column("Task", style="cyan")
                            new_table.add_column("Status", style="yellow")
                            new_table.add_column("Score", style="green")
                            new_table.add_column("Attempts", style="magenta")
                            new_table.add_column("Details", style="blue")
                            
                            for row in bench_rows:
                                new_table.add_row(*row)
                            
                            layout["content"].update(new_table)
                            bench_table = new_table
                            
                            score = 0.0
                            failures += 1
                            break
                        
                        # If perfect score, break early
                        if score == 1.0:
                            bench_rows[bench_idx][1] = "Success"
                            bench_rows[bench_idx][4] = f"Perfect score achieved in {attempt+1} attempts!"
                            
                            # Create new table with updated data
                            new_table = Table(title=f"Benchmarking {model_id}", box=box.ROUNDED)
                            new_table.add_column("Task", style="cyan")
                            new_table.add_column("Status", style="yellow")
                            new_table.add_column("Score", style="green")
                            new_table.add_column("Attempts", style="magenta")
                            new_table.add_column("Details", style="blue")
                            
                            for row in bench_rows:
                                new_table.add_row(*row)
                            
                            layout["content"].update(new_table)
                            bench_table = new_table
                            
                            break
                    
                    # Store final score
                    scores[bench["name"]] = best_score
                    
                    # Update benchmark status
                    if best_score == 1.0:
                        bench_rows[bench_idx][1] = "✅ Success"
                    elif best_score > 0.0:
                        bench_rows[bench_idx][1] = "⚠️ Partial"
                    else:
                        bench_rows[bench_idx][1] = "❌ Failed"
                        
                    # Calculate elapsed time
                    elapsed = time.time() - attempt_start_time
                    bench_rows[bench_idx][4] += f" (took {elapsed:.1f}s)"
                    
                    # Create new table with updated data
                    new_table = Table(title=f"Benchmarking {model_id}", box=box.ROUNDED)
                    new_table.add_column("Task", style="cyan")
                    new_table.add_column("Status", style="yellow")
                    new_table.add_column("Score", style="green")
                    new_table.add_column("Attempts", style="magenta")
                    new_table.add_column("Details", style="blue")
                    
                    for row in bench_rows:
                        new_table.add_row(*row)
                    
                    layout["content"].update(new_table)
                    bench_table = new_table
                    
                    # Update progress
                    model_progress.update(model_task_id, advance=1)
                
                # Construct result for this model
                result = {
                    "model_id": model_id,
                    "context_window": context_window,
                    "score_simple": scores.get("simple", 0.0),
                    "score_moderate": scores.get("moderate", 0.0),
                    "score_complex": scores.get("complex", 0.0),
                    "failures": failures,
                    "last_updated": datetime.utcnow().isoformat() + "Z",
                    "prompt_improvements": prompt_improvements,
                    "timeout_used": model_timeout  # Store the timeout used for future reference
                }
                
                # Add to results
                results.append(result)
                
                # Update state after each model
                layout["footer"].update("[bold green]Saving model state...[/bold green]")
                try:
                    update_modelstate_json([result])
                    layout["footer"].update(f"[green]✓ State updated for {model_id}[/green]")
                except Exception as e:
                    layout["footer"].update(f"[yellow]⚠ Warning: Failed to update model state: {str(e)}[/yellow]")
                
                # Update overall progress
                overall_progress.update(overall_task_id, advance=1)
                
                # Show summary for this model
                summary_table = Table(title=f"Summary for {model_id}", box=box.SIMPLE)
                summary_table.add_column("Task", style="cyan")
                summary_table.add_column("Score", style="green")
                summary_table.add_row("Simple Arithmetic", f"{scores.get('simple', 0.0):.2f}")
                summary_table.add_row("Function Creation", f"{scores.get('moderate', 0.0):.2f}")
                summary_table.add_row("Code Refactoring", f"{scores.get('complex', 0.0):.2f}")
                summary_table.add_row("Overall", f"{(scores.get('simple', 0.0) + scores.get('moderate', 0.0) + scores.get('complex', 0.0))/3:.2f}")
                
                layout["content"].update(summary_table)
                
                # If this is not the last model, ask user if they want to continue
                if i < len(models_to_process) - 1:
                    layout["footer"].update("[yellow]Waiting for user input...[/yellow]")
                    # Need to temporarily exit Live context to get user input
                    live.stop()
                    continue_benchmarking = ask_continue_with_timeout(5)
                    live.start()
                    
                    if not continue_benchmarking:
                        layout["footer"].update("[yellow]Stopping benchmarking at user's request[/yellow]")
                        # Update progress to complete (skip remaining models)
                        overall_progress.update(overall_task_id, completed=len(models))
                        break
                    else:
                        # Reset the model progress for next model
                        model_progress.stop_task(model_task_id)
                        model_progress.remove_task(model_task_id)
                
    return results

def ask_continue_with_timeout(timeout_seconds=15):
    """Ask the user if they want to continue with a timeout default of True."""
    user_input = [True]  # Default to continue
    timer_expired = [False]
    
    def input_thread():
        if console:
            response = Prompt.ask(
                f"Continue with next model? [Y/n] (continues in {timeout_seconds}s)", 
                default="y"
            ).lower()
            user_input[0] = response != "n"
        else:
            response = input(f"Continue with next model? [Y/n] (continues in {timeout_seconds}s): ").lower()
            user_input[0] = response != "n"
    
    def timer_thread():
        for i in range(timeout_seconds, 0, -1):
            if timer_expired[0]:
                return
            sys.stdout.write(f"\rContinuing in {i}s... (press Enter to respond) ")
            sys.stdout.flush()
            time.sleep(1)
        timer_expired[0] = True
        sys.stdout.write("\r" + " " * 50 + "\r")  # Clear the line
        sys.stdout.flush()
    
    input_t = threading.Thread(target=input_thread)
    input_t.daemon = True
    
    timer_t = threading.Thread(target=timer_thread)
    timer_t.daemon = True
    
    timer_t.start()
    input_t.start()
    
    input_t.join(timeout_seconds)
    timer_expired[0] = True  # Signal timer to stop
    
    return user_input[0]

# Example usage (for testing/debugging only):
if __name__ == "__main__":
    try:
        models = discover_lmstudio_models()
        for m in models:
            print(m)
    except Exception as err:
        print(f"Error: {err}")