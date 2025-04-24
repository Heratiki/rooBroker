from typing import Dict, Any
import requests
from deepeval.models import DeepEvalLLM  # type: ignore

# Basic evaluation configuration
EVALUATION_CONFIG = {
    "temperature": 0.2,
    "max_tokens": 2000,
    "timeout": 30
}

class LMStudioLLM(DeepEvalLLM):
    """LM Studio model wrapper for DeepEval benchmarking."""
    
    def __init__(self, model_id: str, api_endpoint: str = "http://localhost:1234/v1/chat/completions", timeout: int = 30):
        """Initialize the LM Studio model wrapper."""
        super().__init__()
        self.model_id = model_id
        self.api_endpoint = api_endpoint
        self.timeout = timeout

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate a response from the LM Studio model.
        
        Args:
            prompt: The input prompt string
            **kwargs: Additional arguments (temperature, max_tokens, etc.)
        
        Returns:
            The model's response as a string
        """
        try:
            messages = [{"role": "user", "content": prompt}]
            payload = {
                "model": self.model_id,
                "messages": messages,
                "temperature": kwargs.get("temperature", EVALUATION_CONFIG["temperature"]),
                "max_tokens": kwargs.get("max_tokens", EVALUATION_CONFIG["max_tokens"])
            }
            
            response = requests.post(self.api_endpoint, json=payload, timeout=self.timeout)
            response.raise_for_status()
            
            return response.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"Error generating response: {str(e)}")
            return ""

    def get_model_name(self) -> str:
        """Return the model ID for DeepEval."""
        return self.model_id