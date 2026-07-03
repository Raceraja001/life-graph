"""Plugin discovery and loading system (T-080).

Scans the ``plugins/`` directory for sub-packages that expose a
``register(event_bus, config)`` function. Each plugin directory must
contain an ``__init__.py`` with a module-level ``register`` callable.

Optional ``config.yaml`` files are loaded automatically and passed
to the plugin's ``register()`` function.

Usage::

    from life_graph.core.events import event_bus
    from life_graph.core.plugins import PluginManager

    pm = PluginManager(event_bus)
    pm.load_all()
    print(pm.list_plugins())
"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Any

import yaml

from life_graph.core.events import EventBus

logger = logging.getLogger(__name__)


class PluginManager:
    """Discovers, loads, and manages Life Graph plugins.

    Args:
        event_bus: The application event bus to pass to plugins.
        plugins_dir: Path to the directory containing plugin packages.
            Defaults to ``plugins/`` relative to the project root.
    """

    def __init__(self, event_bus: EventBus, plugins_dir: str | Path = "plugins") -> None:
        self.event_bus = event_bus
        self.plugins_dir = Path(plugins_dir)
        self.loaded: dict[str, dict[str, Any]] = {}

    def discover(self) -> list[str]:
        """Find plugin directories that contain an ``__init__.py``.

        Returns:
            List of plugin names (directory names).
        """
        if not self.plugins_dir.is_dir():
            logger.warning("Plugins directory not found: %s", self.plugins_dir)
            return []

        plugins: list[str] = []
        for child in sorted(self.plugins_dir.iterdir()):
            if child.is_dir() and (child / "__init__.py").exists():
                plugins.append(child.name)
        logger.info("Discovered %d plugin(s): %s", len(plugins), plugins)
        return plugins

    def load(self, name: str) -> None:
        """Import a single plugin and call its ``register(event_bus, config)`` function.

        Args:
            name: Plugin directory name inside ``plugins_dir``.

        Raises:
            ValueError: If the plugin directory or ``__init__.py`` does not exist.
            RuntimeError: If the plugin has no ``register`` callable.
        """
        plugin_path = self.plugins_dir / name
        if not (plugin_path / "__init__.py").exists():
            raise ValueError(f"Plugin '{name}' has no __init__.py in {plugin_path}")

        # Load optional config.yaml
        config: dict[str, Any] = {}
        config_file = plugin_path / "config.yaml"
        if config_file.exists():
            with open(config_file, encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            logger.debug("Loaded config for plugin '%s': %s", name, config)

        # Import the plugin module
        try:
            # Build a dotted module path from the plugins directory
            module_parts = list(self.plugins_dir.parts) + [name]
            module_path = ".".join(module_parts)
            module = importlib.import_module(module_path)
        except ImportError:
            # Fallback: add plugins_dir parent to sys.path and try bare import
            import sys

            plugins_parent = str(self.plugins_dir.parent.resolve())
            if plugins_parent not in sys.path:
                sys.path.insert(0, plugins_parent)
            module_path = f"{self.plugins_dir.name}.{name}"
            module = importlib.import_module(module_path)

        register_fn = getattr(module, "register", None)
        if not callable(register_fn):
            raise RuntimeError(
                f"Plugin '{name}' has no callable 'register' in __init__.py"
            )

        try:
            register_fn(self.event_bus, config)
            self.loaded[name] = {
                "status": "loaded",
                "config": config,
                "module": module_path,
            }
            logger.info("Loaded plugin: %s", name)
        except Exception:
            self.loaded[name] = {"status": "error", "config": config, "module": module_path}
            logger.exception("Failed to load plugin '%s'", name)

    def load_all(self) -> None:
        """Discover and load all available plugins."""
        for name in self.discover():
            try:
                self.load(name)
            except Exception:
                logger.exception("Error loading plugin '%s'", name)

    def list_plugins(self) -> list[dict[str, Any]]:
        """Return metadata for all loaded plugins.

        Returns:
            List of dicts with ``name``, ``status``, and ``config`` keys.
        """
        return [
            {"name": name, **info}
            for name, info in self.loaded.items()
        ]
