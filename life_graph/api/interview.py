"""Interview Engine API routes.

The system asks a few precise, high-value questions per day; the user
answers in one line. Questions render in the daily brief, dashboard,
CLI, and (future) WhatsApp bot.

Prefix: /interview
Tags: [interview]
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, status

from life_graph.api.responses import success_response
from life_graph.core.events import event_bus
from life_graph.core.tenant import get_current_tenant_id
from life_graph.models.schemas import InterviewAnswerRequest, InterviewQuestionResponse
from life_graph.services.interview import ExpiredQuestionError, InterviewService
from life_graph.storage.database import async_session

router = APIRouter(prefix="/interview", tags=["interview"])


# ── Dependencies ──────────────────────────────────────────────


async def _get_interview_service() -> AsyncGenerator[InterviewService, None]:
    """Yield an InterviewService bound to a request-scoped session.

    Commits on successful completion; rolls back automatically on error
    via the ``async_session`` context manager.
    """
    async with async_session() as session:
        svc = InterviewService(session, event_bus)
        yield svc
        await session.commit()


# ── Routes ───────────────────────────────────────────────────


@router.get(
    "/pending",
    summary="Today's pending interview questions",
)
async def list_pending_questions(
    svc: InterviewService = Depends(_get_interview_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """List open questions, highest priority first.

    This is what the daily brief, dashboard, and CLI all render.
    """
    questions = await svc.list_pending(tenant_id)
    return success_response(
        data={
            "questions": [
                InterviewQuestionResponse.model_validate(q) for q in questions
            ]
        }
    )


@router.post(
    "/{question_id}/answer",
    summary="Answer an interview question",
)
async def answer_question(
    question_id: uuid.UUID,
    body: InterviewAnswerRequest,
    svc: InterviewService = Depends(_get_interview_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Answer a question.

    The answer routes back through the capture spine and updates the
    question's origin (knowledge gap resolved, prediction resolved,
    reflection stored). Answering an expired question returns 410 —
    the answer is still captured as a plain memory.
    """
    try:
        q = await svc.answer(tenant_id, question_id, body.answer)
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview question {question_id} not found",
        )
    except ExpiredQuestionError:
        # Commit the plain-memory capture despite the 410
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This question expired — your answer was still saved as a memory.",
        )
    return success_response(data=InterviewQuestionResponse.model_validate(q))


@router.post(
    "/{question_id}/skip",
    summary="Skip an interview question",
)
async def skip_question(
    question_id: uuid.UUID,
    svc: InterviewService = Depends(_get_interview_service),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Skip a question.

    Anti-nag: the origin's other open questions get halved priority,
    and a question skipped twice is never asked again.
    """
    try:
        q = await svc.skip(tenant_id, question_id)
    except LookupError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Interview question {question_id} not found",
        )
    return success_response(data=InterviewQuestionResponse.model_validate(q))
