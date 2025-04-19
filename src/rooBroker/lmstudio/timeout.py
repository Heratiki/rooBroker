"""
Module for model timeout determination based on model metadata.
"""
from typing import Dict, Any


def get_model_timeout(model: Dict[str, Any]) -> int:
    """
    Determine appropriate timeout based on model size/type.

    Args:
        model: Model information dictionary

    Returns:
        Timeout in seconds
    """
    model_id: str = model.get("id", "").lower()
    context_size: Any = model.get("context_window", 0)

    LARGE_MARKERS = ["32b", "70b", "13b", "7b", "llama-3", "qwen2.5", "codellama", "mistral", "wizardcoder"]
    if any(marker in model_id for marker in LARGE_MARKERS):
        return 120  # 2 minutes for large models

    if isinstance(context_size, (int, float)):
        if context_size > 8000:
            return 120
        if context_size > 4000:
            return 60

    return 30  # Default for smaller models
