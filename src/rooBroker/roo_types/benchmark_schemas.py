"""Validation schemas for benchmark definitions.

This module provides Pydantic models for validating benchmark JSON files
and their test cases based on different evaluation methods.
"""

from typing import List, Dict, Any, Union, Optional, Literal
from pydantic import BaseModel, Field, model_validator, field_validator

# Benchmark Types
TaskType = Literal[
    "statement",  # Single line or statement-level code generation
    "function",  # Complete function implementation
    "class",  # Full class implementation
    "algorithm",  # Algorithm or data structure implementation
    "context",  # Context window testing
]

DifficultyLevel = Literal[
    "basic",  # Entry level tasks
    "intermediate",  # Tasks requiring good programming practices
    "advanced",  # Complex tasks requiring expert knowledge
]

EvaluationMethod = Literal[
    "string_contains",  # Simple string containment check
    "exec_check_state",  # Execute code and check resulting state
    "exec_call_func",  # Execute code and call function with test cases
    "eval_expression",  # Evaluate expression directly
    "class_eval",  # Evaluate class implementation
]


class BaseTestCase(BaseModel):
    """Base class for all test cases."""

    input: Dict[str, Any] = Field(default_factory=dict)
    expected: Any


class StringContainsTestCase(BaseTestCase):
    """Test case for string_contains evaluation method."""

    @field_validator("expected")
    def validate_expected_string(cls, v):
        if not isinstance(v, str):
            raise ValueError(
                "Expected value must be a string for string_contains test cases"
            )
        return v


class ExecCheckStateTestCase(BaseTestCase):
    """Test case for exec_check_state evaluation method."""

    expected: Dict[str, Any]

    @field_validator("expected")
    def validate_expected_dict(cls, v):
        if not isinstance(v, dict):
            raise ValueError(
                "Expected value must be a dictionary for exec_check_state test cases"
            )
        return v


class ExecCallFuncTestCase(BaseTestCase):
    """Test case for exec_call_func evaluation method."""

    input: Dict[str, Any] = Field(default_factory=dict)


class EvalExpressionTestCase(BaseTestCase):
    """Test case for eval_expression evaluation method."""

    pass


class ClassEvalTestCase(BaseModel):
    """Test case for class_eval evaluation method."""

    sequence: List[str] = Field(description="Sequence of method calls to execute")
    expected: Any = Field(description="Expected result of the final method call")


class BenchmarkTask(BaseModel):
    """A single benchmark task definition."""

    id: str = Field(description="Unique identifier for the benchmark")
    name: str = Field(description="Human-readable name")
    type: TaskType
    difficulty: DifficultyLevel
    prompt: str = Field(description="The task prompt")
    system_prompt: str = Field(description="System context/role for the model")
    evaluation_method: EvaluationMethod
    test_cases: List[Dict[str, Any]] = Field(min_length=1)
    temperature: float = Field(default=0.2)
    tags: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_test_cases(self) -> "BenchmarkTask":
        """Validate that test cases match the evaluation method."""
        method = self.evaluation_method

        # Define expected test case type for each method
        method_case_map = {
            "string_contains": StringContainsTestCase,
            "exec_check_state": ExecCheckStateTestCase,
            "exec_call_func": ExecCallFuncTestCase,
            "eval_expression": EvalExpressionTestCase,
            "class_eval": ClassEvalTestCase,
        }

        validator_class = method_case_map[method]
        for case in self.test_cases:
            try:
                validator_class(**case)
            except Exception as e:
                raise ValueError(
                    f"Invalid test case for method {method}: {str(e)}\n"
                    f"Test case: {case}"
                )

        return self
