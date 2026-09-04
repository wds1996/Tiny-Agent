import os

import uvicorn

from a2a.helpers import get_message_text, new_text_message
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events.event_queue import EventQueue

from tiny_agent.integrations.a2a import A2ASkillDescriptor, build_agent_card
from tiny_agent.integrations.a2a_server import build_a2a_starlette_app


class EchoAgentExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        text = get_message_text(context.message) if context.message else ""
        await event_queue.enqueue_event(new_text_message(f"Echo: {text}"))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise RuntimeError("cancel is not supported by this teaching Agent")


def build_app():
    card = build_agent_card(
        name="Tiny-Agent Production Echo",
        description="Stage 13 A2A-over-HTTP teaching service.",
        version="0.1.0",
        url="http://127.0.0.1:9999",
        skills=[
            A2ASkillDescriptor(
                id="echo",
                name="Echo",
                description="Echo text for protocol testing.",
            )
        ],
    )
    return build_a2a_starlette_app(agent_card=card, agent_executor=EchoAgentExecutor())


if __name__ == "__main__":
    app = build_app()
    if os.environ.get("TINY_AGENT_RUN_A2A_SERVER") == "1":
        uvicorn.run(app, host="127.0.0.1", port=9999)
    else:
        print("A2A app built with routes:")
        for route in app.routes:
            print(" -", getattr(route, "path", route))
        print("Set TINY_AGENT_RUN_A2A_SERVER=1 to actually bind port 9999.")
