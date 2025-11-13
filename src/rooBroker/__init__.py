"""rooBroker - CLI tool for discovering, benchmarking, and managing LM Studio and Ollama models.

This package provides tools for:
- Model discovery across multiple providers (LM Studio, Ollama)
- Comprehensive benchmarking with multiple evaluation methods
- RooCode mode generation based on model capabilities
- Context window optimization proxy
- Both CLI and interactive TUI interfaces
"""

__version__ = "0.1.0"

from rooBroker.main import main
from rooBroker.interfaces import ModelProviderClient, LMStudioClient, OllamaClient

__all__ = [
    "__version__",
    "main",
    "ModelProviderClient",
    "LMStudioClient",
    "OllamaClient",
]
