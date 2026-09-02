from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import fmean
from typing import Any, Callable, Literal, Mapping, Protocol, Sequence

from .observability import SpanRecord


def _finite_number(value: Any, *, name: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise TypeError(f"{name} must be numeric")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{name} must be finite")
    return numeric


@dataclass(frozen=True, slots=True)
class ToolInvocation:
    name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    status: str = "ok"
    attempts: int = 1
    failure_code: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("tool invocation name must be non-empty")
        if not isinstance(self.arguments, Mapping):
            raise TypeError("tool invocation arguments must be a mapping")
        if not isinstance(self.attempts, int) or isinstance(self.attempts, bool):
            raise TypeError("attempts must be an integer")
        if self.attempts < 0:
            raise ValueError("attempts must be non-negative")


@dataclass(frozen=True, slots=True)
class EvalExample:
    id: str
    inputs: Mapping[str, Any]
    reference_output: Any | None = None
    expected_tools: tuple[str, ...] = ()
    reference_tool_calls: tuple[ToolInvocation, ...] = ()
    required_tool_sequence: tuple[str, ...] = ()
    forbidden_tools: tuple[str, ...] = ()
    max_tool_calls: int | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("example id must be non-empty")
        if not isinstance(self.inputs, Mapping):
            raise TypeError("example inputs must be a mapping")
        if self.max_tool_calls is not None and self.max_tool_calls < 0:
            raise ValueError("max_tool_calls must be non-negative")


@dataclass(frozen=True, slots=True)
class RunArtifact:
    output: Any
    spans: tuple[SpanRecord, ...] = ()
    tool_calls: tuple[ToolInvocation, ...] = ()
    metrics: Mapping[str, float] = field(default_factory=dict)
    error_type: str | None = None

    def __post_init__(self) -> None:
        for key, value in self.metrics.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError("metric keys must be non-empty strings")
            _finite_number(value, name=f"metric {key!r}")

    @property
    def successful(self) -> bool:
        return self.error_type is None


@dataclass(frozen=True, slots=True)
class EvalScore:
    key: str
    score: float
    comment: str = ""
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.key, str) or not self.key.strip():
            raise ValueError("score key must be non-empty")
        _finite_number(self.score, name="score")


class Evaluator(Protocol):
    def evaluate(self, example: EvalExample, run: RunArtifact) -> Sequence[EvalScore]:
        ...


class ExactMatchEvaluator:
    def __init__(self, key: str = "exact_match") -> None:
        self.key = key

    def evaluate(self, example: EvalExample, run: RunArtifact) -> Sequence[EvalScore]:
        score = 1.0 if run.output == example.reference_output else 0.0
        return (
            EvalScore(
                self.key,
                score,
                comment=(
                    "Actual output exactly matches the reference."
                    if score
                    else "Output differs from the reference."
                ),
            ),
        )


class ToolSelectionEvaluator:
    """Set-based Tool selection evaluator with order/arguments scored elsewhere."""

    def evaluate(self, example: EvalExample, run: RunArtifact) -> Sequence[EvalScore]:
        expected = set(example.expected_tools)
        actual = {call.name for call in run.tool_calls}

        if not expected and not actual:
            precision = recall = f1 = 1.0
        else:
            overlap = len(expected & actual)
            precision = overlap / len(actual) if actual else 0.0
            recall = overlap / len(expected) if expected else (1.0 if not actual else 0.0)
            f1 = (
                2 * precision * recall / (precision + recall)
                if precision + recall > 0
                else 0.0
            )

        details = {
            "expected": sorted(expected),
            "actual": sorted(actual),
            "missing": sorted(expected - actual),
            "unexpected": sorted(actual - expected),
        }
        return (
            EvalScore("tool_precision", precision, details=details),
            EvalScore("tool_recall", recall, details=details),
            EvalScore("tool_f1", f1, details=details),
        )


class ToolArgumentsEvaluator:
    """Exact Tool name + JSON-like argument comparison for offline evals."""

    def evaluate(self, example: EvalExample, run: RunArtifact) -> Sequence[EvalScore]:
        expected = example.reference_tool_calls
        actual = run.tool_calls
        if not expected and not actual:
            return (EvalScore("tool_argument_accuracy", 1.0),)

        denominator = max(len(expected), len(actual), 1)
        matches = 0
        mismatch_details: list[dict[str, Any]] = []
        for index in range(denominator):
            expected_call = expected[index] if index < len(expected) else None
            actual_call = actual[index] if index < len(actual) else None
            matched = (
                expected_call is not None
                and actual_call is not None
                and expected_call.name == actual_call.name
                and dict(expected_call.arguments) == dict(actual_call.arguments)
            )
            if matched:
                matches += 1
            else:
                mismatch_details.append(
                    {
                        "index": index,
                        "expected_tool": expected_call.name if expected_call else None,
                        "actual_tool": actual_call.name if actual_call else None,
                    }
                )
        return (
            EvalScore(
                "tool_argument_accuracy",
                matches / denominator,
                details={"mismatches": mismatch_details},
            ),
        )


class TrajectoryEvaluator:
    """Score required ordered coverage plus deterministic safety/efficiency constraints."""

    def evaluate(self, example: EvalExample, run: RunArtifact) -> Sequence[EvalScore]:
        actual = [call.name for call in run.tool_calls]
        required = list(example.required_tool_sequence)
        sequence_recall = 1.0 if not required else _lcs_length(required, actual) / len(required)
        forbidden_used = sorted(set(actual) & set(example.forbidden_tools))
        within_budget = example.max_tool_calls is None or len(actual) <= example.max_tool_calls
        policy_ok = not forbidden_used and within_budget
        return (
            EvalScore(
                "trajectory_sequence_recall",
                sequence_recall,
                details={"required": required, "actual": actual},
            ),
            EvalScore(
                "trajectory_policy_ok",
                1.0 if policy_ok else 0.0,
                details={
                    "forbidden_used": forbidden_used,
                    "tool_call_count": len(actual),
                    "max_tool_calls": example.max_tool_calls,
                },
            ),
        )


class RunMetricsEvaluator:
    def __init__(self, *metric_keys: str) -> None:
        if not metric_keys:
            raise ValueError("at least one metric key is required")
        self.metric_keys = metric_keys

    def evaluate(self, example: EvalExample, run: RunArtifact) -> Sequence[EvalScore]:
        del example
        return tuple(
            EvalScore(key, float(run.metrics[key]))
            for key in self.metric_keys
            if key in run.metrics
        )


class JudgeModel(Protocol):
    def judge(
        self,
        *,
        rubric: str,
        inputs: Mapping[str, Any],
        output: Any,
        reference_output: Any | None,
    ) -> Mapping[str, Any]:
        ...


class LLMJudgeEvaluator:
    """Provider-neutral LLM-as-judge boundary with strict [0, 1] score shape."""

    def __init__(self, *, key: str, rubric: str, judge_model: JudgeModel) -> None:
        if not key.strip() or not rubric.strip():
            raise ValueError("judge key and rubric must be non-empty")
        self.key = key
        self.rubric = rubric
        self.judge_model = judge_model

    def evaluate(self, example: EvalExample, run: RunArtifact) -> Sequence[EvalScore]:
        raw = self.judge_model.judge(
            rubric=self.rubric,
            inputs=example.inputs,
            output=run.output,
            reference_output=example.reference_output,
        )
        score = raw.get("score")
        comment = raw.get("comment", "")
        numeric = _finite_number(score, name="judge score")
        if not 0.0 <= numeric <= 1.0:
            raise ValueError("judge score must be between 0 and 1")
        if not isinstance(comment, str):
            raise ValueError("judge comment must be a string")
        return (EvalScore(self.key, numeric, comment=comment),)


Target = Callable[[Mapping[str, Any]], RunArtifact]


@dataclass(frozen=True, slots=True)
class ExampleEvaluation:
    example_id: str
    repetition: int
    run: RunArtifact
    scores: tuple[EvalScore, ...]


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    results: tuple[ExampleEvaluation, ...]
    mean_scores: Mapping[str, float]
    metric_counts: Mapping[str, int]

    def __post_init__(self) -> None:
        total = len(self.results)
        for key, value in self.mean_scores.items():
            if not isinstance(key, str) or not key.strip():
                raise ValueError("report metric keys must be non-empty")
            _finite_number(value, name=f"report metric {key!r}")
            count = self.metric_counts.get(key)
            if not isinstance(count, int) or isinstance(count, bool):
                raise TypeError(f"metric count for {key!r} must be an integer")
            if count <= 0 or count > total:
                raise ValueError(f"metric count for {key!r} is inconsistent with results")

    @property
    def total_runs(self) -> int:
        return len(self.results)

    def metric(self, key: str) -> float:
        if key not in self.mean_scores:
            raise KeyError(f"metric {key!r} is not present in the report")
        return float(self.mean_scores[key])

    def coverage(self, key: str) -> float:
        if self.total_runs == 0:
            return 0.0
        return self.metric_counts.get(key, 0) / self.total_runs


class EvaluationSuite:
    def __init__(self, evaluators: Sequence[Evaluator]) -> None:
        if not evaluators:
            raise ValueError("at least one evaluator is required")
        self.evaluators = tuple(evaluators)

    def run(
        self,
        dataset: Sequence[EvalExample],
        target: Target,
        *,
        repetitions: int = 1,
    ) -> EvaluationReport:
        if repetitions <= 0:
            raise ValueError("repetitions must be positive")
        if not dataset:
            raise ValueError("dataset must not be empty")

        results: list[ExampleEvaluation] = []
        values_by_key: dict[str, list[float]] = {}
        for example in dataset:
            for repetition in range(1, repetitions + 1):
                try:
                    run = target(dict(example.inputs))
                    if not isinstance(run, RunArtifact):
                        raise TypeError("evaluation target must return RunArtifact")
                except Exception as exc:
                    run = RunArtifact(output=None, error_type=type(exc).__name__)

                scores: list[EvalScore] = [
                    EvalScore(
                        "execution_success",
                        1.0 if run.successful else 0.0,
                        comment=(
                            "Target completed without an uncaught exception."
                            if run.successful
                            else f"Target raised {run.error_type}."
                        ),
                    )
                ]
                if run.successful:
                    for evaluator in self.evaluators:
                        scores.extend(evaluator.evaluate(example, run))

                seen: set[str] = set()
                for score in scores:
                    if score.key in seen:
                        raise ValueError(
                            f"duplicate metric key {score.key!r} within one example run"
                        )
                    seen.add(score.key)
                    values_by_key.setdefault(score.key, []).append(float(score.score))
                results.append(
                    ExampleEvaluation(
                        example_id=example.id,
                        repetition=repetition,
                        run=run,
                        scores=tuple(scores),
                    )
                )

        mean_scores = {key: fmean(values) for key, values in sorted(values_by_key.items()) if values}
        metric_counts = {key: len(values) for key, values in values_by_key.items()}
        return EvaluationReport(tuple(results), mean_scores, metric_counts)


MetricDirection = Literal["higher", "lower"]


@dataclass(frozen=True, slots=True)
class MetricGateRule:
    key: str
    direction: MetricDirection = "higher"
    absolute_limit: float | None = None
    max_regression: float | None = None
    min_coverage: float = 1.0

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValueError("gate metric key must be non-empty")
        if self.direction not in {"higher", "lower"}:
            raise ValueError("direction must be 'higher' or 'lower'")
        if self.absolute_limit is not None:
            _finite_number(self.absolute_limit, name="absolute_limit")
        if self.max_regression is not None:
            numeric = _finite_number(self.max_regression, name="max_regression")
            if numeric < 0:
                raise ValueError("max_regression must be non-negative")
        _finite_number(self.min_coverage, name="min_coverage")
        if not 0.0 <= self.min_coverage <= 1.0:
            raise ValueError("min_coverage must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class RegressionGateResult:
    passed: bool
    failures: tuple[str, ...]


class RegressionGate:
    """Turn evaluation metrics into explicit CI/release rules."""

    def __init__(self, rules: Sequence[MetricGateRule]) -> None:
        if not rules:
            raise ValueError("at least one gate rule is required")
        self.rules = tuple(rules)

    def check(
        self,
        candidate: EvaluationReport,
        *,
        baseline: EvaluationReport | None = None,
    ) -> RegressionGateResult:
        failures: list[str] = []
        for rule in self.rules:
            coverage = candidate.coverage(rule.key)
            if coverage < rule.min_coverage:
                failures.append(
                    f"{rule.key}: coverage {coverage:.4f} < required {rule.min_coverage:.4f}"
                )
                continue
            candidate_value = candidate.metric(rule.key)
            if rule.absolute_limit is not None:
                if rule.direction == "higher" and candidate_value < rule.absolute_limit:
                    failures.append(
                        f"{rule.key}: {candidate_value:.4f} < minimum {rule.absolute_limit:.4f}"
                    )
                if rule.direction == "lower" and candidate_value > rule.absolute_limit:
                    failures.append(
                        f"{rule.key}: {candidate_value:.4f} > maximum {rule.absolute_limit:.4f}"
                    )
            if baseline is not None and rule.max_regression is not None:
                if baseline.coverage(rule.key) < rule.min_coverage:
                    failures.append(f"{rule.key}: baseline coverage is below required coverage")
                    continue
                baseline_value = baseline.metric(rule.key)
                regression = (
                    baseline_value - candidate_value
                    if rule.direction == "higher"
                    else candidate_value - baseline_value
                )
                if regression > rule.max_regression:
                    failures.append(
                        f"{rule.key}: regression {regression:.4f} exceeds allowed "
                        f"{rule.max_regression:.4f}"
                    )
        return RegressionGateResult(not failures, tuple(failures))


def tool_invocations_from_spans(spans: Sequence[SpanRecord]) -> tuple[ToolInvocation, ...]:
    """Recover Tool names/status from privacy-safe traces, never raw arguments."""

    invocations: list[ToolInvocation] = []
    for span in sorted(spans, key=lambda item: item.start_time_ns):
        if span.kind != "tool":
            continue
        name = span.attributes.get("tool.name")
        if not isinstance(name, str) or not name:
            continue
        attempts_raw = span.attributes.get("tiny_agent.tool.attempts", 1)
        attempts = int(attempts_raw) if isinstance(attempts_raw, (int, float)) else 1
        failure_code = span.attributes.get("error.type")
        invocations.append(
            ToolInvocation(
                name=name,
                arguments={},
                status=span.status,
                attempts=attempts,
                failure_code=failure_code if isinstance(failure_code, str) else None,
            )
        )
    return tuple(invocations)


def _lcs_length(left: Sequence[str], right: Sequence[str]) -> int:
    previous = [0] * (len(right) + 1)
    for left_item in left:
        current = [0]
        for index, right_item in enumerate(right, start=1):
            if left_item == right_item:
                current.append(previous[index - 1] + 1)
            else:
                current.append(max(current[-1], previous[index]))
        previous = current
    return previous[-1]
