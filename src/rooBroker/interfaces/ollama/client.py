"""Ollama client implementation of the ModelProviderClient protocol.

This module provides the OllamaClient class that implements the ModelProviderClient
protocol for interacting with Ollama's API. It handles model discovery and
completion requests with proper error handling and context optimization.
"""

from typing import List, Optional, Dict, Any
import requests
import json  # Add this import at the top if not already present

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
        except requests.exceptions.ConnectionError as e:
            raise RuntimeError(f"Failed to connect to Ollama server: {e}") from e
        except requests.exceptions.Timeout as e:
            raise RuntimeError(f"Connection to Ollama timed out: {e}") from e
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to query Ollama models endpoint: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Unexpected error querying Ollama: {e}") from e

        models: List[DiscoveredModel] = []
        for model in data.get("models", []):
            # Get the model name which is required
            model_name = model.get("name", "")
            if not model_name:
                # Skip models without a name
                continue

            # Create a ModelInfo with required keys
            model_info: OllamaModelInfo = {
                "id": model_name,  # Required
                "name": model_name,  # Required
            }
            
            # Add optional fields if available
            model_info["context_window"] = 8192  # Default value, actual value not provided in /api/tags
            
            if model.get("tag"):
                model_info["version"] = model.get("tag", "latest")
                
            if model.get("modified_at"):
                model_info["created"] = model.get("modified_at", 0)
                
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

            # Create a ModelInfo with required keys
            model_info: OllamaModelInfo = {
                "id": model_id,  # Required
                "name": model_id,  # Required
            }
            
            # Add optional fields if available
            context_length = data.get("parameters", {}).get("context_length")
            if context_length:
                model_info["context_window"] = context_length
            else:
                model_info["context_window"] = 8192  # Default
                
            if data.get("tag"):
                model_info["version"] = data.get("tag", "latest")
                
            if data.get("modified_at"):
                model_info["created"] = data.get("modified_at", 0)
                
            return model_info
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

        # Prepare the payload
        payload: Dict[str, Any] = {
            "model": model_id,
            "messages": ollama_messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        try:
            # Define headers including User-Agent
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'Mozilla/5.0'
            }

            response = requests.post(
                self.chat_endpoint,
                headers=headers,  # Pass the defined headers
                json=payload,  # Use json parameter for automatic Content-Type and serialization
                timeout=60,
                verify=False  # Disable SSL verification
            )
            response.raise_for_status()
            result = response.json()

            # Extract the generated text from the response
            if not result.get("message", {}).get("content"):
                raise ValueError("No content in response message")

            return result["message"]["content"]

        except requests.RequestException as e:
            raise ConnectionError(f"Failed to connect to Ollama: {e}")
        except Exception as e:
            raise ValueError(f"Error in completion request: {e}")