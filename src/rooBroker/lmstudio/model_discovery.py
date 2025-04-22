"""
Entrypoint for LM Studio model discovery and benchmarking, delegating to modular implementations.
"""
from typing import Any, List, Dict
from typing import cast
from .discovery import discover_lmstudio_models
from .benchmark import benchmark_lmstudio_models
from .config import console, rich_available  # type: ignore


def main() -> None:
    """Discover and benchmark LM Studio models."""
    try:
        models: List[Dict[str, Any]] = discover_lmstudio_models()
        results: List[Dict[str, Any]] = benchmark_lmstudio_models(models)
        for res in results:
            if rich_available and console:
                cast(Any, console).print(res)  # type: ignore
            else:
                print(res)
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()