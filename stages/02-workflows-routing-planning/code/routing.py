"""Route Lin's form or a short message to finite, application-owned handlers."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import re
from typing import Literal, Protocol

from pydantic import Field, model_validator

from workflow import City, Contract, Language, WeatherService, WeatherTask, run_workflow


class RouteDecision(Contract):
    route: Literal["weather", "compare", "help", "clarify"]
    cities: tuple[City, ...] = Field(default=(), max_length=2)
    fahrenheit: bool = False
    reason: str = Field(min_length=1, max_length=300)

    @model_validator(mode="after")
    def check_destination(self) -> "RouteDecision":
        expected = {"weather": 1, "compare": 2, "help": 0, "clarify": 0}[self.route]
        if len(self.cities) != expected or len(set(self.cities)) != len(self.cities):
            raise ValueError("the destination and city list disagree")
        if self.route in {"help", "clarify"} and self.fahrenheit:
            raise ValueError("a non-weather destination cannot request conversion")
        if not self.reason.strip():
            raise ValueError("reason must not be blank")
        return self


class SemanticRouter(Protocol):
    def decide(self, request: str) -> RouteDecision: ...


@dataclass(frozen=True)
class RoutingResult:
    decision: RouteDecision
    source: str


def mentioned_cities(request: str) -> set[str]:
    cities = set(re.findall(r"\b(?:Tokyo|Paris)\b", request, flags=re.IGNORECASE))
    normalized = {city.title() for city in cities}
    if "东京" in request:
        normalized.add("Tokyo")
    if "巴黎" in request:
        normalized.add("Paris")
    return normalized


def validate_for_request(decision: RouteDecision, request: str) -> RouteDecision:
    decision = RouteDecision.model_validate(decision)
    if not set(decision.cities).issubset(mentioned_cities(request)):
        raise ValueError("the router invented a city absent from the request")
    return decision


class HybridRouter:
    def __init__(self, semantic_router: SemanticRouter) -> None:
        self.semantic_router = semantic_router

    def route(self, *, request: str | None = None, form: WeatherTask | None = None) -> RoutingResult:
        if (request is None) == (form is None):
            raise ValueError("provide exactly one of request or form")
        if form is not None:
            form = WeatherTask.model_validate(form)
            decision = RouteDecision(
                route="weather" if len(form.cities) == 1 else "compare",
                cities=form.cities, fahrenheit=form.fahrenheit,
                reason="Validated form fields already identify the workflow.",
            )
            return RoutingResult(decision, "form")
        if not isinstance(request, str) or not request.strip() or len(request) > 1000:
            raise ValueError("request must contain 1 to 1000 characters")
        decision = self.semantic_router.decide(request)
        return RoutingResult(validate_for_request(decision, request), "semantic")


def task_from_decision(decision: RouteDecision, language: Language) -> WeatherTask:
    decision = RouteDecision.model_validate(decision)
    if decision.route not in {"weather", "compare"}:
        raise ValueError("this route has no weather task")
    return WeatherTask(cities=decision.cities, fahrenheit=decision.fahrenheit, language=language)


def dispatch(result: RoutingResult, service: WeatherService, *, language: Language = "zh-CN") -> str:
    if language not in {"zh-CN", "en"}:
        raise ValueError("unsupported language")
    decision = RouteDecision.model_validate(result.decision)
    if decision.route in {"weather", "compare"}:
        return run_workflow(task_from_decision(decision, language), service)
    if decision.route == "help":
        return ("可以读取 Tokyo / Paris 的教学记录、换算温度，或比较两城。" if language == "zh-CN"
                else "Read Tokyo / Paris teaching records, convert units, or compare both cities.")
    return ("请说明要查询 Tokyo 还是 Paris，是否比较两城，以及是否需要华氏度；这里只提供教学记录。"
            if language == "zh-CN" else
            "Please specify Tokyo or Paris, whether to compare them, and whether to include Fahrenheit. Only teaching records are available.")


EXAMPLES = {
    "zh-CN": {
        "weather": "读一下东京的教学天气，顺便给我华氏度。",
        "compare": "比较东京和巴黎的教学天气，两座城市都显示华氏度。",
        "help": "这个页面能帮我做什么？",
        "clarify": "那里现在冷不冷？",
    },
    "en": {
        "weather": "Read Tokyo's teaching weather and include Fahrenheit.",
        "compare": "Compare Tokyo and Paris teaching weather; include Fahrenheit for both.",
        "help": "What can this page do?",
        "clarify": "Is it cold there right now?",
    },
}


class ScriptedSemanticRouter:
    """Exact fixture lookup, NOT an NLP classifier. Unknown text is rejected."""

    def __init__(self) -> None:
        self.calls = 0

    def decide(self, request: str) -> RouteDecision:
        self.calls += 1
        for examples in EXAMPLES.values():
            for route, text in examples.items():
                if request == text:
                    cities = ("Tokyo", "Paris") if route == "compare" else (("Tokyo",) if route == "weather" else ())
                    return RouteDecision(
                        route=route, cities=cities, fahrenheit=bool(cities),
                        reason="A fixed test decision for this exact example.",
                    )
        raise ValueError("the offline router only recognizes EXAMPLES; use DeepSeek for other wording")


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline form and message routing demonstration.")
    parser.add_argument("--example", choices=tuple(EXAMPLES["en"]), default="compare")
    parser.add_argument("--language", choices=("zh-CN", "en"), default="zh-CN")
    args = parser.parse_args()
    model = ScriptedSemanticRouter()
    router = HybridRouter(model)
    form = WeatherTask(cities=("Tokyo",), fahrenheit=True, language=args.language)
    result = router.route(form=form)
    print("=== form ===", result.source, "semantic calls:", model.calls)
    print(dispatch(result, WeatherService(), language=args.language))
    result = router.route(request=EXAMPLES[args.language][args.example])
    service = WeatherService()
    print("\n=== scripted message decision (no live LLM) ===")
    print(result.decision.model_dump_json(indent=2))
    print(dispatch(result, service, language=args.language))
    print("source calls:", service.calls)


if __name__ == "__main__":
    main()
