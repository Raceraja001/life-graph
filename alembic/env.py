"""Alembic environment configuration."""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

# Base.metadata is populated as a side effect of importing the modules that
# declare mapped classes, so every such module must be imported here — not
# just models.db. --autogenerate compares that metadata against the live
# database and reads a table it cannot see as a table to DROP.
#
# models.db alone registers 43 of the 64 tables. The documented
# `alembic revision --autogenerate` workflow would therefore have emitted
# DROP TABLE for the other 21, among them approval_queue, audit_log,
# trust_scores and every eval_* table.
#
# tests/unit/test_alembic_metadata.py asserts this list stays complete.
import life_graph.autonomy.models  # noqa: F401  - registers 8 tables
import life_graph.self_improving.models  # noqa: F401  - registers 7 tables
import life_graph.watchers.models  # noqa: F401  - registers 6 tables
from alembic import context
from life_graph.config import settings
from life_graph.models.db import Base

config = context.config

# Override sqlalchemy.url with settings
config.set_main_option("sqlalchemy.url", settings.database_url_sync)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Apache AGE stores the knowledge graph as ordinary Postgres tables, one per
# vertex and edge label, created and owned entirely by AGE. They are not
# SQLAlchemy models and never will be, so autogenerate reads all 21 of them as
# tables to DROP — Entity, Preference, Decision, _ag_label_vertex and every
# edge table, i.e. the whole knowledge graph.
#
# They cannot be filtered by schema: AGE puts them in a schema named after the
# graph, but they reflect with schema=None because the connection search_path
# includes it. ag_catalog.ag_label is the authoritative list, so ask AGE.
_AGE_LABELS: set[str] = set()


def _load_age_labels(connection) -> set[str]:  # noqa: ANN001
    """Names of the tables Apache AGE manages. Empty if AGE is not installed."""
    try:
        rows = connection.exec_driver_sql("SELECT name FROM ag_catalog.ag_label")
        return {row[0] for row in rows}
    except Exception:  # noqa: BLE001 - a database without AGE is legitimate
        return set()


def include_object(obj, name, type_, reflected, compare_to):  # noqa: ANN001, ARG001
    """Keep autogenerate to the tables SQLAlchemy actually owns."""
    return not (type_ == "table" and name in _AGE_LABELS)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        include_object=include_object,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        global _AGE_LABELS
        _AGE_LABELS = _load_age_labels(connection)

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
