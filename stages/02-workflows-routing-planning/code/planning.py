from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator


TEACHING_WEATHER = {
    "Tokyo": {"temperature_c": 18.0, "condition": "cloudy"},
    "Paris": {"temperature_c": 12.0, "condition": "light rain"},
}


class Operation(str, Enum):
    READ_PRIMARY_WEATHER = "read_primary_weather"
    READ_BACKUP_WEATHER = "read_backup_weather"
    CONVERT_TEMPERATURE = "convert_temperature"
    WRITE_BRIEF = "write_brief"


class PlanStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str = Field(min_length=1)
    operation: Operation
    depends_on: list[str] = Field(default_factory=list)
    city: Literal["Tokyo", "Paris"] | None = None
    source_step: str | None = None
    conversion_step: str | None = None

    @model_validator(mode="after")
    def validate_operation_inputs(self) -> "PlanStep":
        if self.operation in {
            Operation.READ_PRIMARY_WEATHER,
            Operation.READ_BACKUP_WEATHER,
        }:
            if self.city is None:
                raise ValueError("weather lookup steps require city")
            if self.source_step is not None or self.conversion_step is not None:
                raise ValueError("weather lookup steps do not use source references")

        elif self.operation is Operation.CONVERT_TEMPERATURE:
            if self.source_step is None:
                raise ValueError("convert_temperature requires source_step")
            if self.city is not None or self.conversion_step is not None:
                raise ValueError("convert_temperature accepts only source_step")

        elif self.operation is Operation.WRITE_BRIEF:
            if self.source_step is None or self.conversion_step is None:
                raise ValueError(
                    "write_brief requires source_step and conversion_step"
                )
            if self.city is not None:
                raise ValueError("write_brief does not take city directly")

        return self


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str = Field(min_length=1)
    steps: list[PlanStep] = Field(min_length=1, max_length=5)

    @model_validator(mode="after")
    def validate_dependencies(self) -> "Plan":
        seen: set[str] = set()

        for step in self.steps:
            if step.step_id in seen:
                raise ValueError(f"duplicate step_id: {step.step_id}")

            for dependency in step.depends_on:
                if dependency not in seen:
                    raise ValueError(
                        f"step {step.step_id!r} depends on unavailable "
                        f"step {dependency!r}"
                    )

            referenced = {
                value
                for value in (step.source_step, step.conversion_step)
                if value is not None
            }
            if not referenced.issubset(seen):
                missing = sorted(referenced - seen)
                raise ValueError(
                    f"step {step.step_id!r} references unavailable steps: {missing}"
                )

            seen.add(step.step_id)

        return self


class StepFailure(RuntimeError):
    def __init__(
        self,
        *,
        step_id: str,
        operation: Operation,
        message: str,
    ) -> None:
        super().__init__(message)
        self.step_id = step_id
        self.operation = operation
        self.message = message


class Planner(Protocol):
    def make_plan(
        self,
        task: str,
        *,
        failure: StepFailure | None = None,
    ) -> Plan:
        """Return a bounded plan for the task and optional observed failure."""


class ScriptedPlanner:
    """Deterministic planner used to make planning and replanning observable."""

    def make_plan(
        self,
        task: str,
        *,
        failure: StepFailure | None = None,
    ) -> Plan:
        del task

        lookup_operation = (
            Operation.READ_BACKUP_WEATHER
            if failure is not None
            else Operation.READ_PRIMARY_WEATHER
        )

        return Plan(
            goal="Read Tokyo's teaching weather and report Celsius and Fahrenheit.",
            steps=[
                PlanStep(
                    step_id="weather",
                    operation=lookup_operation,
                    city="Tokyo",
                ),
                PlanStep(
                    step_id="convert",
                    operation=Operation.CONVERT_TEMPERATURE,
                    depends_on=["weather"],
                    source_step="weather",
                ),
                PlanStep(
                    step_id="brief",
                    operation=Operation.WRITE_BRIEF,
                    depends_on=["weather", "convert"],
                    source_step="weather",
                    conversion_step="convert",
                ),
            ],
        )


class PlanExecutor:
    def __init__(
        self,
        *,
        primary_available: bool = False,
        max_execution_steps: int = 8,
    ) -> None:
        if max_execution_steps < 1:
            raise ValueError("max_execution_steps must be at least 1")
        self.primary_available = primary_available
        self.max_execution_steps = max_execution_steps

    def execute(self, plan: Plan) -> str:
        results: dict[str, Any] = {}

        for index, step in enumerate(plan.steps, start=1):
            if index > self.max_execution_steps:
                raise RuntimeError("execution step budget exhausted")

            results[step.step_id] = self._execute_step(step, results)

        final_step = plan.steps[-1]
        final_result = results[final_step.step_id]
        if not isinstance(final_result, str):
            raise RuntimeError("the final plan step must produce text")
        return final_result

    def _execute_step(
        self,
        step: PlanStep,
        results: dict[str, Any],
    ) -> Any:
        if step.operation is Operation.READ_PRIMARY_WEATHER:
            if not self.primary_available:
                raise StepFailure(
                    step_id=step.step_id,
                    operation=step.operation,
                    message="primary teaching weather source is unavailable",
                )
            return self._read_weather(step.city)

        if step.operation is Operation.READ_BACKUP_WEATHER:
            return self._read_weather(step.city)

        if step.operation is Operation.CONVERT_TEMPERATURE:
            weather = results[step.source_step]
            temperature_c = float(weather["temperature_c"])
            return {"temperature_f": round(temperature_c * 9 / 5 + 32, 1)}

        if step.operation is Operation.WRITE_BRIEF:
            weather = results[step.source_step]
            conversion = results[step.conversion_step]
            return (
                f"{weather['city']}: {weather['temperature_c']}°C / "
                f"{conversion['temperature_f']}°F, {weather['condition']}."
            )

        raise RuntimeError(f"unsupported operation: {step.operation}")

    @staticmethod
    def _read_weather(city: str | None) -> dict[str, Any]:
        if city is None:
            raise RuntimeError("city must be present after plan validation")
        record = TEACHING_WEATHER[city]
        return {"city": city, **record}


def run_with_replanning(
    task: str,
    *,
    planner: Planner,
    executor: PlanExecutor,
    max_replans: int = 1,
) -> str:
    if max_replans < 0:
        raise ValueError("max_replans must not be negative")

    failure: StepFailure | None = None

    for attempt in range(max_replans + 1):
        plan = planner.make_plan(task, failure=failure)
        print(f"\nplan attempt {attempt + 1}:")
        for step in plan.steps:
            print(f"- {step.step_id}: {step.operation.value}")

        try:
            return executor.execute(plan)
        except StepFailure as exc:
            failure = exc
            print(
                f"observed failure: {exc.step_id} / "
                f"{exc.operation.value} / {exc.message}"
            )
            if attempt == max_replans:
                raise

    raise AssertionError("unreachable")


def main() -> None:
    answer = run_with_replanning(
        "Read Tokyo's teaching weather and convert it to Fahrenheit.",
        planner=ScriptedPlanner(),
        executor=PlanExecutor(primary_available=False),
        max_replans=1,
    )
    print("\nfinal answer:")
    print(answer)


if __name__ == "__main__":
    main()
