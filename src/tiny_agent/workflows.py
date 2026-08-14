from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol

from .decision import StructuredDecisionModel


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RouteDecision:
    route: str
    reason: str


class Router(Protocol):
    def route(self, request: str) -> RouteDecision:
        ...


class RuleRouter:
    """Deterministic router evaluated from top to bottom."""

    def __init__(
        self,
        rules: list[tuple[str, Callable[[str], bool]]],
        *,
        fallback: str,
    ) -> None:
        self.rules = rules
        self.fallback = fallback

    def route(self, request: str) -> RouteDecision:
        for name, predicate in self.rules:
            if predicate(request):
                return RouteDecision(
                    route=name,
                    reason=f"Matched deterministic rule for {name!r}.",
                )
        return RouteDecision(
            route=self.fallback,
            reason="No deterministic rule matched; using configured fallback.",
        )


class LLMRouter:
    """Schema-constrained semantic router backed by a decision model."""

    def __init__(
        self,
        model: StructuredDecisionModel,
        routes: dict[str, str],
    ) -> None:
        if not routes:
            raise ValueError("routes must not be empty")
        self.model = model
        self.routes = dict(routes)

    def route(self, request: str) -> RouteDecision:
        route_names = list(self.routes)
        route_catalog = "\n".join(
            f"- {name}: {description}" for name, description in self.routes.items()
        )
        schema = {
            "type": "object",
            "properties": {
                "route": {"type": "string", "enum": route_names},
                "reason": {"type": "string"},
            },
            "required": ["route", "reason"],
            "additionalProperties": False,
        }
        decision = self.model.decide(
            prompt=(
                "Route the user request to exactly one destination.\n\n"
                f"Available routes:\n{route_catalog}\n\n"
                f"User request:\n{request}"
            ),
            instructions=(
                "You are a routing component, not a user-facing assistant. "
                "Choose the single best route from the provided catalog."
            ),
            schema_name="route_decision",
            schema=schema,
        )
        route = decision.get("route")
        reason = decision.get("reason")
        if route not in self.routes:
            raise RuntimeError(f"Router returned unknown route: {route!r}")
        if not isinstance(reason, str) or not reason.strip():
            raise RuntimeError("Router returned an empty reason")
        return RouteDecision(route=route, reason=reason)


@dataclass(frozen=True, slots=True)
class RoutingResult:
    decision: RouteDecision
    output: Any


class RoutingWorkflow:
    """Use one router decision, then deterministic dispatch."""

    def __init__(
        self,
        router: Router,
        handlers: dict[str, Callable[[str], Any]],
    ) -> None:
        if not handlers:
            raise ValueError("handlers must not be empty")
        self.router = router
        self.handlers = dict(handlers)

    def run(self, request: str) -> RoutingResult:
        decision = self.router.route(request)
        handler = self.handlers.get(decision.route)
        if handler is None:
            raise KeyError(f"No handler registered for route: {decision.route}")
        return RoutingResult(
            decision=decision,
            output=handler(request),
        )


# ---------------------------------------------------------------------------
# Planning and execution
# ---------------------------------------------------------------------------


class StepFailure(RuntimeError):
    """Expected executor failure whose message is safe to expose to a replanner.

    Unexpected exceptions are intentionally reduced to their exception type before
    entering control-plane state. This prevents arbitrary internal exception text
    from being copied into a model-backed replanner prompt.
    """


@dataclass(frozen=True, slots=True)
class PlanStep:
    id: str
    description: str


@dataclass(frozen=True, slots=True)
class Plan:
    objective: str
    steps: tuple[PlanStep, ...]


@dataclass(frozen=True, slots=True)
class StepResult:
    step: PlanStep
    success: bool
    output: str | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class PlanRunResult:
    success: bool
    initial_plan: Plan
    final_plan: Plan
    results: tuple[StepResult, ...]
    replans: int
    failure_reason: str | None = None


class Planner(Protocol):
    def plan(self, task: str) -> Plan:
        ...


class Replanner(Protocol):
    def replan(
        self,
        *,
        task: str,
        completed: tuple[StepResult, ...],
        failure: StepResult,
    ) -> Plan | None:
        """Return only the remaining plan, or ``None`` to stop."""
        ...


class StepRunner(Protocol):
    def run(
        self,
        *,
        task: str,
        step: PlanStep,
        completed: tuple[StepResult, ...],
    ) -> str:
        ...


class StructuredPlanner:
    """Generate a bounded high-level plan using schema-constrained output."""

    def __init__(
        self,
        model: StructuredDecisionModel,
        *,
        max_plan_steps: int = 6,
    ) -> None:
        if max_plan_steps <= 0:
            raise ValueError("max_plan_steps must be positive")
        self.model = model
        self.max_plan_steps = max_plan_steps

    def plan(self, task: str) -> Plan:
        schema = _plan_schema(self.max_plan_steps)
        data = self.model.decide(
            prompt=f"Create a high-level execution plan for this task:\n\n{task}",
            instructions=(
                "Return the smallest useful plan. Each step should describe one "
                "meaningful executor goal. Do not include steps that can be omitted."
            ),
            schema_name="execution_plan",
            schema=schema,
        )
        return _parse_plan(data)


class StructuredReplanner:
    """Replan only after a failed observation and return remaining work."""

    def __init__(
        self,
        model: StructuredDecisionModel,
        *,
        max_plan_steps: int = 6,
    ) -> None:
        if max_plan_steps <= 0:
            raise ValueError("max_plan_steps must be positive")
        self.model = model
        self.max_plan_steps = max_plan_steps

    def replan(
        self,
        *,
        task: str,
        completed: tuple[StepResult, ...],
        failure: StepResult,
    ) -> Plan | None:
        completed_text = "\n".join(
            f"- {result.step.id}: success={result.success}; "
            f"output={result.output!r}; error={result.error!r}"
            for result in completed
        )
        data = self.model.decide(
            prompt=(
                f"Original task:\n{task}\n\n"
                f"Execution history:\n{completed_text}\n\n"
                f"Failed step:\n{failure.step.id}: {failure.step.description}\n"
                f"Failure:\n{failure.error}\n\n"
                "Create a new plan containing only the remaining work needed to "
                "finish the original task. Do not repeat already successful work "
                "unless the failure makes it invalid."
            ),
            instructions=(
                "You are a bounded replanner. Replanning is exceptional recovery, "
                "not a reason to rewrite the plan after every successful step."
            ),
            schema_name="remaining_plan",
            schema=_plan_schema(self.max_plan_steps),
        )
        return _parse_plan(data)


class PlanExecutorWorkflow:
    """Plan once, execute deterministically, and replan only on failure.

    The planner does not execute work. The step runner does not decide the global
    strategy. The workflow owns budgets and the transition between the two.
    """

    def __init__(
        self,
        planner: Planner,
        step_runner: StepRunner,
        *,
        replanner: Replanner | None = None,
        max_plan_steps: int = 6,
        max_total_steps: int = 12,
        max_replans: int = 1,
    ) -> None:
        if max_plan_steps <= 0:
            raise ValueError("max_plan_steps must be positive")
        if max_total_steps <= 0:
            raise ValueError("max_total_steps must be positive")
        if max_replans < 0:
            raise ValueError("max_replans must be non-negative")
        self.planner = planner
        self.step_runner = step_runner
        self.replanner = replanner
        self.max_plan_steps = max_plan_steps
        self.max_total_steps = max_total_steps
        self.max_replans = max_replans

    def run(self, task: str) -> PlanRunResult:
        initial_plan = self.planner.plan(task)
        self._validate_plan(initial_plan)

        current_plan = initial_plan
        results: list[StepResult] = []
        replans = 0
        total_steps = 0

        while True:
            failure: StepResult | None = None

            for step in current_plan.steps:
                if total_steps >= self.max_total_steps:
                    return PlanRunResult(
                        success=False,
                        initial_plan=initial_plan,
                        final_plan=current_plan,
                        results=tuple(results),
                        replans=replans,
                        failure_reason=(
                            f"Execution exceeded max_total_steps={self.max_total_steps}"
                        ),
                    )

                total_steps += 1
                try:
                    output = self.step_runner.run(
                        task=task,
                        step=step,
                        completed=tuple(results),
                    )
                    result = StepResult(
                        step=step,
                        success=True,
                        output=str(output),
                    )
                except StepFailure as exc:
                    result = StepResult(
                        step=step,
                        success=False,
                        error=f"StepFailure: {exc}",
                    )
                except Exception as exc:
                    # Unexpected details stay outside the model-facing workflow state.
                    # A production observability layer should record the full exception.
                    result = StepResult(
                        step=step,
                        success=False,
                        error=type(exc).__name__,
                    )

                results.append(result)
                if not result.success:
                    failure = result
                    break

            if failure is None:
                return PlanRunResult(
                    success=True,
                    initial_plan=initial_plan,
                    final_plan=current_plan,
                    results=tuple(results),
                    replans=replans,
                )

            if self.replanner is None or replans >= self.max_replans:
                return PlanRunResult(
                    success=False,
                    initial_plan=initial_plan,
                    final_plan=current_plan,
                    results=tuple(results),
                    replans=replans,
                    failure_reason=failure.error,
                )

            next_plan = self.replanner.replan(
                task=task,
                completed=tuple(results),
                failure=failure,
            )
            replans += 1
            if next_plan is None:
                return PlanRunResult(
                    success=False,
                    initial_plan=initial_plan,
                    final_plan=current_plan,
                    results=tuple(results),
                    replans=replans,
                    failure_reason="Replanner chose to stop.",
                )

            self._validate_plan(next_plan)
            current_plan = next_plan

    def _validate_plan(self, plan: Plan) -> None:
        if not plan.objective.strip():
            raise ValueError("Plan objective must not be empty")
        if not plan.steps:
            raise ValueError("Plan must contain at least one step")
        if len(plan.steps) > self.max_plan_steps:
            raise ValueError(
                f"Plan has {len(plan.steps)} steps but max_plan_steps="
                f"{self.max_plan_steps}"
            )

        ids = [step.id for step in plan.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("Plan step ids must be unique")
        for step in plan.steps:
            if not step.id.strip() or not step.description.strip():
                raise ValueError("Plan steps require non-empty id and description")


def _plan_schema(max_plan_steps: int) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "objective": {"type": "string"},
            "steps": {
                "type": "array",
                "minItems": 1,
                "maxItems": max_plan_steps,
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "description": {"type": "string"},
                    },
                    "required": ["id", "description"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["objective", "steps"],
        "additionalProperties": False,
    }


def _parse_plan(data: dict[str, Any]) -> Plan:
    objective = data.get("objective")
    raw_steps = data.get("steps")
    if not isinstance(objective, str) or not objective.strip():
        raise RuntimeError("Planner returned an invalid objective")
    if not isinstance(raw_steps, list) or not raw_steps:
        raise RuntimeError("Planner returned no steps")

    steps: list[PlanStep] = []
    for raw in raw_steps:
        if not isinstance(raw, dict):
            raise RuntimeError("Each plan step must be an object")
        step_id = raw.get("id")
        description = raw.get("description")
        if not isinstance(step_id, str) or not step_id.strip():
            raise RuntimeError("Planner returned a step without a valid id")
        if not isinstance(description, str) or not description.strip():
            raise RuntimeError("Planner returned a step without a description")
        steps.append(PlanStep(id=step_id, description=description))

    return Plan(objective=objective, steps=tuple(steps))
