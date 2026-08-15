from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from core.config import settings

_LIST_SESSIONS_QUERY = """
SELECT thread_id, checkpoint->>'ts' AS last_modified
FROM (
    SELECT DISTINCT ON (thread_id) thread_id, checkpoint
    FROM checkpoints
    WHERE checkpoint_ns = ''
    ORDER BY thread_id, checkpoint_id DESC
) latest
ORDER BY last_modified DESC
"""

_POOL_CONNECTION_KWARGS = {
    "autocommit": True,
    "row_factory": dict_row,
}


@asynccontextmanager
async def get_checkpointer():
    async with AsyncConnectionPool(
        conninfo=settings.database_url,
        min_size=settings.db_pool_min_size,
        max_size=settings.db_pool_max_size,
        kwargs=_POOL_CONNECTION_KWARGS,
    ) as pool:
        checkpointer = AsyncPostgresSaver(pool)
        await checkpointer.setup()
        yield checkpointer


async def list_sessions(checkpointer: AsyncPostgresSaver) -> list[dict]:
    async with checkpointer.conn.connection() as conn:
        cursor = await conn.execute(_LIST_SESSIONS_QUERY)
        return await cursor.fetchall()
