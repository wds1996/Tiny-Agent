from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Protocol

from pydantic import BaseModel, ConfigDict, Field


class Route(str, Enum):
    WEATHER = "weather"
    ACCOUNT = "account"
    GENERAL = "general"


class RouteDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route: Route
    reason: str = Field(min_length=1)


class SemanticRouter(Protocol):
    def decide(self, request: str) -> RouteDecision:
        """Choose one route for a natural-language request."""


def rule_route(request: str) -> Route | None:
    """Use deterministic routing when the input already carries a reliable signal."""
    normalized = request.strip().lower()

    if normalized.startswith("weather:"):
        return Route.WEATHER
    if normalized.startswith("account:"):
        return Route.ACCOUNT

    return None


class ScriptedSemanticRouter:
    """A deterministic stand-in for a model router used by the offline demo."""

    def decide(self, request: str) -> RouteDecision:
        normalized = request.lower()

        if any(word in normalized for word in ("rain", "temperature", "forecast")):
            return RouteDecision(
                route=Route.WEATHER,
                reason="The request is asking about weather information.",
            )

        if any(word in normalized for word in ("invoice", "billing", "refund")):
            return RouteDecision(
                route=Route.ACCOUNT,
                reason="The request is about account or billing information.",
            )

        return RouteDecision(
            route=Route.GENERAL,
            reason="No specialized route is clearly required.",
        )


@dataclass(frozen=True)
class RoutingResult:
    route: Route
    source: str
    reason: str


class HybridRouter:
    """Prefer deterministic routing and use semantic routing only when needed."""

    def __init__(self, semantic_router: SemanticRouter) -> None:
        self.semantic_router = semantic_router

    def route(self, request: str) -> RoutingResult:
        if not request.strip():
            raise ValueError("request must not be blank")

        deterministic = rule_route(request)
        if deterministic is not None:
            return RoutingResult(
                route=deterministic,
                source="rule",
                reason="The request contains an explicit route prefix.",
            )

        decision = self.semantic_router.decide(request)
        return RoutingResult(
            route=decision.route,
            source="semantic",
            reason=decision.reason,
        )


def handle_weather(request: str) -> str:
    return f"weather handler received: {request}"


def handle_account(request: str) -> str:
    return f"account handler received: {request}"


def handle_general(request: str) -> str:
    return f"general handler received: {request}"


HANDLERS: dict[Route, Callable[[str], str]] = {
    Route.WEATHER: handle_weather,
    Route.ACCOUNT: handle_account,
    Route.GENERAL: handle_general,
}


def dispatch(request: str, routing: RoutingResult) -> str:
    """Execute ordinary application code after the route has been chosen."""
    handler = HANDLERS[routing.route]
    return handler(request)


def main() -> None:
    router = HybridRouter(ScriptedSemanticRouter())

    examples = [
        "weather: show Tokyo's teaching forecast",
        "I was charged twice on my latest invoice.",
        "Help me rewrite this sentence more clearly.",
    ]

    for request in examples:
        routing = router.route(request)
        output = dispatch(request, routing)

        print(f"request: {request}")
        print(f"route:   {routing.route.value}")
        print(f"source:  {routing.source}")
        print(f"reason:  {routing.reason}")
        print(f"output:  {output}")
        print("-" * 60)


if __name__ == "__main__":
    main()
