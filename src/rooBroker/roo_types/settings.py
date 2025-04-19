"""Type definitions for API and settings-related data structures."""

from typing import Dict, Any, TypedDict

class OpenRouterModelInfo(TypedDict):
    maxTokens: int
    contextWindow: int
    supportsImages: bool
    supportsComputerUse: bool
    supportsPromptCache: bool
    inputPrice: float
    outputPrice: float
    cacheWritesPrice: float
    cacheReadsPrice: float
    description: str
    thinking: bool

class VSCodeModelSelector(TypedDict):
    vendor: str
    family: str

class ApiProviderConfig(TypedDict):
    apiConfigs: Dict[str, Any]
    modeApiConfigs: Dict[str, str]

class Settings(TypedDict):
    providerProfiles: ApiProviderConfig
