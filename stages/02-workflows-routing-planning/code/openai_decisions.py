from __future__ import annotations

import os
from typing import Any

from planning import (
    Operation,
    Plan,
    PlanExecutor,
    Planner,
    StepFailure,
    run_with_replanning,
)
from routing import HybridRouter, RouteDecision, SemanticRouter, dispatch


def required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise RuntimeError(f"Set {name} before running this example.")
    return value.strip()


def create_client() -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "OpenAI SDK is not installed. Run:\n"
            "python -m pip install -r "
            "stages/02-workflows-routing-planning/code/requirements.txt"
        ) from exc

    required_env("OPENAI_API_KEY")
    return OpenAI()


class OpenAISemanticRouter(SemanticRouter):
    def __init__(self, *, client: Any, model: str) -> None:
        self.client = client
        self.model = model

    def decide(self, request: str) -> RouteDecision:
        response = self.client.responses.parse(
            model=self.model,
            instructions=(
                "Classify the user's request into exactly one route. "
                "weather: weather or forecast questions. "
                "account: invoices, billing, refunds, or account records. "
                "general: everything else. "
                "Return a short reason based only on the request."
            ),
            input=request,
            text_format=RouteDecision,
        )

        if response.status != "completed" or response.output_parsed is None:
            raise RuntimeError("The router did not return a valid RouteDecision.")

        return response.output_parsed


class OpenAIPlanner(Planner):
    def __init__(self, *, client: Any, model: str) -> None:
        self.client = client
        self.model = model

    def make_plan(
        self,
        task: str,
        *,
        failure: StepFailure | None = None,
    ) -> Plan:
        failure_text = (
            "No execution failure has been observed."
            if failure is None
            else (
                f"Observed failure: step_id={failure.step_id}; "
                f"operation={failure.operation.value}; message={failure.message}"
            )
        )

        response = self.client.responses.parse(
            model=self.model,
            instructions=(
                "Create a short executable plan using only these operations: "
                f"{', '.join(operation.value for operation in Operation)}. "
                "For the initial plan, read Tokyo with read_primary_weather. "
                "If the observed failure says the primary source is unavailable, "
                "use read_backup_weather instead. Then convert the weather step "
                "with convert_temperature and finish with write_brief. "
                "Use unique step_id values. A step may reference only earlier steps. "
                "Keep the plan to at most five steps."
            ),
            input=f"Task: {task}\n{failure_text}",
            text_format=Plan,
        )

        if response.status != "completed" or response.output_parsed is None:
            raise RuntimeError("The planner did not return a valid Plan.")

        return response.output_parsed


def main() -> None:
    client = create_client()
    model = required_env("OPENAI_MODEL")

    router = HybridRouter(OpenAISemanticRouter(client=client, model=model))
    request = "I was charged twice and I do not know which team should handle it."
    routing = router.route(request)

    print("=== routing ===")
    print("route:", routing.route.value)
    print("source:", routing.source)
    print("reason:", routing.reason)
    print("dispatch:", dispatch(request, routing))

    print("\n=== planning ===")
    answer = run_with_replanning(
        "Read Tokyo's teaching weather and report Celsius and Fahrenheit.",
        planner=OpenAIPlanner(client=client, model=model),
        executor=PlanExecutor(primary_available=False),
        max_replans=1,
    )
    print("\nfinal answer:")
    print(answer)


if __name__ == "__main__":
    main()
