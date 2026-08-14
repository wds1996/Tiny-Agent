"""Stage 02: Structured Planner + Stage 01 ReAct Agent as the Executor.

Run from the repository root:

    pip install -e ".[openai]"
    export OPENAI_API_KEY="..."
    python stages/02-planning-routing/code/planner_executor_agent.py

This example uses small deterministic mock enterprise data as tools so the learning
focus stays on orchestration rather than external API setup.
"""

from tiny_agent import AgentRuntime, Tool, ToolRegistry
from tiny_agent.models import OpenAIResponsesModel
from tiny_agent.models.openai_structured import OpenAIStructuredDecisionModel
from tiny_agent.workflows import (
    PlanExecutorWorkflow,
    PlanStep,
    StepResult,
    StructuredPlanner,
)


# ---------------------------------------------------------------------------
# Deterministic mock enterprise capabilities
# ---------------------------------------------------------------------------


def get_service_health(service: str) -> str:
    data = {
        "checkout": (
            "checkout error rate rose from 1.2% to 18.4% at 09:10 UTC; "
            "latency also increased from 220 ms to 1.8 s"
        )
    }
    return data.get(service.lower(), f"No health data found for service={service!r}")


def get_recent_deployments(service: str) -> str:
    data = {
        "checkout": (
            "deploy checkout-2026.08.14-rc3 completed at 09:04 UTC; "
            "it changed payment-provider timeout and retry configuration"
        )
    }
    return data.get(service.lower(), f"No deployment data found for service={service!r}")


def get_error_summary(service: str) -> str:
    data = {
        "checkout": (
            "83% of new checkout failures are upstream payment timeout errors; "
            "the spike begins six minutes after checkout-2026.08.14-rc3"
        )
    }
    return data.get(service.lower(), f"No error summary found for service={service!r}")


SERVICE_SCHEMA = {
    "type": "object",
    "properties": {
        "service": {
            "type": "string",
            "description": "The service name to inspect, for example checkout.",
        }
    },
    "required": ["service"],
    "additionalProperties": False,
}


tools = ToolRegistry(
    [
        Tool(
            name="get_service_health",
            description="Read current health and latency/error metrics for a service.",
            parameters=SERVICE_SCHEMA,
            handler=get_service_health,
        ),
        Tool(
            name="get_recent_deployments",
            description="Read recent deployments and configuration changes for a service.",
            parameters=SERVICE_SCHEMA,
            handler=get_recent_deployments,
        ),
        Tool(
            name="get_error_summary",
            description="Read an aggregated summary of recent error classes for a service.",
            parameters=SERVICE_SCHEMA,
            handler=get_error_summary,
        ),
    ]
)


# ---------------------------------------------------------------------------
# One AgentRuntime invocation executes exactly one high-level PlanStep.
# ---------------------------------------------------------------------------


class AgentStepRunner:
    def __init__(self, runtime: AgentRuntime) -> None:
        self.runtime = runtime

    def run(
        self,
        *,
        task: str,
        step: PlanStep,
        completed: tuple[StepResult, ...],
    ) -> str:
        completed_text = "\n".join(
            f"- {result.step.id}: {result.output}"
            for result in completed
            if result.success
        ) or "(none)"

        result = self.runtime.run(
            "Complete exactly one assigned plan step.\n\n"
            f"Original task:\n{task}\n\n"
            f"Assigned step:\n{step.id}: {step.description}\n\n"
            f"Already completed results:\n{completed_text}\n\n"
            "Use tools only when they help complete this assigned step. Return a "
            "concise step result that the next step can use. Do not rewrite the "
            "global plan."
        )
        return result.output


# Planner uses structured output; Executor uses the Stage 01 ReAct runtime.
planner_model = OpenAIStructuredDecisionModel(
    model="gpt-5.6-luna",
    reasoning_effort="none",
)
planner = StructuredPlanner(planner_model, max_plan_steps=4)

executor_model = OpenAIResponsesModel(
    model="gpt-5.6-luna",
    reasoning_effort="none",
    strict_tools=True,
)
executor_runtime = AgentRuntime(
    model=executor_model,
    tools=tools,
    system_prompt=(
        "You are a scoped incident-analysis executor. Complete only the assigned "
        "step. Use available evidence tools when necessary and never invent tool "
        "results."
    ),
    max_steps=5,
)

workflow = PlanExecutorWorkflow(
    planner=planner,
    step_runner=AgentStepRunner(executor_runtime),
    max_plan_steps=4,
    max_total_steps=6,
    max_replans=0,
)


if __name__ == "__main__":
    task = (
        "Investigate why checkout errors increased this morning and prepare a concise "
        "evidence-based incident brief."
    )
    result = workflow.run(task)

    print("\nInitial plan")
    print("------------")
    for step in result.initial_plan.steps:
        print(f"- {step.id}: {step.description}")

    print("\nExecution")
    print("---------")
    for item in result.results:
        status = "OK" if item.success else "FAILED"
        print(f"[{status}] {item.step.id}: {item.output or item.error}")

    print("\nWorkflow result")
    print("---------------")
    print(f"success={result.success}, replans={result.replans}")
