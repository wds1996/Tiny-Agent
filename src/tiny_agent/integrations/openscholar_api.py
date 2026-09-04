from dataclasses import asdict
from typing import Any

from ..approval import ApprovalDecision
from ..capstone.base_agent import BaseOpenScholarAgent
from ..capstone.langgraph_agent import LangGraphOpenScholarAgent
from ..capstone.models import ResearchRequest


def build_openscholar_app(
    *,
    base_agent: BaseOpenScholarAgent,
    graph_agent: LangGraphOpenScholarAgent | None = None,
):
    """Build a thin FastAPI adapter around the capstone orchestrators.

    Body-level ``user_id`` is demo correlation metadata, not authenticated
    identity. Production must bind owner/tenant identity from an auth layer.
    """

    try:
        from fastapi import FastAPI, HTTPException
        from pydantic import BaseModel, Field
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "OpenScholar HTTP serving requires: python -m pip install -e '.[stage15]'"
        ) from exc

    class ResearchBody(BaseModel):
        question: str = Field(min_length=1, max_length=8000)
        user_id: str = Field(default="demo-user", min_length=1, max_length=255)
        thread_id: str = Field(default="demo-thread", min_length=1, max_length=255)
        allow_external_search: bool = True
        preferred_style: str | None = Field(default=None, max_length=200)
        remember_style: bool = False
        export_path: str | None = Field(default=None, max_length=500)

    class ApprovalBody(BaseModel):
        outcome: str
        edited_arguments: dict[str, Any] | None = None
        feedback: str | None = Field(default=None, max_length=2000)

    app = FastAPI(title="Tiny-Agent OpenScholar", version="0.1.0")

    def to_request(body: ResearchBody) -> ResearchRequest:
        try:
            return ResearchRequest(**body.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/livez")
    async def livez() -> dict[str, str]:
        return {"status": "alive"}

    @app.post("/v1/research/base")
    async def research_base(body: ResearchBody) -> dict[str, Any]:
        return asdict(await base_agent.run(to_request(body)))

    @app.post("/v1/research/langgraph")
    async def research_langgraph(body: ResearchBody) -> dict[str, Any]:
        if graph_agent is None:
            raise HTTPException(status_code=503, detail="LangGraph implementation unavailable")
        return asdict(await graph_agent.run(to_request(body)))

    @app.post("/v1/research/langgraph/{thread_id}/resume")
    async def resume_langgraph(thread_id: str, body: ApprovalBody) -> dict[str, Any]:
        if graph_agent is None:
            raise HTTPException(status_code=503, detail="LangGraph implementation unavailable")
        try:
            decision = ApprovalDecision.from_payload(body.model_dump())
            report = await graph_agent.resume(thread_id=thread_id, decision=decision)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return asdict(report)

    return app
