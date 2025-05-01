from typing import Any, Dict, List, Sequence
from rich.console import Console
from rich.table import Table
from rich import box
from rooBroker.roo_types.discovery import DiscoveredModel

console = Console()

def pretty_print_models(models: Sequence[DiscoveredModel]) -> None:
    table = Table(title="Discovered Models", box=box.SIMPLE)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Provider", style="magenta")
    table.add_column("Family", style="green")
    table.add_column("Context Window", style="yellow")
    for m in models:
        table.add_row(
            str(m["id"]),
            str(m.get("provider", "Unknown")),
            str(m.get("family", "")),
            str(m.get("context_window", ""))
        )
    console.print(table)

def pretty_print_benchmarks(results: List[Dict[str, Any]]) -> None:
    # Standard benchmarks table
    table = Table(title="Standard Benchmark Results", box=box.SIMPLE)
    table.add_column("Model ID", style="cyan", no_wrap=True)
    table.add_column("Statement", style="green")
    table.add_column("Function", style="yellow")
    table.add_column("Class", style="red")
    table.add_column("Algorithm", style="blue")
    table.add_column("Context", style="magenta")
    table.add_column("Failures", style="white")

    for r in results:
        table.add_row(
            r.get("model_id", ""),
            f"{r.get('avg_score_statement', 0):.2f}",
            f"{r.get('avg_score_function', 0):.2f}",
            f"{r.get('avg_score_class', 0):.2f}",
            f"{r.get('avg_score_algorithm', 0):.2f}",
            f"{r.get('avg_score_context', 0):.2f}",
            str(r.get("failures", 0))
        )
    console.print(table)
    
    # BIG-BENCH-HARD table for models with those results
    bb_models = [r for r in results if "bigbench_scores" in r]
    if bb_models:
        # Prepare category buckets
        categories: Dict[str, List[float]] = {}
        bb_table = Table(title="BIG-BENCH-HARD Results", box=box.SIMPLE)
        bb_table.add_column("Model ID", style="cyan", no_wrap=True)
        bb_table.add_column("Overall", style="green")
        bb_table.add_column("Logical", style="yellow")
        bb_table.add_column("Algorithmic", style="red")
        bb_table.add_column("Abstract", style="blue")
        bb_table.add_column("Mathematics", style="magenta")
        bb_table.add_column("Code Gen", style="cyan")
        bb_table.add_column("Problem Solving", style="green")
        
        for r in bb_models:
            scores = r["bigbench_scores"]
            # group weighted scores by category
            for task in scores.get("tasks", []):
                cat = task.get("complexity_category", "other")
                categories.setdefault(cat, []).append(float(task.get("weighted_score", 0.0)))
            
            # Calculate category averages
            cat_avgs: Dict[str, float] = {
                cat: (sum(vals) / len(vals)) if vals else 0.0
                for cat, vals in categories.items()
            }
            
            bb_table.add_row(
                r.get("model_id", ""),
                f"{scores.get('overall', 0):.2f}",
                f"{cat_avgs.get('logical_reasoning', 0):.2f}",
                f"{cat_avgs.get('algorithmic_thinking', 0):.2f}",
                f"{cat_avgs.get('abstract_reasoning', 0):.2f}",
                f"{cat_avgs.get('mathematics', 0):.2f}",
                f"{cat_avgs.get('code_generation', 0):.2f}",
                f"{cat_avgs.get('problem_solving', 0):.2f}"
            )
        console.print(bb_table)
        
        # Add a weighted averages summary table
        summary_table = Table(title="Overall Performance Summary", box=box.SIMPLE)
        summary_table.add_column("Model ID", style="cyan", no_wrap=True)
        summary_table.add_column("Standard Avg", style="yellow")
        summary_table.add_column("BIG-BENCH Avg", style="green")
        summary_table.add_column("Overall (60/40)", style="red")
        
        for r in bb_models:
            standard_avg = (
                r.get('score_simple', 0.0) +
                r.get('score_moderate', 0.0) +
                r.get('score_complex', 0.0) +
                r.get('score_context_window', 0.0)
            ) / 4
            
            bb_score = r["bigbench_scores"].get('overall', 0.0)
            overall = standard_avg * 0.4 + bb_score * 0.6
            
            summary_table.add_row(
                r.get("model_id", ""),
                f"{standard_avg:.2f}",
                f"{bb_score:.2f}",
                f"{overall:.2f}"
            )
        console.print(summary_table)