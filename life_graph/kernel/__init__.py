"""OS Kernel — the core operating system layer for Life Graph.

Manages agent personas, task execution (process manager),
intelligent routing (chief router), scheduled jobs, project
awareness, and notifications.
"""

from life_graph.kernel.process_manager import ProcessManager
from life_graph.kernel.personas import PersonaService
from life_graph.kernel.chief_router import ChiefRouter
from life_graph.kernel.scheduler import SchedulerService
from life_graph.kernel.project_registry import ProjectRegistry
from life_graph.kernel.notification_engine import NotificationEngine

__all__ = [
    "ProcessManager",
    "PersonaService",
    "ChiefRouter",
    "SchedulerService",
    "ProjectRegistry",
    "NotificationEngine",
]
