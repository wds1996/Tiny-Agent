from dataclasses import asdict
import inspect
from typing import Any, Awaitable, Callable, Mapping

from ..capstone.base_agent import BaseOpenScholarAgent
from ..capstone.models import ResearchRequest
from ..production import BoundedAgentService, ServiceCapacityError, ServiceRequest, ServiceTimeoutError
from ..service_identity import AuthenticatedIdentity, bind_trusted_identity


Authenticator = Callable[[Any], AuthenticatedIdentity | Awaitable[AuthenticatedIdentity]]


class OpenScholarServiceHandler:
    """Translate server-bound trusted service metadata into a ResearchRequest."""

    def __init__(self, agent: BaseOpenScholarAgent) -> None:
        self.agent = agent

    async def __call__(self, question: str, metadata: Mapping[str, Any]) -> dict[str, Any]:
        subject_id = str(metadata["subject_id"])
        tenant_id = str(metadata["tenant_id"])
        request = ResearchRequest(
            question=question,
            # Tenant-scoped identity prevents cross-tenant memory namespace collisions.
            user_id=f"{tenant_id}:{subject_id}",
            thread_id=str(metadata.get("thread_id") or f"{tenant_id}:{subject_id}:default"),
            allow_external_search=bool(metadata.get("allow_external_search", True)),
            preferred_style=metadata.get("preferred_style"),
            remember_style=bool(metadata.get("remember_style", False)),
        )
        return asdict(await self.agent.run(request))


def build_bounded_openscholar_service(
    agent: BaseOpenScholarAgent,
    *,
    max_concurrency: int = 8,
    queue_timeout_seconds: float = 0.25,
    request_timeout_seconds: float = 60.0,
) -> BoundedAgentService:
    return BoundedAgentService(
        OpenScholarServiceHandler(agent),
        max_concurrency=max_concurrency,
        queue_timeout_seconds=queue_timeout_seconds,
        request_timeout_seconds=request_timeout_seconds,
    )


def build_authenticated_openscholar_app(service: BoundedAgentService, *, authenticate: Authenticator):
    """FastAPI boundary that derives user/tenant identity from a trusted resolver.

    This module deliberately does not enable postponed annotations: `Request` is
    imported inside this factory as an optional integration dependency, and
    FastAPI needs the concrete Request type when it inspects the route signature.
    Request JSON is then validated explicitly with Pydantic so the body cannot
    smuggle authoritative identity fields into the service.
    """

    try:
        from fastapi import FastAPI, HTTPException, Request
        from pydantic import BaseModel, ConfigDict, Field, ValidationError
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("production OpenScholar API requires Stage 15 dependencies") from exc

    class Body(BaseModel):
        model_config = ConfigDict(extra="forbid")
        question: str = Field(min_length=1, max_length=8000)
        thread_id: str | None = Field(default=None, max_length=255)
        allow_external_search: bool = True
        preferred_style: str | None = Field(default=None, max_length=200)
        remember_style: bool = False

    app = FastAPI(title="Tiny-Agent OpenScholar Production Boundary", version="0.2.0")

    @app.get("/livez")
    async def livez() -> dict[str, str]:
        return {"status": "alive"}

    @app.post("/v1/research")
    async def research(request: Request):
        try:
            raw = await request.json()
            body = Body.model_validate(raw)
        except (ValidationError, ValueError, TypeError) as exc:
            detail = exc.errors() if isinstance(exc, ValidationError) else "invalid JSON request body"
            raise HTTPException(status_code=422, detail=detail) from exc

        if body.remember_style and body.preferred_style is None:
            raise HTTPException(status_code=422, detail="remember_style requires preferred_style")

        identity_value = authenticate(request)
        identity = await identity_value if inspect.isawaitable(identity_value) else identity_value
        if not isinstance(identity, AuthenticatedIdentity):
            raise HTTPException(status_code=401, detail="authentication failed")

        metadata = bind_trusted_identity(
            {
                "thread_id": body.thread_id or f"{identity.tenant_id}:{identity.principal.subject_id}:default",
                "allow_external_search": body.allow_external_search,
                "preferred_style": body.preferred_style,
                "remember_style": body.remember_style,
            },
            identity,
        )
        service_request = ServiceRequest(input=body.question, metadata=metadata)
        try:
            result = await service.run(service_request)
        except ServiceCapacityError as exc:
            raise HTTPException(status_code=429, detail="service at capacity") from exc
        except ServiceTimeoutError as exc:
            raise HTTPException(status_code=504, detail="research run timed out") from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail="research run failed") from exc
        return {
            "request_id": result.request_id,
            "run_id": result.run_id,
            "output": result.output,
            "elapsed_ms": result.elapsed_ms,
        }

    return app
