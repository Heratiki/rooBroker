"""
API client for LM Studio chat calls with context optimization.
"""
from typing import List, Dict, Any
import requests
from .config import LM_STUDIO_MODELS_ENDPOINT, CHAT_COMPLETIONS_ENDPOINT
from .timeout import get_model_timeout


def call_lmstudio_with_max_context(  # deprecated - use LMStudioClient.run_completion instead
    model_id: str,
    messages: List[Dict[str, str]],
    api_endpoint: str = CHAT_COMPLETIONS_ENDPOINT,
    timeout: int = 60,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    optimize_context: bool = True
) -> Dict[str, Any]:
    """
    Make an API call to LM Studio with optimized context handling.

    Args:
        model_id: ID of the LM Studio model to use
        messages: Chat messages with role/content dicts
        api_endpoint: Endpoint for chat completions
        timeout: Request timeout in seconds
        temperature: Sampling temperature
        max_tokens: Maximum tokens to generate
        optimize_context: Whether to optimize based on model context window

    Returns:
        Response JSON as dict

    Raises:
        RuntimeError on failure
    """
    payload: Dict[str, Any] = {"model": model_id, "messages": messages, "temperature": temperature}
    if optimize_context:
        try:
            resp = requests.get(LM_STUDIO_MODELS_ENDPOINT, timeout=5)
            resp.raise_for_status()
            for info in resp.json().get("data", []):
                if info.get("id") == model_id or info.get("name") == model_id:
                    context_length = info.get("context_length") or info.get("context_window")
                    if isinstance(context_length, (int, float)):
                        response_buffer = min(max_tokens, max(1000, int(context_length * 0.25)))
                        payload["max_tokens"] = response_buffer
                        input_limit = context_length - response_buffer
                        estimated = sum(len(m.get("content", "")) // 4 for m in messages)
                        if estimated > input_limit * 0.9:
                            print(f"Warning: Input may exceed token limit. Est: {estimated}, Limit: {input_limit}")
                    break
            else:
                payload["max_tokens"] = max_tokens
        except Exception:
            payload["max_tokens"] = max_tokens
    else:
        payload["max_tokens"] = max_tokens

    try:
        res = requests.post(api_endpoint, json=payload, timeout=timeout)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        raise RuntimeError(f"Error calling LM Studio API: {e}")
