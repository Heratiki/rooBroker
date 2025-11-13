"""Core model discovery logic.

This module provides a unified interface for discovering models across
different providers (LM Studio, Ollama, etc.) using the interface clients.
"""

from typing import List, Dict, Tuple, Optional, Any

from rooBroker.interfaces.lmstudio.client import LMStudioClient
from rooBroker.interfaces.ollama.client import OllamaClient
from rooBroker.roo_types.discovery import DiscoveredModel
from rooBroker.core.log_config import logger


def discover_all_models() -> List[DiscoveredModel]:
    """Discover all available models from connected providers.

    Returns:
        List[DiscoveredModel]: Combined list of discovered models from all providers.
        Returns an empty list if no models are found or all providers fail.
    """
    # TODO: P2 - No configuration for provider endpoints
    # Issue: Hardcodes default URLs (localhost:1234, localhost:11434) with no way
    # to configure custom URLs for remote providers or non-standard ports.
    # Why it matters: Users can't discover models from remote servers or custom setups.
    # Action: Accept optional base_urls dict parameter or read from environment variables.

    # TODO: P2 - No deduplication of models
    # Issue: If the same model appears in multiple providers (e.g., via proxies or
    # shared model stores), it will be listed multiple times in all_models.
    # Why it matters: Duplicate models in UI, wasted benchmarking on same model twice.
    # Action: Deduplicate by model ID, or mark which providers have which models.

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
        except RuntimeError as e:
            # Expected errors from providers (connection issues, etc.)
            # Log as debug since this is expected when a provider is not running
            logger.debug(
                f"Provider {client.__class__.__name__} unavailable: {e}"
            )
        except Exception as e:
            # Unexpected errors - log as warning but continue with other providers
            logger.warning(
                f"Unexpected error discovering models from {client.__class__.__name__}: {e}"
            )

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
        # TODO: P2 - Direct mutation of TypedDict may fail at runtime
        # Issue: model is a TypedDict (ModelInfo/OllamaModelInfo), and setting
        # model["provider"] = "LM Studio" works only if "provider" is in the TypedDict.
        # It is marked NotRequired, so this works, but if model is not a dict (e.g., frozen),
        # this will fail. Type checker doesn't catch this.
        # Why it matters: Could fail at runtime if TypedDict implementation changes.
        # Action: Use safer pattern: model = {**model, "provider": "LM Studio"}.
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
