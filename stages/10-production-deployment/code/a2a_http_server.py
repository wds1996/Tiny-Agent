import os

import uvicorn
from starlette.applications import Starlette

from a2a.helpers import get_message_text, new_agent_text_message
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore

from tiny_agent.integrations.a2a import A2ASkillDescriptor, build_agent_card


class EchoAgentExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        text = get_message_text(context.message) if context.message else ""
        await event_queue.enqueue_event(new_agent_text_message(f"Echo: {text}"))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise RuntimeError("cancel is not supported by this teaching Agent")


def build_app() -> Starlette:
    card = build_agent_card(
        name="Tiny-Agent Production Echo",
        description="Stage 10 A2A-over-HTTP teaching service.",
        version="0.1.0",
        url="http://127.0.0.1:9999",
        skills=[A2ASkillDescriptor(id="echo", name="Echo", description="Echo text for protocol testing.")],
    )
    handler = DefaultRequestHandler(
        agent_executor=EchoAgentExecutor(),
        task_store=InMemoryTaskStore(),
        agent_card=card,
    )
    routes = []
    routes.extend(create_agent_card_routes(card))
    routes.extend(create_jsonrpc_routes(handler, "/"))
    return Starlette(routes=routes)


if __name__ == "__main__":
    app = build_app()
    if os.environ.get("TINY_AGENT_RUN_A2A_SERVER") == "1":
        uvicorn.run(app, host="127.0.0.1", port=9999)
    else:
        print("A2A app built with routes:")
        for route in app.routes:
            print(" -", getattr(route, "path", route))
        print("Set TINY_AGENT_RUN_A2A_SERVER=1 to actually bind port 9999.")
