"""Ollama client implementation of the ModelProviderClient protocol.

This module provides the OllamaClient class that implements the ModelProviderClient
protocol for interacting with Ollama's API. It handles model discovery and
completion requests with proper error handling and context optimization.
"""

from typing import List, Optional, Dict, Any
import requests

from rooBroker.interfaces.base import ModelProviderClient
from rooBroker.roo_types.discovery import (
    DiscoveredModel,
    ChatMessage,
    OllamaModelInfo
)


class OllamaClient(ModelProviderClient):
    """Ollama API client implementing the ModelProviderClient protocol."""

    def __init__(self, base_url: str = "http://localhost:11434") -> None:
        """Initialize the Ollama client.

        Args:
            base_url: Base URL for the Ollama API. Defaults to localhost:11434.
        """
        self.base_url = base_url.rstrip("/")
        self.tags_endpoint = f"{self.base_url}/api/tags"
        self.show_endpoint = f"{self.base_url}/api/show"
        self.generate_endpoint = f"{self.base_url}/api/generate"
        self.chat_endpoint = f"{self.base_url}/api/chat"

    def discover_models(self) -> List[DiscoveredModel]:
        """Discover available models from Ollama.

        Returns:
            List[DiscoveredModel]: List of discovered models with their information.
            Returns an empty list if no models are found.

        Raises:
            RuntimeError: If unable to query the Ollama models endpoint.
        """
        try:
            response = requests.get(self.tags_endpoint, timeout=5)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            print(f"Warning: Failed to query Ollama models endpoint: {e}")
            return []

        models: List[DiscoveredModel] = []
        for model in data.get("models", []):
            model_info = OllamaModelInfo(
                id=model.get("name", ""),
                name=model.get("name", ""),
                # Use default context window since it's not provided in /api/tags
                context_window=8192,
                version=model.get("tag", "latest"),
                created=model.get("modified_at", 0)
            )
            models.append(model_info)
        return models

    def get_model_details(self, model_id: str) -> Optional[DiscoveredModel]:
        """Get detailed information about a specific model.

        Args:
            model_id: The ID of the model to get details for.

        Returns:
            Optional[DiscoveredModel]: The model's details if found, None otherwise.
        """
        try:
            response = requests.post(
                self.show_endpoint,
                json={"name": model_id},
                timeout=5
            )
            response.raise_for_status()
            data = response.json()

            return OllamaModelInfo(
                id=model_id,
                name=model_id,
                context_window=data.get("parameters", {}).get("context_length", 8192),
                version=data.get("tag", "latest"),
                created=data.get("modified_at", 0)
            )
        except Exception as e:
            print(f"Warning: Failed to get model details for {model_id}: {e}")
            return None

    def run_completion(
        self,
        messages: List[ChatMessage],
        model_id: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """Run a chat completion request for the specified model.

        Args:
            messages: List of chat messages forming the conversation history.
            model_id: The ID of the model to use for completion.
            temperature: Sampling temperature, controls randomness.
            max_tokens: Maximum number of tokens to generate.

        Returns:
            str: The generated completion text.

        Raises:
            ConnectionError: If unable to connect to Ollama.
            ValueError: If the model_id is invalid or other parameter validation fails.
        """
        # Convert messages to Ollama format
        ollama_messages = [{"role": msg["role"], "content": msg["content"]} for msg in messages]

        # Prepare payload with context optimization
        payload: Dict[str, Any] = {
            "model": model_id,
            "messages": ollama_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False  # Ensure we get a complete response
        }

        try:
            response = requests.post(
                self.chat_endpoint,
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            result = response.json()

            # Extract the generated text from the response
            if "message" not in result:
                raise ValueError("No message in response")

            return result["message"]["content"]

        except requests.RequestException as e:
            raise ConnectionError(f"Failed to connect to Ollama: {e}")
        except Exception as e:
            raise ValueError(f"Error in completion request: {e}")