from __future__ import annotations

from typing import Any


class PostgresPool:
    """Explicit lifecycle wrapper around psycopg_pool.AsyncConnectionPool."""

    def __init__(self, dsn: str, *, min_size: int = 1, max_size: int = 4) -> None:
        if not dsn.strip():
            raise ValueError("dsn must be non-empty")
        if min_size < 0 or max_size <= 0 or min_size > max_size:
            raise ValueError("invalid pool size")
        try:
            from psycopg_pool import AsyncConnectionPool
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("PostgresPool requires the Stage 13 optional dependency") from exc
        self._pool: Any = AsyncConnectionPool(
            conninfo=dsn,
            min_size=min_size,
            max_size=max_size,
            open=False,
        )

    async def open(self, *, timeout: float = 5.0) -> None:
        await self._pool.open()
        await self._pool.wait(timeout=timeout)

    async def ready(self) -> bool:
        async with self._pool.connection(timeout=1.0) as conn:
            await conn.execute("SELECT 1")
        return True

    async def aclose(self) -> None:
        await self._pool.close()
