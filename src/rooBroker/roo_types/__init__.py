"""Common type definitions for the RooBroker project."""

from .benchmarking import (
    BenchmarkExecutionResult,
    BenchmarkTask,
    BaseTestResult as TestResult,
    BaseTestCase as TestCase
)
from .discovery import BenchmarkResult
from .models import (
    ModelState,
    ApiConfig,
    ModelConfiguration,
    ApiProvider,
    Priority,
    FileRestrictions,
    PromptImprovement
)
from .modes import (
    EditRestrictions,
    RooModes,
    ModeEntry,
    GroupType,
    GroupItem,
    EditMode,
    BenchmarkData,
    BenchmarkScores
)
from .settings import (
    OpenRouterModelInfo,
    VSCodeModelSelector,
    ApiProviderConfig,
    Settings
)

__all__ = [
    # Benchmarking types
    'BenchmarkResult',
    'TestResult',
    'BenchmarkTask',
    'TestCase',
    
    # Model types
    'ModelState',
    'ApiConfig',
    'ModelConfiguration',
    'ApiProvider',
    'Priority',
    'FileRestrictions',
    'PromptImprovement',
    
    # Mode types
    'EditRestrictions',
    'RooModes',
    'ModeEntry',
    'GroupType',
    'GroupItem',
    'EditMode',
    'BenchmarkData',
    'BenchmarkScores',
    
    # Settings types
    'OpenRouterModelInfo',
    'VSCodeModelSelector',
    'ApiProviderConfig',
    'Settings'
]
