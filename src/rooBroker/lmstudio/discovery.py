"""
Discovery of LM Studio models.
"""
from typing import List, Dict, Any
import requests

from .config import LM_STUDIO_MODELS_ENDPOINT


def discover_lmstudio_models(  # deprecated - use LMStudioClient.discover_models instead
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

    models: List[Dict[str, Any]] = []
    for model in data.get("data", []):
        model_info: Dict[str, Any] = {
            "id": model.get("id") or model.get("name"),
            "family": model.get("family"),
            "context_window": model.get("context_length") or model.get("context_window"),
        }
        models.append(model_info)
    return models
