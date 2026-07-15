"""Main autonomy router — mounts all sub-module routers."""

from fastapi import APIRouter

from life_graph.autonomy.approvals.router import router as approvals_router
from life_graph.autonomy.audit.router import router as audit_router
from life_graph.autonomy.levels.router import router as levels_router
from life_graph.autonomy.pipeline.router import router as pipeline_router
from life_graph.autonomy.safety.router import router as safety_router
from life_graph.autonomy.shadow.router import router as shadow_router
from life_graph.autonomy.trust.router import router as trust_router

router = APIRouter(prefix="/autonomy", tags=["autonomy"])
router.include_router(safety_router)
router.include_router(trust_router)
router.include_router(pipeline_router)
router.include_router(approvals_router)
router.include_router(audit_router)
router.include_router(levels_router)
router.include_router(shadow_router)
