from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any


def build_a2a_starlette_app(
    *,
    agent_card: Any,
    agent_executor: Any,
    task_store: Any | None = None,
    rpc_url: str = "/",
):
    """Build a current A2A 1.0 Starlette service with explicit shutdown drain.

    Imports remain lazy so the Tiny-Agent core does not depend on the optional
    Stage 13 web/A2A stack. The default in-memory task store is appropriate for
    teaching and smoke tests only; production replicas need shared durable task
    semantics if clients depend on task lookup/resubscription.
    """

    if not rpc_url.startswith("/"):
        raise ValueError("rpc_url must start with '/'")

    try:
        from a2a.server.request_handlers import DefaultRequestHandler
        from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
        from a2a.server.tasks import InMemoryTaskStore
        from starlette.applications import Starlette
    except ImportError as exc:  # pragma: no cover - optional extra boundary
        raise RuntimeError(
            "A2A serving requires the Stage 13 optional dependency: "
            "python -m pip install -e '.[stage13]'"
        ) from exc

    handler = DefaultRequestHandler(
        agent_executor=agent_executor,
        task_store=task_store if task_store is not None else InMemoryTaskStore(),
        agent_card=agent_card,
    )
    routes = [
        *create_agent_card_routes(agent_card),
        *create_jsonrpc_routes(handler, rpc_url),
    ]

    @asynccontextmanager
    async def lifespan(app):
        yield
        close = getattr(handler, "aclose", None)
        if close is not None:
            await close()

    app = Starlette(routes=routes, lifespan=lifespan)
    app.state.a2a_request_handler = handler
    return app
