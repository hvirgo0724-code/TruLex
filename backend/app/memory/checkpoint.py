"""Async PostgreSQL resources for LangGraph's asynchronous graph execution."""
from contextlib import AsyncExitStack

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres.aio import AsyncPostgresStore

from app.core.config import settings


def _normalize_uri(uri: str) -> str:
    return uri.replace("postgresql+psycopg2://", "postgresql://").replace(
        "postgresql+psycopg://", "postgresql://"
    )


async def enter_memory(stack: AsyncExitStack):
    saver = await stack.enter_async_context(
        AsyncPostgresSaver.from_conn_string(_normalize_uri(settings.DB_URI))
    )
    await saver.setup()
    store = await stack.enter_async_context(
        AsyncPostgresStore.from_conn_string(_normalize_uri(settings.DB_URI))
    )
    await store.setup()
    return saver, store
