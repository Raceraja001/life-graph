"""FastAPI application entry point."""

from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from life_graph.api import admin, graph, intentions, memories, search
from life_graph.api.multimodal import router as multimodal_router
from life_graph.config import settings
from life_graph.core.events import event_bus
from life_graph.core.plugins import PluginManager
from life_graph.storage.database import engine


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    # Startup — load plugins
    plugins_dir = Path(__file__).resolve().parent.parent / "plugins"
    plugin_manager = PluginManager(event_bus, plugins_dir=plugins_dir)
    plugin_manager.load_all()
    app.state.plugin_manager = plugin_manager
    app.state.event_bus = event_bus
    logger.info(
        "Loaded %d plugin(s): %s",
        len(plugin_manager.loaded),
        list(plugin_manager.loaded.keys()),
    )
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
app.include_router(graph.router)
app.include_router(multimodal_router)

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

