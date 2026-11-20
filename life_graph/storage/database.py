"""Database engine and session management."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from life_graph.config import settings


def engine_connect_args(database_url: str, idle_in_transaction_timeout_ms: int) -> dict:
    """asyncpg ``connect_args`` carrying the server-side session timeouts.

    Only ``idle_in_transaction_session_timeout``: nothing else reclaimed a
    connection left idle in an open transaction (audit H7). Other drivers get
    nothing, since ``server_settings`` is asyncpg's.
    """
    if "+asyncpg" not in database_url or idle_in_transaction_timeout_ms <= 0:
        return {}
    return {
        "server_settings": {
            "idle_in_transaction_session_timeout": str(int(idle_in_transaction_timeout_ms)),
        }
    }


engine = create_async_engine(
    settings.database_url,
    pool_size=settings.database_pool_size,
    max_overflow=settings.database_max_overflow,
    pool_pre_ping=True,  # Detect stale connections after DB restart
    pool_recycle=1800,  # Recycle connections every 30 min
    echo=settings.debug,
    connect_args=engine_connect_args(
        settings.database_url, settings.database_idle_in_transaction_timeout_ms
    ),
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def end_transaction(session: AsyncSession) -> None:
    """Commit *session*'s open transaction, if it has one, before a slow call.

    The read -> close -> call -> reopen pattern for code that is handed a
    session: a model call or a subprocess must not run while the session sits
    "idle in transaction" holding a snapshot and its locks. The next
    statement on the same session begins a fresh transaction. ORM objects
    survive (``expire_on_commit=False`` above). A session with no transaction
    open, or a test's mock, is left alone.
    """
    in_transaction = getattr(session, "in_transaction", None)
    if callable(in_transaction) and in_transaction() is True:
        await session.commit()


async def get_session() -> AsyncSession:
    """Dependency for FastAPI routes to get a database session."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
