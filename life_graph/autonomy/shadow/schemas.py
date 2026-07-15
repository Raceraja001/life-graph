"""Pydantic schemas for the Shadow Mode API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from life_graph.core.shadow import ShadowGrade


class GradeRequest(BaseModel):
    """Body for grading a would-have-done shadow run."""

    grade: ShadowGrade


class ShadowRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_id: str
    action_type: str
    command: str
    risk_level: str | None
    project_id: str | None
    would_have_routed: str
    grade: str | None
    created_at: datetime


class ShadowEnrollmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    agent_id: str
    status: str
    graded_good: int
    graded_bad: int
    enrolled_at: datetime
    graduated_at: datetime | None
