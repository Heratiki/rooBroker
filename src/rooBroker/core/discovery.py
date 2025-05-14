"""Core model discovery logic.

This module provides a unified interface for discovering models across
different providers (LM Studio, Ollama, etc.) using the interface clients.
"""

from typing import List, Dict, Tuple, Optional, Any

from rooBroker.interfaces.lmstudio.client import LMStudioClient
from rooBroker.interfaces.ollama.client import OllamaClient
from rooBroker.roo_types.discovery import DiscoveredModel


def discover_all_models() -> List[DiscoveredModel]:
    """Discover all available models from connected providers.

    Returns:
        List[DiscoveredModel]: Combined list of discovered models from all providers.
        Returns an empty list if no models are found or all providers fail.
    """
    # Initialize clients with default configurations
    lm_client = LMStudioClient()
    ollama_client = OllamaClient()
    clients = [lm_client, ollama_client]

    # Initialize empty list for all discovered models
    all_models: List[DiscoveredModel] = []

    # Try discovering models from each provider
    for client in clients:
        try:
            provider_models = client.discover_models()
            all_models.extend(provider_models)
        except Exception as e:
            # Don't print warning here - let the caller handle this
            # Just continue with other providers silently
            pass

    return all_models


def discover_models_with_status() -> Tuple[List[DiscoveredModel], Dict[str, Any]]:
    """Discover models with detailed provider status information.

    Returns:
        Tuple containing:
            - List[DiscoveredModel]: Combined list of discovered models
            - Dict with provider status information:
                {
                    "providers": {
                        "LM Studio": {"status": True/False, "count": n, "error": "msg"},
                        "Ollama": {"status": True/False, "count": n, "error": "msg"}
                    },
                    "total_count": n
                }
    """
    # Initialize clients
    lm_client = LMStudioClient()
    ollama_client = OllamaClient()

    # Initialize results
    all_models: List[DiscoveredModel] = []
    status: Dict[str, Any] = {
        "providers": {
            "LM Studio": {"status": False, "count": 0, "error": None},
            "Ollama": {"status": False, "count": 0, "error": None},
        },
        "total_count": 0,
    }

    # Try LM Studio
    try:
        lm_models = lm_client.discover_models()
        for model in lm_models:
            model["provider"] = "LM Studio"
        all_models.extend(lm_models)
        status["providers"]["LM Studio"]["status"] = True
        status["providers"]["LM Studio"]["count"] = len(lm_models)
    except Exception as e:
        status["providers"]["LM Studio"]["error"] = str(e)

    # Try Ollama
    try:
        ollama_models = ollama_client.discover_models()
        for model in ollama_models:
            model["provider"] = "Ollama"
        all_models.extend(ollama_models)
        status["providers"]["Ollama"]["status"] = True
        status["providers"]["Ollama"]["count"] = len(ollama_models)
    except Exception as e:
        status["providers"]["Ollama"]["error"] = str(e)

    # Update total count
    status["total_count"] = len(all_models)

    return all_models, status
