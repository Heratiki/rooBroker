"""
Benchmarking LM Studio models with optional UI and adaptive prompting.
"""
from typing import List, Dict, Any, cast
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
from .deepeval import benchmark_with_bigbench
from .config import console, rich_available, Prompt, Progress, TextColumn, BarColumn, TimeElapsedColumn, TimeRemainingColumn, SpinnerColumn, Live, Layout, Table, Text, box, CHAT_COMPLETIONS_ENDPOINT
from rich.console import Console  # import class for fallback
from .promptwizard import PromptWizard


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
    run_bigbench: bool = True
) -> List[Dict[str, Any]]:
    """Run defined benchmarks on each LM Studio model."""
    benchmarks: List[Dict[str, Any]] = [
        {"name": "simple", "prompt": "What is the result of 7 * 8?", "system_prompt": "You are a precise calculator. Provide only the numeric result.", "expected": "56", "temperature": 0.1},
        {"name": "moderate", "prompt": "Write a Python function that returns the square of a number.", "system_prompt": "You are a Python programmer. Write clean, efficient code.", "expected": "def square(n):\n    return n * n", "temperature": 0.2},
        {"name": "complex", "prompt": "Refactor this code to use a list comprehension:\nresult=[]\nfor x in range(10):\n    if x%2==0: result.append(x*x)", "system_prompt": "You are a Python expert. Provide the most concise, readable solution.", "expected": "[x*x for x in range(10) if x%2==0]", "temperature": 0.2},
        {"name": "context_window", "prompt": "".join([f"Para {i} number={i*10+7}.\n" for i in range(1,21)]) + "Q: number in para 7?", "system_prompt": "You are a helpful assistant. Answer accurately.", "expected": "77", "temperature": 0.1}
    ]

    results: List[Dict[str, Any]] = []
    all_ids = [m["id"] for m in models]
    # Show progress bar for standard benchmarks
    total_tasks = len(models) * len(benchmarks)
    completed_tasks = 0
    header = Text(f"Progress: {completed_tasks}/{total_tasks} tasks", style="bold magenta")
    table = Table(box=box.SIMPLE_HEAVY)
    table.add_column("Model ID", style="cyan", no_wrap=True)
    table.add_column("Benchmark", style="green")
    table.add_column("Attempt", style="yellow")
    table.add_column("Status", style="white")
    table.add_column("Score", style="bold")
    table.add_column("PromptWizard Activity", style="dim")
    layout = Layout()
    layout.split(
        Layout(header, name="header", size=3),
        Layout(table, name="body")
    )
    live = Live(layout, console=console, refresh_per_second=2)
    live.start()
    for idx, model in enumerate(models):
        model_id: str = model["id"]
        timeout_sec = get_model_timeout(model)
        other_ids = [mid for mid in all_ids if mid != model_id]
        analyzer = other_ids[0] if other_ids else model_id
        improver = other_ids[-1] if other_ids else analyzer

        model_result: Dict[str, Any] = {"model_id": model_id, "context_window": model.get("context_window", None), "failures": 0, "last_updated": datetime.now(timezone.utc).isoformat().replace('+00:00','Z'), "timeout_used": timeout_sec}
        scores: Dict[str, float] = {}
        prompt_impr: Dict[str, Any] = {}

        for bench in benchmarks:
            # Create a PromptWizard for more structured prompt refinement
            wizard_console = console if console else Console()
            wizard = PromptWizard(bench['name'], model_id, wizard_console)
            # Iteratively refine the prompt zero‐shot before running
            original_prompt = bench['prompt']
            bench['prompt'] = wizard.iterative_zero_shot_refine(
                original_prompt,
                bench['expected'],
                improver,
                api_endpoint=CHAT_COMPLETIONS_ENDPOINT
            )
            # Advance progress and update description per benchmark
            # Inform user about request phase
            if console:
                console.print(f"[blue]→ Sending request for '{bench['name']}' on model {model_id}[/blue]")
            best_score = 0.0; best_resp = ''
            prompt = bench["prompt"]
            attempt = 0  # Initialize attempt for type safety
            for attempt in range(max_retries+1):
                if console:
                    console.print(f"[blue]Attempt {attempt+1}/{max_retries+1} for '{bench['name']}'[/blue]")
                auth_resp = call_lmstudio_with_max_context(model_id, [{"role":"system","content":bench["system_prompt"]},{"role":"user","content":prompt}], timeout=timeout_sec, temperature=bench["temperature"], max_tokens=500)
                if console:
                    console.print(f"[blue]← Received response for '{bench['name']}' (model {model_id})[/blue]")
                text = auth_resp.get("choices", [])[0].get("message",{}).get("content","").strip()
                score = bench.get("score_fn", lambda r: 1.0 if bench["expected"] in r else 0.0)(text) if bench.get("score_fn") else (1.0 if bench["expected"] in text else 0.0)
                if console:
                    console.print(f"[green]Scored {score:.2f} for '{bench['name']}'[/green]")
                if score > best_score:
                    best_score, best_resp = score, text
                if score < 1.0 and attempt < max_retries:
                    if console:
                        console.print(f"[yellow]Improving prompt for '{bench['name']}' based on response...[/yellow]")
                    # Use PromptWizard for critique and synthesis phases
                    prompt = wizard.refine(prompt, text, bench['expected'], analyzer, improver)
                    prompt_impr[bench['name']] = {'analysis': wizard.history[-1]['critique']['analysis'], 'improved_prompt': wizard.history[-1]['new_prompt']}
                elif score < 1.0:
                    model_result["failures"] += 1
                if score == 1.0:
                    break
            final_attempt = attempt + 1
            final_score = best_score
            prompt_activity = ""
            if bench["name"] in prompt_impr:
                prompt_activity = f"Analysis: {prompt_impr[bench['name']]['analysis']} | New Prompt: {prompt_impr[bench['name']]['improved_prompt']}"
            table.add_row(model_id, bench["name"], f"{final_attempt}/{max_retries+1}", "Completed", f"{final_score:.2f}", prompt_activity)
            completed_tasks += 1
            layout["header"].update(Text(f"Progress: {completed_tasks}/{total_tasks} tasks", style="bold magenta"))
            live.refresh()
            scores[bench["name"]] = best_score
            model_result[f"score_{bench['name']}"] = best_score

        if run_bigbench:
            try:
                bb = benchmark_with_bigbench(model, timeout=get_model_timeout(model))
                if bb is not None:
                    model_result["bigbench_scores"] = bb.get("bigbench_scores", {})
                    model_result["bigbench_predictions"] = bb.get("predictions", [])
            except Exception:
                pass

        model_result["prompt_improvements"] = prompt_impr
        results.append(model_result)
        update_modelstate_json(cast(List[ModelState], [model_result]))
        if idx < len(models)-1 and not ask_continue_with_timeout(5):
            break
    return results
