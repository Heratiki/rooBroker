"""LM Studio client implementation of the ModelProviderClient protocol.

This module provides the LMStudioClient class that implements the ModelProviderClient
protocol for interacting with LM Studio's API. It handles model discovery and
completion requests with proper error handling and context optimization.
"""

from typing import List, Optional, Dict, Any, cast
import requests

from rooBroker.interfaces.base import ModelProviderClient
from rooBroker.roo_types.discovery import DiscoveredModel, ChatMessage, ModelInfo
from rooBroker.core.log_config import logger


class LMStudioClient(ModelProviderClient):
    """LM Studio API client implementing the ModelProviderClient protocol."""

    def __init__(self, base_url: str = "http://localhost:1234") -> None:
        """Initialize the LM Studio client.

        Args:
            base_url: Base URL for the LM Studio API. Defaults to localhost:1234.
        """
        self.base_url = base_url.rstrip("/")
        self.models_endpoint = f"{self.base_url}/v1/models"
        self.completions_endpoint = f"{self.base_url}/v1/chat/completions"

    def discover_models(self) -> List[DiscoveredModel]:
        """Discover available models from LM Studio.

        Returns:
            List[DiscoveredModel]: List of discovered models with their information.

        Raises:
            RuntimeError: If unable to query the LM Studio models endpoint.
        """
        try:
            response = requests.get(self.models_endpoint, timeout=5)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.ConnectionError as e:
            raise RuntimeError(f"Failed to connect to LM Studio server: {e}") from e
        except requests.exceptions.Timeout as e:
            raise RuntimeError(f"Connection to LM Studio timed out: {e}") from e
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to query LM Studio models endpoint: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Unexpected error querying LM Studio: {e}") from e

        models: List[DiscoveredModel] = []
        for model in data.get("data", []):
            # Create a ModelInfo (which is a TypedDict, not a class)
            # Ensure required keys are always provided
            model_id = model.get("id") or model.get("name")
            if not model_id:
                # Skip models without ID
                continue

            model_info: ModelInfo = {
                "id": model_id,  # Required key
                # Optional keys added only if they exist
            }

            # Add optional fields only if they exist
            if model.get("family"):
                model_info["family"] = model.get("family")

            context_window = model.get("context_length") or model.get("context_window")
            if context_window:
                model_info["context_window"] = context_window

            if model.get("created"):
                model_info["created"] = model.get("created")

            models.append(model_info)
        return models

    def get_model_details(self, model_id: str) -> Optional[DiscoveredModel]:
        """Get detailed information about a specific model.

        Args:
            model_id: The ID of the model to get details for.

        Returns:
            Optional[DiscoveredModel]: The model's details if found, None otherwise.
        """
        models = self.discover_models()
        for model in models:
            if model.get("id") == model_id:
                return model
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
            ConnectionError: If unable to connect to LM Studio.
            ValueError: If the model_id is invalid or other parameter validation fails.
        """
        # Convert messages to LM Studio format
        lm_messages = [
            {"role": msg["role"], "content": msg["content"]} for msg in messages
        ]

        # Prepare the payload with context optimization
        payload: Dict[str, Any] = {
            "model": model_id,
            "messages": lm_messages,
            "temperature": temperature,
        }

        # Optimize context if model details are available
        model_details = self.get_model_details(model_id)
        # Safely access context_window with a default value since it's not a required key
        if model_details:
            # Use .get() with a default value to safely handle optional keys
            context_length = model_details.get("context_window", 0)
            if context_length:
                response_buffer = min(max_tokens, max(1000, int(context_length * 0.25)))
                payload["max_tokens"] = response_buffer
                input_limit = context_length - response_buffer

                # Estimate input tokens (rough approximation)
                estimated = sum(len(m["content"]) // 4 for m in messages)
                if estimated > input_limit * 0.9:
                    logger.warning(
                        f"Input may exceed token limit. Est: {estimated}, Limit: {input_limit}"
                    )
            else:
                logger.info("Using default max_tokens due to missing context_length.")
        else:
            logger.info("Using default max_tokens due to missing model details.")

        # If we didn't have valid context information, use the default max_tokens
        payload["max_tokens"] = max_tokens

        # Determine dynamic timeout based on model_id
        timeout_sec = 60  # Default timeout
        if any(keyword in model_id.lower() for keyword in ["7b", "13b"]) or (
            model_details and model_details.get("context_window", 0) > 8000
        ):
            timeout_sec = 120
        elif any(keyword in model_id.lower() for keyword in ["30b", "34b", "70b"]):
            timeout_sec = 180

        logger.debug(
            f"Using dynamic timeout: {timeout_sec} seconds for model_id: {model_id}"
        )

        try:
            response = requests.post(
                self.completions_endpoint,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0",
                },
                verify=False,
                timeout=timeout_sec,
            )
            response.raise_for_status()
            result = response.json()

            # Extract the generated text from the response
            if not result.get("choices"):
                raise ValueError("No completion choices in response")

            return result["choices"][0]["message"]["content"]

        except requests.RequestException as e:
            raise ConnectionError(f"Failed to connect to LM Studio: {e}")
        except Exception as e:
            raise ValueError(f"Error in completion request: {e}")
