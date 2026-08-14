"""Stage 02: bounded replanning without any API key.

Run from the repository root:

    python stages/02-planning-routing/code/bounded_replanning.py

The example is deterministic so you can inspect the control transition:

initial plan -> expected StepFailure -> one remaining-work replan -> success
"""

from tiny_agent.workflows import (
    Plan,
    PlanExecutorWorkflow,
    PlanStep,
    StepFailure,
    StepResult,
)


class InitialPlanner:
    def plan(self, task: str) -> Plan:
        return Plan(
            objective="Prepare an evidence-based incident brief",
            steps=(
                PlanStep("health", "Inspect current checkout service health."),
                PlanStep("primary_logs", "Read the primary checkout log service."),
                PlanStep("brief", "Write the incident brief from gathered evidence."),
            ),
        )


class FallbackReplanner:
    def replan(
        self,
        *,
        task: str,
        completed: tuple[StepResult, ...],
        failure: StepResult,
    ) -> Plan:
        # A real StructuredReplanner would receive the same safe workflow state and
        # generate this remaining-work plan with a schema-constrained model call.
        assert failure.step.id == "primary_logs"
        return Plan(
            objective="Finish the brief with the approved fallback evidence source",
            steps=(
                PlanStep(
                    "fallback_logs",
                    "Read the fallback aggregated error archive.",
                ),
                PlanStep(
                    "brief_after_fallback",
                    "Write the incident brief using completed health data and fallback logs.",
                ),
            ),
        )


class IncidentStepRunner:
    def run(
        self,
        *,
        task: str,
        step: PlanStep,
        completed: tuple[StepResult, ...],
    ) -> str:
        if step.id == "health":
            return "Checkout error rate is 18.4%, up from a 1.2% baseline."

        if step.id == "primary_logs":
            # StepFailure is an expected failure with a model-safe explanation.
            raise StepFailure(
                "Primary log service is unavailable; use an approved fallback source."
            )

        if step.id == "fallback_logs":
            return (
                "Fallback archive shows payment-provider timeout errors dominate the "
                "new failures."
            )

        if step.id == "brief_after_fallback":
            evidence = " | ".join(
                result.output or ""
                for result in completed
                if result.success
            )
            return f"Incident brief based on available evidence: {evidence}"

        if step.id == "brief":
            return "This original step should not run after the plan is invalidated."

        raise StepFailure(f"No executor is available for step {step.id!r}.")


workflow = PlanExecutorWorkflow(
    planner=InitialPlanner(),
    step_runner=IncidentStepRunner(),
    replanner=FallbackReplanner(),
    max_plan_steps=4,
    max_total_steps=6,
    max_replans=1,
)


if __name__ == "__main__":
    result = workflow.run("Prepare an incident brief for today's checkout outage.")

    print("Initial plan:")
    for step in result.initial_plan.steps:
        print(f"  - {step.id}: {step.description}")

    print("\nObserved execution:")
    for item in result.results:
        status = "OK" if item.success else "FAILED"
        print(f"  [{status}] {item.step.id}: {item.output or item.error}")

    print("\nFinal plan after recovery:")
    for step in result.final_plan.steps:
        print(f"  - {step.id}: {step.description}")

    print(f"\nsuccess={result.success}, replans={result.replans}")

    assert result.success is True
    assert result.replans == 1
