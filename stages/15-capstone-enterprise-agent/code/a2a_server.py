from __future__ import annotations

import os

import uvicorn
from a2a.helpers import get_message_text, new_text_message
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events.event_queue import EventQueue

from tiny_agent.capstone import ResearchRequest
from tiny_agent.integrations.a2a import A2ASkillDescriptor, build_agent_card
from tiny_agent.integrations.a2a_server import build_a2a_starlette_app

from common import offline_base_agent

agent = offline_base_agent()


class OpenScholarExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        question = get_message_text(context.message) if context.message else ""
        if not question.strip():
            await event_queue.enqueue_event(new_text_message("Please provide a non-empty research question."))
            return
        report = await agent.run(
            ResearchRequest(
                question=question,
                allow_external_search=False,
                user_id="a2a-demo-user",
                thread_id="a2a-demo-thread",
            )
        )
        await event_queue.enqueue_event(new_text_message(report.answer))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise RuntimeError("Cancellation is not implemented by this teaching A2A executor.")


def build_app():
    card = build_agent_card(
        name="Tiny-Agent OpenScholar",
        description="Academic research Agent grounded in a local full-text corpus.",
        version="0.1.0",
        url="http://127.0.0.1:9998",
        skills=[
            A2ASkillDescriptor(
                id="academic-research",
                name="Academic Research",
                description="Research an Agent/RAG question and return an evidence-grounded answer.",
                tags=("research", "rag", "agents"),
                examples=("Compare ReAct and RAG.",),
            )
        ],
    )
    return build_a2a_starlette_app(agent_card=card, agent_executor=OpenScholarExecutor())


if __name__ == "__main__":
    app = build_app()
    if os.environ.get("TINY_AGENT_RUN_A2A_SERVER") == "1":
        uvicorn.run(app, host="127.0.0.1", port=9998)
    else:
        print("OpenScholar A2A app built with routes:")
        for route in app.routes:
            print(" -", getattr(route, "path", route))
        print("Set TINY_AGENT_RUN_A2A_SERVER=1 to bind port 9998.")
