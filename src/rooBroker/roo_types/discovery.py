"""Type definitions for LM Studio model discovery and benchmarking."""

from typing import Any, Callable, TypedDict, Union, Literal, NotRequired


class BenchmarkTest(TypedDict):
    """Definition for a single benchmark test."""
    prompt: str
    expected: str
    category: Literal['simple', 'moderate', 'complex', 'context_window']
    score_fn: Callable[[str], float]


class BenchmarkResult(TypedDict):
    """Result of running benchmark tests."""
    score_simple: float
    score_moderate: float
    score_complex: float
    score_context_window: float


class AnalysisResult(TypedDict):
    """Result of analyzing a model's response."""
    analysis: str
    score: float
    suggestions: list[str]


class ChatMessage(TypedDict):
    """A single message in a chat completion request."""
    role: Literal['system', 'user', 'assistant']
    content: str


class ChatCompletionRequest(TypedDict):
    """Request structure for chat completion API."""
    model: str
    messages: list[ChatMessage]
    temperature: float
    max_tokens: int


class ModelInfo(TypedDict):
    """Information about an LM Studio model.
    
    The 'id' key is required, all other keys are optional.
    """
    id: str  # Required key
    family: NotRequired[str]
    context_window: NotRequired[int]
    created: NotRequired[int]
    provider: NotRequired[str]  # Added provider key


class OllamaModelInfo(TypedDict):
    """Information about an Ollama model for discovery.
    
    The 'id' and 'name' keys are required, all other keys are optional.
    """
    id: str  # Required key
    name: str  # Required key
    context_window: NotRequired[int]
    version: NotRequired[str]
    created: NotRequired[int]
    provider: NotRequired[str]  # Added provider key


DiscoveredModel = Union[ModelInfo, OllamaModelInfo]
