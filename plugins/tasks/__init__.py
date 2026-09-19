"""Google Tasks connector: the user's own to-do lists, read-only.

Google sign-in with ``tasks.readonly`` (docs/specs/connector-tasks.md): every
list's open tasks plus those completed in the last week, incremental via
``updatedMin``. Notes are kept for local models only. Nothing here writes:
promises from sent mail still become reminders inside Life Graph.
"""

from plugins.tasks.connector import TasksConnector

CONNECTOR = TasksConnector()
