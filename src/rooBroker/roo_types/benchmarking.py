"""Type definitions for benchmarking-related data structures.

This module defines the core types used by the benchmarking system. It focuses on
modular, provider-agnostic data structures that support various levels of task
complexity and categories.
"""

from typing import List, Dict, Any, Union, Optional, Literal, TypedDict
from typing_extensions import NotRequired
from pydantic import BaseModel, Field, root_validator, validator
from pydantic.fields import FieldInfo

# Benchmark Types and Constants
TaskType = Literal[
    "statement",    # Single line or statement-level code generation
    "function",     # Complete function implementation
    "class",        # Full class implementation
    "algorithm",    # Algorithm or data structure implementation
    "context"       # Context window testing
]

DifficultyLevel = Literal[
    "basic",          # Entry level tasks
    "intermediate",   # More complex tasks
    "advanced"       # Expert level tasks
]

EvaluationMethod = Literal[
    "string_contains",  # Check if response contains expected string
    "exec_check_state", # Execute code and check state
    "exec_call_func",   # Execute function and check return value
    "eval_expression",  # Evaluate expression and check result
    "class_eval"       # Evaluate class implementation
]

class BaseTestInput(TypedDict):
    """Base input data for a benchmark test case."""
    variables: NotRequired[Dict[str, Any]]
    setup: NotRequired[str]

class BaseTestCase(TypedDict):
    """Base structure for a single test case within a benchmark task."""
    input: BaseTestInput
    expected: Any

class BenchmarkMetricsDict(TypedDict):
    """Metrics for benchmark evaluation."""
    test_pass_rate: float
    pass_at_k: Dict[str, float]
    error_rate: float
    code_quality: NotRequired[Dict[str, Any]]

class BaseTestResult(TypedDict):
    """Base structure for test execution results."""
    passed: bool
    error: Optional[str]
    metrics: Optional[Dict[str, Any]]

class BaseBenchmarkResult(TypedDict):
    """Base structure for complete benchmark results."""
    task_id: str
    test_results: List[BaseTestResult]
    metrics: BenchmarkMetricsDict

class BenchmarkTask(BaseModel):
    """Core benchmark task definition."""
    id: str
    name: str
    type: TaskType
    difficulty: DifficultyLevel
    prompt: str
    system_prompt: str
    evaluation_method: EvaluationMethod
    expected: Optional[Any] = None
    expected_response_variants: Optional[List[Any]] = None
    test_cases: List[Dict[str, Any]] = Field(default_factory=list)
    temperature: float = Field(0.2)
    tags: List[str] = Field(default_factory=list)

    @root_validator(pre=True)
    def validate_test_cases(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate test cases based on evaluation method."""
        method = values.get("evaluation_method")
        test_cases = values.get("test_cases", [])
        
        if not test_cases and method != "string_contains":
            raise ValueError("Test cases are required for non-string_contains evaluation methods")
            
        return values

class BenchmarkExecutionResult(TypedDict):
    """Result of executing a benchmark."""
    task_id: str
    test_results: List[Dict[str, Any]]
    metrics: Dict[str, Any]

# Export these types
__all__ = [
    'BenchmarkExecutionResult',
    'BenchmarkTask',
    'BaseTestResult',
    'BaseTestCase',
    'TaskType',
    'DifficultyLevel',
    'EvaluationMethod'
]
