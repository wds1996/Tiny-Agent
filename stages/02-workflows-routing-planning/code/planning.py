"""Validate a weather plan, execute it, and replan remaining read-only work."""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from typing import Literal, Mapping, Protocol

from pydantic import Field, model_validator

from workflow import (
    City, Contract, Reading, Source, SourceUnavailable, WeatherService,
    WeatherTask, convert_temperature, render_brief,
)


class PlanStep(Contract):
    step_id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,31}$")
    operation: Literal["read_weather", "convert_temperature", "write_brief"]
    inputs: tuple[str, ...] = Field(default=(), max_length=2)
    city: City | None = None
    source: Source | None = None

    @model_validator(mode="after")
    def check_shape(self) -> "PlanStep":
        if len(set(self.inputs)) != len(self.inputs):
            raise ValueError("input references must not repeat")
        if self.operation == "read_weather":
            if self.city is None or self.source is None or self.inputs:
                raise ValueError("read_weather needs city/source and no inputs")
        elif self.city is not None or self.source is not None:
            raise ValueError("derived steps take input references, not city/source")
        elif self.operation == "convert_temperature" and len(self.inputs) != 1:
            raise ValueError("conversion needs exactly one input")
        elif self.operation == "write_brief" and not self.inputs:
            raise ValueError("the brief needs at least one input")
        return self


class Plan(Contract):
    goal: str = Field(min_length=1, max_length=300)
    steps: tuple[PlanStep, ...] = Field(min_length=1, max_length=5)

    @model_validator(mode="after")
    def check_ids(self) -> "Plan":
        if not self.goal.strip():
            raise ValueError("goal must not be blank")
        ids = [step.step_id for step in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("step IDs must be unique within a plan")
        return self


@dataclass(frozen=True)
class Failure:
    step_id: str
    city: str
    source: str
    code: str = "source_unavailable"


class PlanRejected(ValueError):
    pass


class ExecutionBudgetExceeded(RuntimeError):
    pass


class Planner(Protocol):
    def make_plan(
        self, task: WeatherTask, *, completed: Mapping[str, Reading], failures: tuple[Failure, ...]
    ) -> Plan: ...


def validate_plan(
    plan: Plan, task: WeatherTask, completed: Mapping[str, Reading], failures: tuple[Failure, ...]
) -> Plan:
    """Check order, result types, source eligibility and the requested final product."""
    plan = Plan.model_validate(plan)
    known = {key: (value.city, value.temperature_f is not None) for key, value in completed.items()}
    blocked = {(failure.source, failure.city) for failure in failures}
    for index, step in enumerate(plan.steps):
        if step.step_id in known:
            raise PlanRejected("a new step cannot overwrite a completed result")
        if not set(step.inputs).issubset(known):
            raise PlanRejected("an input refers to a missing or future result")
        if step.operation == "read_weather":
            if step.city not in task.cities:
                raise PlanRejected("the plan requests a city outside the task")
            if any(city == step.city for city, _ in known.values()):
                raise PlanRejected("the plan repeats a completed or planned city lookup")
            if (step.source, step.city) in blocked:
                raise PlanRejected("the plan selects a source already observed unavailable")
            if step.source == "backup" and ("primary", step.city) not in blocked:
                raise PlanRejected("backup requires an observed primary failure for that city")
            known[step.step_id] = (step.city, False)
        elif step.operation == "convert_temperature":
            city, converted = known[step.inputs[0]]
            if converted or not task.fahrenheit or (city, True) in known.values():
                raise PlanRejected("conversion is repeated or not requested")
            known[step.step_id] = (city, True)
        else:
            if index != len(plan.steps) - 1:
                raise PlanRejected("write_brief must be the final step")
            products = [known[key] for key in step.inputs]
            expected = {(city, task.fahrenheit) for city in task.cities}
            if len(products) != len(expected) or set(products) != expected:
                raise PlanRejected("the brief omits a city or has the wrong units")
    if plan.steps[-1].operation != "write_brief":
        raise PlanRejected("the plan does not finish the requested brief")
    return plan


class ScriptedPlanner:
    """A deterministic builder for these tiny tasks; not a language model."""

    def make_plan(
        self, task: WeatherTask, *, completed: Mapping[str, Reading], failures: tuple[Failure, ...]
    ) -> Plan:
        blocked = {(failure.source, failure.city) for failure in failures}
        steps: list[PlanStep] = []
        raw = {r.city: key for key, r in completed.items() if r.temperature_f is None}
        converted = {r.city: key for key, r in completed.items() if r.temperature_f is not None}
        for city in task.cities:
            if city not in raw and city not in converted:
                key = "weather_" + city.lower()
                source = "backup" if ("primary", city) in blocked else "primary"
                steps.append(PlanStep(step_id=key, operation="read_weather", city=city, source=source))
                raw[city] = key
        for city in task.cities:
            if task.fahrenheit and city not in converted:
                key = "fahrenheit_" + city.lower()
                steps.append(PlanStep(step_id=key, operation="convert_temperature", inputs=(raw[city],)))
                converted[city] = key
        inputs = tuple((converted if task.fahrenheit else raw)[city] for city in task.cities)
        steps.append(PlanStep(step_id="brief", operation="write_brief", inputs=inputs))
        return Plan(goal="Produce the requested teaching-weather brief.", steps=tuple(steps))


@dataclass(frozen=True)
class StepEvent:
    plan_number: int
    step_id: str
    operation: str
    status: str


@dataclass
class PlanRun:
    status: str = "running"
    answer: str | None = None
    completed: dict[str, Reading] = field(default_factory=dict)
    failures: list[Failure] = field(default_factory=list)
    plans: list[Plan] = field(default_factory=list)
    events: list[StepEvent] = field(default_factory=list)
    plan_calls: int = 0
    execution_steps: int = 0
    error: str | None = None


class PlanExecutor:
    def __init__(self, service: WeatherService) -> None:
        self.service = service

    def execute(
        self, plan: Plan, task: WeatherTask, run: PlanRun, *, max_execution_steps: int
    ) -> str:
        task = WeatherTask.model_validate(task)
        plan = validate_plan(plan, task, run.completed, tuple(run.failures))
        for step in plan.steps:
            if run.execution_steps >= max_execution_steps:
                raise ExecutionBudgetExceeded("the whole run's execution budget is exhausted")
            run.execution_steps += 1
            try:
                value = self._execute_step(step, task, run.completed)
            except SourceUnavailable as exc:
                run.failures.append(Failure(step.step_id, exc.city, exc.source))
                run.events.append(StepEvent(run.plan_calls, step.step_id, step.operation, "source_unavailable"))
                raise
            except Exception:
                run.events.append(StepEvent(run.plan_calls, step.step_id, step.operation, "execution_error"))
                raise
            run.events.append(StepEvent(run.plan_calls, step.step_id, step.operation, "ok"))
            if step.operation == "write_brief":
                return value
            run.completed[step.step_id] = value
        raise PlanRejected("missing final brief")

    def _execute_step(self, step: PlanStep, task: WeatherTask, results: Mapping[str, Reading]) -> Reading | str:
        if step.operation == "read_weather":
            return self.service.read(step.city, step.source)
        if step.operation == "convert_temperature":
            return convert_temperature(results[step.inputs[0]])
        if step.operation == "write_brief":
            return render_brief(task, tuple(results[key] for key in step.inputs))
        raise PlanRejected("unknown operation")


def run_with_replanning(
    task: WeatherTask, *, planner: Planner, executor: PlanExecutor,
    max_replans: int = 1, max_execution_steps: int = 8,
) -> PlanRun:
    task = WeatherTask.model_validate(task)
    if type(max_replans) is not int or max_replans < 0:
        raise ValueError("max_replans must be a nonnegative integer")
    if type(max_execution_steps) is not int or max_execution_steps < 0:
        raise ValueError("max_execution_steps must be a nonnegative integer")
    run = PlanRun()
    try:
        for _ in range(max_replans + 1):
            if run.execution_steps >= max_execution_steps:
                raise ExecutionBudgetExceeded("no execution budget remains; do not ask for another plan")
            run.plan_calls += 1
            plan = planner.make_plan(task, completed=dict(run.completed), failures=tuple(run.failures))
            plan = validate_plan(plan, task, run.completed, tuple(run.failures))
            run.plans.append(plan)
            try:
                run.answer = executor.execute(plan, task, run, max_execution_steps=max_execution_steps)
                run.status = "completed"
                return run
            except SourceUnavailable:
                if run.plan_calls == max_replans + 1:
                    raise
        raise RuntimeError("unreachable")
    except Exception as exc:
        # Failure is observable, not another planning opportunity. Never retry arbitrary errors.
        run.status = "failed"
        run.error = type(exc).__name__
        return run


def print_run(run: PlanRun) -> None:
    for number, plan in enumerate(run.plans, 1):
        print(f"plan {number}:")
        for step in plan.steps:
            details = f"{step.source}/{step.city}" if step.operation == "read_weather" else ",".join(step.inputs)
            print(f"  {step.step_id}: {step.operation}({details})")
        for event in run.events:
            if event.plan_number == number:
                print(f"    executed {event.step_id}: {event.status}")
    print("status:", run.status, "plan calls:", run.plan_calls, "execution steps:", run.execution_steps)
    print(run.answer if run.answer is not None else f"No completed brief: {run.error}")
    print("retained result IDs:", list(run.completed))


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline planning and bounded replanning.")
    parser.add_argument("--cities", nargs="+", choices=("Tokyo", "Paris"), default=["Tokyo", "Paris"])
    parser.add_argument("--celsius-only", action="store_true")
    parser.add_argument("--failure", choices=("none", "primary", "both"), default="primary")
    parser.add_argument("--max-replans", type=int, default=1)
    parser.add_argument("--max-steps", type=int, default=8)
    parser.add_argument("--language", choices=("zh-CN", "en"), default="zh-CN")
    args = parser.parse_args()
    blocked = () if args.failure == "none" else (("primary", args.cities[-1]),)
    if args.failure == "both":
        blocked += (("backup", args.cities[-1]),)
    service = WeatherService(unavailable=blocked)
    task = WeatherTask(cities=tuple(args.cities), fahrenheit=not args.celsius_only, language=args.language)
    run = run_with_replanning(task, planner=ScriptedPlanner(), executor=PlanExecutor(service),
                              max_replans=args.max_replans, max_execution_steps=args.max_steps)
    print("offline planner: no live LLM")
    print_run(run)
    print("source calls:", service.calls)
    raise SystemExit(0 if run.status == "completed" else 1)


if __name__ == "__main__":
    main()
