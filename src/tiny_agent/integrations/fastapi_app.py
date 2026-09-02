from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Mapping
from contextlib import AbstractAsyncContextManager
from typing import Any, Callable

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from tiny_agent.production import (
    BoundedAgentService,
    ServiceCapacityError,
    ServiceRequest,
    ServiceTimeoutError,
    run_readiness_checks,
)


class RunRequestModel(BaseModel):
    input: str = Field(min_length=1, max_length=100_000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunResponseModel(BaseModel):
    request_id: str
    run_id: str
    output: Any
    elapsed_ms: float


def create_app(
    service: BoundedAgentService,
    *,
    readiness_checks: Mapping[str, Callable[[], Any]] | None = None,
    readiness_timeout_seconds: float = 1.0,
    lifespan: Callable[[FastAPI], AbstractAsyncContextManager[Any]] | None = None,
) -> FastAPI:
    """Create a thin HTTP adapter around the framework-neutral service core."""

    checks = dict(readiness_checks or {})
    app = FastAPI(title="Tiny-Agent Service", version="0.1.0", lifespan=lifespan)

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        request_id = _safe_request_id(request.headers.get("x-request-id"))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response

    @app.get("/livez")
    async def livez() -> dict[str, str]:
        return {"status": "alive"}

    @app.get("/readyz")
    async def readyz():
        report = await run_readiness_checks(
            checks, timeout_seconds=readiness_timeout_seconds
        )
        payload = {
            "status": "ready" if report.ready else "not_ready",
            "checks": [
                {"name": item.name, "ok": item.ok, "error_type": item.error_type}
                for item in report.checks
            ],
        }
        return JSONResponse(status_code=200 if report.ready else 503, content=payload)

    @app.post("/v1/runs", response_model=RunResponseModel)
    async def run_agent(body: RunRequestModel, request: Request) -> RunResponseModel:
        service_request = ServiceRequest(
            input=body.input,
            metadata=body.metadata,
            request_id=request.state.request_id,
        )
        try:
            result = await service.run(service_request)
        except ServiceCapacityError as exc:
            raise HTTPException(status_code=429, detail="service at capacity") from exc
        except ServiceTimeoutError as exc:
            raise HTTPException(status_code=504, detail="agent run timed out") from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail="agent run failed") from exc
        return RunResponseModel(
            request_id=result.request_id,
            run_id=result.run_id,
            output=result.output,
            elapsed_ms=result.elapsed_ms,
        )

    @app.post("/v1/runs/stream")
    async def stream_agent(body: RunRequestModel, request: Request):
        service_request = ServiceRequest(
            input=body.input,
            metadata=body.metadata,
            request_id=request.state.request_id,
        )

        async def events() -> AsyncIterator[str]:
            yield _sse(
                "run.started",
                {"request_id": service_request.request_id, "run_id": service_request.run_id},
            )
            try:
                result = await service.run(service_request)
            except ServiceCapacityError:
                yield _sse("run.error", {"code": "capacity_exceeded"})
            except ServiceTimeoutError:
                yield _sse("run.error", {"code": "run_timeout"})
            except Exception:
                yield _sse("run.error", {"code": "run_failed"})
            else:
                yield _sse(
                    "run.completed",
                    {
                        "request_id": result.request_id,
                        "run_id": result.run_id,
                        "output": jsonable_encoder(result.output),
                        "elapsed_ms": result.elapsed_ms,
                    },
                )

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app


def _safe_request_id(value: str | None) -> str:
    if value is None:
        return uuid.uuid4().hex
    candidate = value.strip()
    if not candidate or len(candidate) > 128 or any(ord(ch) < 32 for ch in candidate):
        return uuid.uuid4().hex
    return candidate


def _sse(event: str, data: Mapping[str, Any]) -> str:
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str)
    return f"event: {event}\ndata: {payload}\n\n"
