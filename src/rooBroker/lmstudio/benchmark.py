"""
Benchmarking LM Studio models with optional UI and adaptive prompting.
"""
from typing import List, Dict, Any
import time
from datetime import datetime, timezone
import threading
import sys

from lmstudio_client import call_lmstudio_with_max_context
from lmstudio_analysis import analyze_response, improve_prompt
from lmstudio_timeout import get_model_timeout
from lmstudio_modelstate import update_modelstate_json
from lmstudio_deepeval import benchmark_with_bigbench
from lmstudio_config import console, rich_available, Prompt, Progress, TextColumn, BarColumn, TimeElapsedColumn, TimeRemainingColumn, SpinnerColumn, Live, Layout, Table, Text, box


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
            best_score = 0.0; best_resp = ''
            prompt = bench["prompt"]
            for attempt in range(max_retries+1):
                auth_resp = call_lmstudio_with_max_context(model_id, [{"role":"system","content":bench["system_prompt"]},{"role":"user","content":prompt}], timeout=timeout_sec, temperature=bench["temperature"], max_tokens=500)
                text = auth_resp.get("choices", [])[0].get("message",{}).get("content","").strip()
                score = bench.get("score_fn", lambda r: 1.0 if bench["expected"] in r else 0.0)(text) if bench.get("score_fn") else (1.0 if bench["expected"] in text else 0.0)
                if score > best_score:
                    best_score, best_resp = score, text
                if score < 1.0 and attempt < max_retries:
                    analysis = analyze_response(text, bench["expected"], analyzer)
                    prompt = improve_prompt(bench, analysis, improver)
                    prompt_impr[bench["name"]] = {"analysis": analysis["analysis"], "improved_prompt": prompt}
                elif score < 1.0:
                    model_result["failures"] += 1
                if score == 1.0:
                    break
            scores[bench["name"]] = best_score
            model_result[f"score_{bench['name']}"] = best_score

        if run_bigbench:
            try:
                bb = benchmark_with_bigbench(model, timeout=get_model_timeout(model))
                model_result["bigbench_scores"] = bb.get("bigbench_scores")
                model_result["bigbench_predictions"] = bb.get("predictions")
            except Exception:
                pass

        model_result["prompt_improvements"] = prompt_impr
        results.append(model_result)
        update_modelstate_json([model_result])
        if idx < len(models)-1 and not ask_continue_with_timeout(5):
            break
    return results
