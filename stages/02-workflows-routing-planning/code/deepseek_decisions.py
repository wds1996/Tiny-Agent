"""Real DeepSeek routing and planning; the application still executes every step."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from typing import Any, Mapping, TypeVar

from pydantic import BaseModel

from planning import Failure, Plan, PlanExecutor, print_run, run_with_replanning
from routing import EXAMPLES, HybridRouter, RouteDecision, dispatch, task_from_decision
from workflow import Reading, WeatherService, WeatherTask

ROUTER_INSTRUCTIONS = """Interpret a request for a teaching-weather page.
Return weather for one explicitly named Tokyo/Paris city, compare for both cities
when their records are to be compared, help for page-capability questions, and
clarify for missing/unsupported cities, live weather, unrelated requests or unclear intent.
Recognize 东京 as Tokyo and 巴黎 as Paris. Never invent a city. Set fahrenheit=true
only if Fahrenheit is requested. help/clarify have no cities and fahrenheit=false.
Only classify and extract fields. Do not answer temperatures or execute anything.
The reason is a short explanation, not an instruction to downstream code."""

PLANNER_INSTRUCTIONS = """Propose the remaining work for a fixed teaching-weather task.
Only operations read_weather, convert_temperature and write_brief exist.
read_weather requires city/source and empty inputs. Both sources expose the SAME
teaching-v1 snapshot; neither is live. Prefer primary. backup is permitted ONLY
when failures records a primary failure for that city. Never select a failed pair.
convert_temperature requires exactly one earlier unconverted reading ID as inputs;
city and source are null. Include conversion only when task.fahrenheit is true.
write_brief is last, city/source null; inputs include exactly one correctly converted
or unconverted reading per requested city. The application compares two cities.
Reuse IDs in completed; never overwrite/re-read their cities. You may assign other
step IDs and choose any dependency-correct order. Steps have unique IDs, no forward
references, at most five steps. Do not fill numeric temperatures into a plan.
If no source can finish the task, do not invent an operation. A plan is a proposal,
not permission. Return the schema, including empty inputs/null fields where required."""

T = TypeVar("T", bound=BaseModel)


class ProviderDecisionError(RuntimeError):
    pass


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Set {name} before running the live example.")
    return value


def create_client() -> Any:
    api_key = required_env("DEEPSEEK_API_KEY")
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("Install stages/02-workflows-routing-planning/code/requirements.txt first.") from exc
    return OpenAI(api_key=api_key, base_url="https://api.deepseek.com", timeout=30.0, max_retries=0)


class StructuredClient:
    def __init__(self, *, client: Any, model: str, max_calls: int = 3) -> None:
        if not isinstance(model, str) or not model.strip():
            raise ValueError("model must not be blank")
        if type(max_calls) is not int or max_calls < 1:
            raise ValueError("max_calls must be a positive integer")
        self.client, self.model, self.max_calls = client, model, max_calls
        self.calls = 0
        self.decisions: list[dict[str, Any]] = []

    def parse(self, schema: type[T], *, instructions: str, input_text: str) -> T:
        if self.calls >= self.max_calls:
            raise ProviderDecisionError("the model request budget is exhausted")
        self.calls += 1
        response = self.client.responses.parse(
            model=self.model, instructions=instructions, input=input_text,
            text_format=schema, max_output_tokens=4096,
        )
        if response.status != "completed":
            raise ProviderDecisionError("the provider response did not complete")
        if any(item.type in {"function_call", "custom_tool_call"} for item in response.output):
            raise ProviderDecisionError("expected a decision, not a tool call")
        if not isinstance(response.output_parsed, schema):
            raise ProviderDecisionError("the provider returned no parsed decision of the required type")
        value = schema.model_validate(response.output_parsed)
        self.decisions.append(value.model_dump(mode="json"))
        return value


class DeepSeekSemanticRouter:
    def __init__(self, model: StructuredClient) -> None:
        self.model = model

    def decide(self, request: str) -> RouteDecision:
        return self.model.parse(RouteDecision, instructions=ROUTER_INSTRUCTIONS, input_text=request)


class DeepSeekPlanner:
    def __init__(self, model: StructuredClient) -> None:
        self.model = model

    def make_plan(
        self, task: WeatherTask, *, completed: Mapping[str, Reading], failures: tuple[Failure, ...]
    ) -> Plan:
        context = {
            "task": task.model_dump(mode="json"),
            "completed": {key: asdict(value) for key, value in completed.items()},
            "failures": [asdict(failure) for failure in failures],
        }
        return self.model.parse(
            Plan, instructions=PLANNER_INSTRUCTIONS,
            input_text=json.dumps(context, ensure_ascii=False, allow_nan=False),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Live DeepSeek decisions; service usage applies.")
    parser.add_argument("--mode", choices=("route", "plan"), default="plan")
    parser.add_argument("--example", choices=tuple(EXAMPLES["en"]), default="compare")
    parser.add_argument("--question", help="Override the selected example with natural language.")
    parser.add_argument("--language", choices=("zh-CN", "en"), default="zh-CN")
    parser.add_argument("--failure", choices=("none", "primary"), default="none")
    parser.add_argument("--show-decisions", action="store_true")
    args = parser.parse_args()
    model_id = required_env("DEEPSEEK_MODEL")
    client = create_client()
    model = StructuredClient(client=client, model=model_id)
    status = 0
    try:
        print("live DeepSeek: API usage applies; weather data stays local")
        question = args.question if args.question is not None else EXAMPLES[args.language][args.example]
        routing = HybridRouter(DeepSeekSemanticRouter(model)).route(request=question)
        print("route:", routing.decision.route)
        if args.mode == "route" or routing.decision.route in {"help", "clarify"}:
            print(dispatch(routing, WeatherService(), language=args.language))
        else:
            task = task_from_decision(routing.decision, args.language)
            blocked = (("primary", task.cities[-1]),) if args.failure == "primary" else ()
            service = WeatherService(unavailable=blocked)
            run = run_with_replanning(task, planner=DeepSeekPlanner(model), executor=PlanExecutor(service))
            print_run(run)
            print("source calls:", service.calls)
            status = 0 if run.status == "completed" else 1
    finally:
        print("model requests attempted:", model.calls)
        if args.show_decisions:
            print(json.dumps(model.decisions, ensure_ascii=False, indent=2))
        client.close()
    raise SystemExit(status)


if __name__ == "__main__":
    main()
