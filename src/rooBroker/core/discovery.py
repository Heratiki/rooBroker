"""Core model discovery logic.

This module provides a unified interface for discovering models across
different providers (LM Studio, Ollama, etc.) using the interface clients.
"""

from typing import List

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
            # Print warning but continue with other providers
            print(f"Warning: Failed to discover models from {client.__class__.__name__}: {e}")

    return all_models