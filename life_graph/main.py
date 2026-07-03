"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from life_graph.api import admin, intentions, memories, search
from life_graph.config import settings
from life_graph.storage.database import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    # Startup
    yield
    # Shutdown
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Brain-inspired personal memory system with proactive recall",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register API routers ─────────────────────────────────────
app.include_router(memories.router)
app.include_router(search.router)
app.include_router(intentions.router)
app.include_router(admin.router)

# ── Static files (Brain Viewer dashboard) ─────────────────────
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/brain", StaticFiles(directory=str(static_dir), html=True), name="static")


@app.get("/")
async def root():
    """Redirect root to the Brain Viewer dashboard."""
    return RedirectResponse(url="/brain/")


@app.get("/health")
async def health_check():
    """Basic health check endpoint."""
    return {"status": "healthy", "version": "0.1.0"}

