from __future__ import annotations

import os
from typing import Any

from pydantic import ValidationError

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
            "The OpenAI-compatible Python SDK is not installed. Run:\n"
            "python -m pip install -r "
            "stages/02-workflows-routing-planning/code/requirements.txt"
        ) from exc

    return OpenAI(
        api_key=required_env("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com",
    )


class DeepSeekSemanticRouter(SemanticRouter):
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


class DeepSeekPlanner(Planner):
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

        instructions = (
            "Create a short executable plan using only these operations: "
            f"{', '.join(operation.value for operation in Operation)}. "
            "Return exactly three steps in this order: "
            "(1) weather: read Tokyo with read_primary_weather, or with "
            "read_backup_weather only after a primary-source failure; this step "
            "uses city='Tokyo' and no source references. "
            "(2) convert: convert_temperature; depends_on=['weather'] and "
            "source_step='weather'; it has no city or conversion_step. "
            "(3) brief: write_brief; depends_on=['weather', 'convert'], "
            "source_step='weather', and conversion_step='convert'. "
            "write_brief never has a city field: it receives the city through "
            "source_step. Use these exact step_id values and do not add steps."
        )
        input_text = f"Task: {task}\n{failure_text}"
        validation_error: ValidationError | None = None

        for attempt in range(2):
            retry_note = ""
            if validation_error is not None:
                retry_note = (
                    "\nYour previous plan was rejected by the application validator: "
                    f"{validation_error}. Return a corrected plan that follows the "
                    "required step shapes exactly."
                )
            try:
                response = self.client.responses.parse(
                    model=self.model,
                    instructions=instructions + retry_note,
                    input=input_text,
                    text_format=Plan,
                )
            except ValidationError as exc:
                validation_error = exc
                if attempt == 0:
                    continue
                raise RuntimeError(
                    "The planner returned an invalid Plan after one corrective retry."
                ) from exc

            if response.status != "completed" or response.output_parsed is None:
                raise RuntimeError("The planner did not return a valid Plan.")
            return response.output_parsed

        raise AssertionError("unreachable")


def main() -> None:
    client = create_client()
    model = required_env("DEEPSEEK_MODEL")

    router = HybridRouter(DeepSeekSemanticRouter(client=client, model=model))
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
        planner=DeepSeekPlanner(client=client, model=model),
        executor=PlanExecutor(primary_available=False),
        max_replans=1,
    )
    print("\nfinal answer:")
    print(answer)


if __name__ == "__main__":
    main()
