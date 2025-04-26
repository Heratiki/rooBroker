"""Type definitions for benchmarking-related data structures.

This module defines the core types used by the benchmarking system. It focuses on
modular, provider-agnostic data structures that support various levels of task
complexity and categories.

These types support both simple benchmarks (like statement-level code generation) and
complex benchmarks (like algorithmic problem-solving), enabling a comprehensive
evaluation of model capabilities.
"""

from typing import List, TypedDict, Literal, Optional, Dict, Any

TaskType = Literal[
    "statement",    # Single line or statement-level code generation
    "function",     # Complete function implementation
    "class",        # Full class implementation
    "algorithm",    # Algorithm or data structure implementation
    "context"       # Context window testing
]

DifficultyLevel = Literal[
    "basic",          # Entry level tasks
    "intermediate",   # Tasks requiring good programming practices
    "advanced"        # Complex tasks requiring expert knowledge
]

BenchmarkMetrics = Literal[
    "conciseness",     # Code should be concise and efficient
    "readability",     # Code should be easily readable
    "documentation",   # Code should have proper documentation
    "type_hints",     # Code should use type hints
    "error_handling", # Code should handle errors properly
    "encapsulation",  # Code should follow OOP principles
    "performance",    # Code should be performant
    "context_retention" # Model retains context across paragraphs
]

class MetricResult(TypedDict):
    """Results for a single metric."""
    score: float
    max_score: float
    details: Optional[str]

class TestResult(TypedDict):
    """Results for a single test case."""
    passed: bool
    actual_output: Any
    expected_output: Any
    error: Optional[str]

class BenchmarkResult(TypedDict):
    """Results for a single benchmark task."""
    name: str
    type: TaskType
    difficulty: DifficultyLevel
    metrics: Dict[BenchmarkMetrics, MetricResult]
    test_results: List[TestResult]
    overall_score: float
    duration_ms: float
    error: Optional[str]

class CategoryResults(TypedDict):
    """Results grouped by task type."""
    statement_level: List[BenchmarkResult]
    function_level: List[BenchmarkResult]
    class_level: List[BenchmarkResult]
    algorithm_level: List[BenchmarkResult]
    context_tests: List[BenchmarkResult]

class BenchmarkSummary(TypedDict):
    """Overall benchmark summary."""
    total_tasks: int
    passed_tasks: int
    overall_score: float
    category_scores: Dict[TaskType, float]
    difficulty_scores: Dict[DifficultyLevel, float]
    results: CategoryResults
