# Life Graph Plugins

Plugins extend the Life Graph system by subscribing to events emitted by the
core application. Each plugin lives in its own sub-directory under `plugins/`.

## Directory Structure

```
plugins/
├── my_plugin/
│   ├── __init__.py     # Required — must export register(event_bus, config)
│   └── config.yaml     # Optional — plugin configuration
└── README.md           # This file
```

## Writing a Plugin

### 1. Create the directory

```bash
mkdir plugins/my_plugin
```

### 2. Create `__init__.py`

Your `__init__.py` **must** expose a `register(event_bus, config)` function:

```python
"""My custom plugin."""
import logging
from typing import Any

logger = logging.getLogger(__name__)

def register(event_bus, config: dict[str, Any]) -> None:
    """Called by PluginManager on startup.

    Args:
        event_bus: The application EventBus instance.
        config: Dict loaded from config.yaml (empty dict if no config).
    """
    from life_graph.core.events import EventType

    async def on_memory_created(event):
        logger.info("Memory created: %s", event.payload)

    event_bus.subscribe(EventType.MEMORY_CREATED, on_memory_created)
    logger.info("my_plugin registered successfully")
```

### 3. (Optional) Create `config.yaml`

```yaml
# Any plugin-specific configuration
my_setting: "value"
notifications_enabled: true
```

The config dict is passed directly to your `register()` function.

## Available Event Types

| Event Type | Value | Description |
|---|---|---|
| `MEMORY_CREATED` | `memory:created` | A new memory was stored |
| `MEMORY_RETRIEVED` | `memory:retrieved` | A memory was retrieved/recalled |
| `MEMORY_UPDATED` | `memory:updated` | An existing memory was modified |
| `MEMORY_DELETED` | `memory:deleted` | A memory was deleted |
| `SESSION_START` | `session:start` | A new user session began |
| `SESSION_END` | `session:end` | A user session ended |
| `INTENTION_TRIGGERED` | `intention:triggered` | A prospective memory triggered |
| `CONTRADICTION_DETECTED` | `contradiction:detected` | A contradiction was found |
| `VOICE_TRANSCRIBED` | `voice:transcribed` | Audio was transcribed |
| `IMAGE_PROCESSED` | `image:processed` | An image was OCR-processed |
| `DOCUMENT_IMPORTED` | `document:imported` | A document was imported |

## Plugin Loading

Plugins are loaded automatically at application startup by the `PluginManager`.
They can also be loaded manually:

```python
from life_graph.core.events import event_bus
from life_graph.core.plugins import PluginManager

pm = PluginManager(event_bus, plugins_dir="plugins")
pm.load_all()  # discovers and loads all plugins
```

## Guidelines

- **Never crash**: Wrap all fallible operations in try/except.
- **Async handlers**: Event handlers must be `async def`.
- **Lazy imports**: Import heavy dependencies inside your handler, not at module level.
- **Logging**: Use `logging.getLogger(__name__)` for diagnostics.
