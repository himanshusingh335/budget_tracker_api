from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

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


@asynccontextmanager
async def get_checkpointer():
    async with AsyncPostgresSaver.from_conn_string(settings.database_url) as checkpointer:
        await checkpointer.setup()
        yield checkpointer


async def list_sessions(checkpointer: AsyncPostgresSaver) -> list[dict]:
    cursor = await checkpointer.conn.execute(_LIST_SESSIONS_QUERY)
    return await cursor.fetchall()
