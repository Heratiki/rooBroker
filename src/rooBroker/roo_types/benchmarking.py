"""Type definitions for benchmarking-related data structures."""

from typing import List, TypedDict, Literal

ComplexityCategory = Literal[
    'logical_reasoning',
    'algorithmic_thinking',
    'abstract_reasoning',
    'mathematics',
    'code_generation',
    'problem_solving',
    'other'
]

class MetricsDict(TypedDict):
    accuracy: float
    f1_score: float
    precision: float
    recall: float

class BigBenchTask(TypedDict):
    task: str
    weighted_score: float
    raw_score: float
    metrics: MetricsDict
    complexity_category: ComplexityCategory

class BigBenchScores(TypedDict):
    overall: float
    raw_overall: float
    tasks: List[BigBenchTask]

class TaskScore(TypedDict):
    name: str
    score: float
    metrics: MetricsDict

class ComplexityScores(TypedDict):
    logical_reasoning: List[TaskScore]
    algorithmic_thinking: List[TaskScore]
    abstract_reasoning: List[TaskScore]
    mathematics: List[TaskScore]
    code_generation: List[TaskScore]
    problem_solving: List[TaskScore]
    other: List[TaskScore]
