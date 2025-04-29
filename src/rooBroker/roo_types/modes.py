"""Type definitions for modes-related data structures."""

from typing import TypedDict, Dict, List, Union, Literal, Any, NotRequired
from .models import ApiConfig, Priority, FileRestrictions

class EditRestrictions(TypedDict):
    fileRegex: str
    description: str

class GroupItem(TypedDict):
    fileRegex: str
    description: str

EditMode = List[Union[Literal['edit'], GroupItem]]
GroupType = Union[Literal['read', 'command', 'mcp'], EditMode]

class BenchmarkScores(TypedDict):
    bigbench: Dict[str, Any]
    standard: Dict[str, float]
    overall: float

class BenchmarkData(TypedDict):
    scores: BenchmarkScores
    lastUpdated: str

class ModeEntry(TypedDict):
    slug: str
    name: str
    roleDefinition: str
    groups: List[GroupType]
    source: str
    customInstructions: str
    contextWindow: int
    maxResponseTokens: int
    benchmarkData: BenchmarkData
    apiConfiguration: NotRequired[ApiConfig]
    priority: NotRequired[Priority]
    fileRestrictions: NotRequired[FileRestrictions]
    editRestrictions: NotRequired[EditRestrictions]

class RooModes(TypedDict):
    customModes: List[ModeEntry]
