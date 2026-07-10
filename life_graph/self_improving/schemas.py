"""Pydantic v2 schemas for Era 5: Self-Improving Agent.

All response schemas use ``from_attributes=True`` so they can be
constructed directly from SQLAlchemy ORM model instances.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ── Eval Suites ───────────────────────────────────────────────────────────────


class EvalSuiteCreate(BaseModel):
    """Payload for creating a new eval suite."""

    task_type: str = Field(..., min_length=1, description="Task type this suite evaluates")
    name: str = Field(..., min_length=1, description="Human-readable suite name")
    description: str | None = Field(None, description="Suite description")
    accuracy_threshold_pct: float = Field(
        90.0, ge=0.0, le=100.0, description="Minimum accuracy to pass",
    )
    auto_optimize_enabled: bool = Field(
        True, description="Auto-trigger optimization on failure",
    )
    max_consecutive_fails: int = Field(
        3, ge=1, description="Max consecutive failures before alerting",
    )


class EvalSuiteResponse(BaseModel):
    """Serialized eval suite returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: str
    task_type: str
    name: str
    description: str | None = None
    accuracy_threshold_pct: float
    auto_optimize_enabled: bool
    consecutive_failures: int = 0
    max_consecutive_fails: int = 3
    case_count: int = 0
    last_run_at: datetime | None = None
    last_accuracy_pct: float | None = None
    created_at: datetime
    updated_at: datetime


# ── Eval Cases ────────────────────────────────────────────────────────────────


class EvalCaseCreate(BaseModel):
    """Payload for creating a single eval case."""

    input_text: str = Field(..., min_length=1, description="Input text for the case")
    expected_output: str = Field(..., min_length=1, description="Expected output")
    scoring_type: str = Field(
        "exact_match",
        pattern="^(exact_match|contains|regex|semantic_similarity|llm_judge)$",
        description="How to score this case",
    )
    scoring_config: dict[str, Any] = Field(
        default_factory=dict, description="Extra scoring configuration",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Case metadata",
    )
    source: str = Field("manual", description="Origin of the case")


class EvalCaseBulkCreate(BaseModel):
    """Payload for bulk-importing eval cases."""

    cases: list[EvalCaseCreate] = Field(
        ..., min_length=1, description="List of cases to import",
    )


class EvalCaseResponse(BaseModel):
    """Serialized eval case returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    suite_id: uuid.UUID
    input_text: str
    expected_output: str
    scoring_type: str
    scoring_config: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    source: str
    is_active: bool
    created_at: datetime


# ── Eval Runs & Results ───────────────────────────────────────────────────────


class EvalRunTrigger(BaseModel):
    """Payload for triggering an eval run."""

    prompt_version_id: str = Field(
        ..., description="Prompt version to evaluate",
    )
    trigger: str = Field(
        "manual",
        pattern="^(manual|nightly_cron|optimization_test|regression_check)$",
        description="What triggered this run",
    )


class EvalResultResponse(BaseModel):
    """Serialized single eval result."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    run_id: uuid.UUID
    case_id: uuid.UUID
    status: str
    actual_output: str | None = None
    score: float | None = None
    failure_type: str | None = None
    failure_reason: str | None = None
    similarity_score: float | None = None
    latency_ms: int | None = None
    tokens_used: int | None = None
    cost_usd: float | None = None
    error_message: str | None = None
    created_at: datetime


class EvalRunResponse(BaseModel):
    """Serialized eval run returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    suite_id: uuid.UUID
    prompt_version_id: str
    trigger: str
    status: str
    total_cases: int | None = None
    passed: int | None = None
    failed: int | None = None
    errored: int | None = None
    accuracy_pct: float | None = None
    avg_latency_ms: float | None = None
    p95_latency_ms: float | None = None
    total_tokens: int | None = None
    total_cost_usd: float | None = None
    duration_seconds: float | None = None
    error_message: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    results: list[EvalResultResponse] = Field(default_factory=list)


class FailureAnalysis(BaseModel):
    """Grouped failure analysis from an eval run."""

    failure_type: str
    count: int
    percentage: float
    examples: list[EvalResultResponse] = Field(default_factory=list)


# ── Prompt Versions ───────────────────────────────────────────────────────────


class PromptVersionCreate(BaseModel):
    """Payload for creating a new prompt version."""

    task_type: str = Field(..., min_length=1, description="Task type")
    prompt_text: str = Field(..., min_length=1, description="Prompt template")
    few_shot_examples: list[dict[str, Any]] = Field(
        default_factory=list, description="Few-shot examples",
    )
    change_note: str | None = Field(None, description="What changed")
    created_by: str = Field("human", description="Creator: human or optimizer")


class PromptVersionResponse(BaseModel):
    """Serialized prompt version."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: str
    task_type: str
    version_number: int
    prompt_text: str
    few_shot_examples: list[dict[str, Any]] = Field(default_factory=list)
    is_active: bool
    eval_score: float | None = None
    created_by: str
    optimization_run_id: str | None = None
    change_note: str | None = None
    activated_at: datetime | None = None
    deactivated_at: datetime | None = None
    created_at: datetime


class PromptVersionActivate(BaseModel):
    """Payload for activating a prompt version."""

    reason: str | None = Field(None, description="Why this version is being activated")


# ── Optimization ──────────────────────────────────────────────────────────────


class OptimizationTrigger(BaseModel):
    """Payload for triggering a prompt optimization run."""

    suite_id: uuid.UUID = Field(..., description="Eval suite to optimize for")
    trigger_eval_run_id: str = Field(
        ..., description="The eval run that triggered this optimization",
    )


class OptimizationRunResponse(BaseModel):
    """Serialized optimization run."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: str
    suite_id: uuid.UUID
    task_type: str
    trigger_eval_run_id: str
    trigger_accuracy_pct: float | None = None
    threshold_pct: float | None = None
    training_positive_count: int | None = None
    training_negative_count: int | None = None
    candidate_version_id: str | None = None
    candidate_eval_run_id: str | None = None
    candidate_accuracy_pct: float | None = None
    previous_version_id: str | None = None
    previous_accuracy_pct: float | None = None
    status: str
    regression_details: dict[str, Any] | None = None
    review_decision: str | None = None
    review_reason: str | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    optimization_tokens: int | None = None
    eval_tokens: int | None = None
    optimization_cost_usd: float | None = None
    eval_cost_usd: float | None = None
    total_cost_usd: float | None = None
    error_message: str | None = None
    started_at: datetime
    completed_at: datetime | None = None


class ReviewDecision(BaseModel):
    """Payload for reviewing an optimization run."""

    decision: str = Field(
        ...,
        pattern="^(approve|reject)$",
        description="Approve or reject the optimization",
    )
    reason: str | None = Field(None, description="Reason for the decision")
    reviewed_by: str = Field("human", description="Who reviewed")


# ── Dashboard & Trends ────────────────────────────────────────────────────────


class PerTaskAccuracy(BaseModel):
    """Accuracy stats for a single task type."""

    task_type: str
    suite_id: uuid.UUID
    suite_name: str
    last_accuracy_pct: float | None = None
    accuracy_threshold_pct: float
    case_count: int
    last_run_at: datetime | None = None
    status: str = "unknown"  # passing, failing, no_data


class AccuracyTrend(BaseModel):
    """Accuracy trend data point."""

    run_id: uuid.UUID
    accuracy_pct: float | None = None
    started_at: datetime
    prompt_version_id: str
    trigger: str


class CostTrend(BaseModel):
    """Cost trend data point."""

    date: datetime
    eval_cost_usd: float = 0.0
    optimization_cost_usd: float = 0.0
    total_cost_usd: float = 0.0


class AutoFix(BaseModel):
    """Summary of an auto-fix attempt."""

    optimization_run_id: uuid.UUID
    task_type: str
    status: str
    previous_accuracy_pct: float | None = None
    candidate_accuracy_pct: float | None = None
    started_at: datetime


class DashboardOverview(BaseModel):
    """Top-level dashboard overview for the self-improving system."""

    total_suites: int = 0
    total_cases: int = 0
    total_runs: int = 0
    total_prompt_versions: int = 0
    avg_accuracy_pct: float | None = None
    suites_passing: int = 0
    suites_failing: int = 0
    recent_optimizations: list[AutoFix] = Field(default_factory=list)
    per_task: list[PerTaskAccuracy] = Field(default_factory=list)
    accuracy_trends: list[AccuracyTrend] = Field(default_factory=list)
    cost_trends: list[CostTrend] = Field(default_factory=list)
