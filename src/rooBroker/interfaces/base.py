"""Base protocol for model provider clients.

This module defines the base Protocol that all model provider clients
(LM Studio, Ollama, etc.) must implement to provide a consistent interface
for model discovery and interaction.
"""

from typing import List, Optional, Protocol

from rooBroker.roo_types.discovery import (
    ChatCompletionRequest,
    ChatMessage,
    DiscoveredModel,
)


class ModelProviderClient(Protocol):
    """Protocol defining the interface for model provider clients.
    
    This protocol must be implemented by all model provider clients
    (e.g., LM Studio, Ollama) to ensure consistent interaction patterns
    across different providers.
    
    The protocol focuses on core operations:
    - Model discovery and information retrieval
    - Running completions for benchmarking and interaction
    """
    
    def discover_models(self) -> List[DiscoveredModel]:
        """Discover available models from this provider.
        
        Returns:
            List[DiscoveredModel]: List of discovered models with their information.
            Returns an empty list if no models are found.
        """
        ...
    
    def get_model_details(self, model_id: str) -> Optional[DiscoveredModel]:
        """Get detailed information about a specific model.
        
        Args:
            model_id: The ID of the model to get details for.
            
        Returns:
            Optional[DiscoveredModel]: The model's details if found, None otherwise.
        """
        ...
    
    def run_completion(
        self,
        messages: List[ChatMessage],
        model_id: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """Run a chat completion request for the specified model.
        
        This method is used for both basic interaction and benchmarking tasks.
        
        Args:
            messages: List of chat messages forming the conversation history.
            model_id: The ID of the model to use for completion.
            temperature: Sampling temperature, controls randomness.
            max_tokens: Maximum number of tokens to generate.
            
        Returns:
            str: The generated completion text.
            
        Raises:
            ConnectionError: If unable to connect to the model provider.
            ValueError: If the model_id is invalid or other parameter validation fails.
        """
        ...