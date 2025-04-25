"""Type definitions for model-related data structures."""

from typing import Dict, Optional, TypedDict, Literal, NotRequired

from .benchmarking import BigBenchScores
from .settings import OpenRouterModelInfo, VSCodeModelSelector

PromptImprovement = TypedDict('PromptImprovement', {
    'analysis': str,
    'score': float,
    'timestamp': str
})

class ModelState(TypedDict, total=False):
    model_id: str
    id: str
    context_window: int
    score_simple: float
    score_moderate: float
    score_complex: float
    score_context_window: float
    bigbench_scores: BigBenchScores
    prompt_improvements: Dict[str, PromptImprovement]
    last_updated: str

ApiProvider = Literal['lmstudio', 'openrouter', 'azure']

class ApiConfig(TypedDict):
    apiProvider: ApiProvider
    openRouterModelId: str
    openRouterModelInfo: OpenRouterModelInfo
    vsCodeLmModelSelector: VSCodeModelSelector
    lmStudioModelId: str
    lmStudioDraftModelId: str
    lmStudioSpeculativeDecodingEnabled: bool
    modelTemperature: NotRequired[Optional[float]]
    rateLimitSeconds: int
    id: str

Priority = Literal['high', 'medium', 'low']

class FileRestrictions(TypedDict):
    fileRegex: str
    description: str

class ModelConfiguration(TypedDict):
    config_id: str
    thinking_mode: bool
    priority: Priority
    api_config: ApiConfig
    file_restrictions: FileRestrictions

class OllamaModelDetails(TypedDict, total=False):
    """Detailed model information for Ollama models."""
    id: str
    name: str
    context_window: int
    version: str
    status: str
    additional_info: dict[str, any]
