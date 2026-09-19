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

## Connector plugins (calendar, email, contacts, GitHub, …)

A plugin that brings in data from an outside source exports `CONNECTOR` instead
of (or as well as) `register`. The connector runtime (`life_graph/connectors/`)
discovers it in both the API and the worker. See `plugins/calendar/`,
`plugins/mail/`, `plugins/contacts/` and `plugins/github/`, and the designs in
`docs/specs/connectors.md`, `docs/specs/connector-contacts.md` and
`docs/specs/connector-github.md`. A plugin can also check a credential when it
is added (`verify_credential`), e.g. to refuse a token that can write.

A source that is imported rather than fetched (a vCard export) uses auth method
`file` and provides `import_file(account, text) -> SyncResult`; the runtime
treats each import as the complete set for that account.

A connector implements the `Connector` protocol (`life_graph/connectors/base.py`):
`name`, `display_name`, `item_kinds`, `auth_methods`, `async sync(account,
secret, cursor) -> SyncResult` and `async fetch_body(...)`. It returns plain
`Item` objects and nothing else: it never touches the database, the tool
registry or a model. The core stores items, holds credentials, schedules syncs,
and decides what a cloud model may see, so a plugin cannot leak data by mistake.
