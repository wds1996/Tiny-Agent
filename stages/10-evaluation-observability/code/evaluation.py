"""Score outcomes and behavior separately, and compare matching experiments."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from statistics import mean
import time
from uuid import uuid4

from tracing import Trace, Tracer
from typing import Callable, Sequence

from contracts import AgentRun, Request, ToolRecord


@dataclass(frozen=True)
class EvalCase:
    id: str
    request: Request
    expected_decision: str
    allowed_paths: tuple[tuple[ToolRecord, ...], ...]
    required_evidence: tuple[str, ...] = ()
    critical: bool = False


@dataclass(frozen=True)
class CaseScore:
    case_id: str
    run_id: str
    execution_ok: bool
    decision_ok: bool
    evidence_ok: bool
    trajectory_ok: bool
    diagnostics_ok: bool

    @property
    def passed(self) -> bool:
        return all((self.execution_ok, self.decision_ok, self.evidence_ok,
                    self.trajectory_ok, self.diagnostics_ok))

    @property
    def failures(self) -> tuple[str, ...]:
        return tuple(name for name in ("execution", "decision", "evidence", "trajectory", "diagnostics")
                     if not getattr(self, f"{name}_ok"))


def score_case(case: EvalCase, run: AgentRun) -> CaseScore:
    answer = run.answer
    citations = set(answer.evidence_ids) if answer else set()
    return CaseScore(
        case.id, run.run_id,
        execution_ok=run.error is None and answer is not None,
        decision_ok=answer is not None and answer.decision == case.expected_decision,
        evidence_ok=(answer is not None and citations == set(case.required_evidence)
                     and citations <= set(run.visible_ids)
                     and citations <= set(run.retrieved_ids)),
        trajectory_ok=run.calls in case.allowed_paths,
        diagnostics_ok=(run.trace.run_id == run.run_id and bool(run.trace.spans)
                        and not run.trace.dropped_spans and not run.trace.telemetry_errors),
    )


def percentile(values: Sequence[float], fraction: float = .95) -> float:
    """Nearest-rank sample quantile; it is not a population guarantee."""
    if not values or not 0 < fraction <= 1:
        raise ValueError("nonempty values and 0 < fraction <= 1 required")
    if any(not math.isfinite(x) or x < 0 for x in values):
        raise ValueError("invalid measured value")
    return sorted(values)[math.ceil(fraction * len(values)) - 1]


def recall_at_k(ranked_ids: Sequence[str], relevant_ids: set[str], *, k: int) -> float | None:
    if type(k) is not int or k < 1:
        raise ValueError("k must be a positive integer")
    if not relevant_ids:
        return None  # no relevant item: not a positive retrieval-quality test
    return len(set(ranked_ids[:k]) & relevant_ids) / len(relevant_ids)


def reciprocal_rank(ranked_ids: Sequence[str], relevant_ids: set[str]) -> float | None:
    if not relevant_ids:
        return None
    return next((1 / i for i, item in enumerate(ranked_ids, 1) if item in relevant_ids), 0.0)


@dataclass(frozen=True)
class EvalReport:
    variant: str
    suite_fingerprint: str
    scores: tuple[CaseScore, ...]
    runs: tuple[AgentRun, ...]
    critical_ids: tuple[str, ...]

    @property
    def pass_rate(self) -> float:
        return mean(score.passed for score in self.scores)

    def metrics(self) -> dict:
        costs = [run.estimated_cost_usd for run in self.runs]
        return {
            "cases": len(self.scores), "pass_rate": self.pass_rate,
            "average_tool_requests": mean(len(run.calls) for run in self.runs),
            "failed_tool_requests": sum(c.outcome == "failed" for r in self.runs for c in r.calls),
            "rejected_tool_requests": sum(c.outcome == "rejected" for r in self.runs for c in r.calls),
            "average_latency_ms": mean(run.latency_ms for run in self.runs),
            "p95_latency_ms": percentile([run.latency_ms for run in self.runs]),
            "model_calls": sum(run.model_calls for run in self.runs),
            "total_estimated_cost_usd": sum(costs) if all(c is not None for c in costs) else None,
            "cost_coverage": sum(c is not None for c in costs) / len(costs),
        }


def evaluate(cases: Sequence[EvalCase], runner: Callable[[Request], AgentRun], *, variant: str) -> EvalReport:
    if not cases or len({c.id for c in cases}) != len(cases):
        raise ValueError("cases must be nonempty with unique IDs")
    if any(not c.id or not c.allowed_paths for c in cases):
        raise ValueError("each case needs an ID and at least one allowed path")
    payload = json.dumps([asdict(c) for c in cases], sort_keys=True, ensure_ascii=False)
    fingerprint = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    runs, scores = [], []
    for case in cases:
        # Give the runner the input/environment only. Never pass expected labels.
        started = time.perf_counter()
        fallback = Trace(uuid4().hex)
        try:
            with Tracer(fallback).span("runner.invoke"):
                run = runner(case.request)
        except Exception:
            # Keep the failed case in the denominator; do not publish exception text.
            run = AgentRun(fallback.run_id, None, (), (), (),
                           (time.perf_counter() - started) * 1000, fallback,
                           error="runner_error", prompt_tokens=None, completion_tokens=None)
        if not isinstance(run, AgentRun):
            raise TypeError("runner must return AgentRun")
        if not math.isfinite(run.latency_ms) or run.latency_ms < 0:
            raise ValueError("invalid observed latency")
        if run.estimated_cost_usd is not None and (
            not math.isfinite(run.estimated_cost_usd) or run.estimated_cost_usd < 0
        ):
            raise ValueError("invalid estimated cost")
        runs.append(run)
        scores.append(score_case(case, run))
    if len({run.run_id for run in runs}) != len(runs):
        raise ValueError("each trial needs a distinct run ID")
    return EvalReport(variant, fingerprint, tuple(scores), tuple(runs),
                      tuple(c.id for c in cases if c.critical))


@dataclass(frozen=True)
class GateResult:
    accepted: bool
    reasons: tuple[str, ...]


def regression_gate(baseline: EvalReport, candidate: EvalReport, *, minimum_pass_rate: float = 1.0) -> GateResult:
    if not 0 <= minimum_pass_rate <= 1:
        raise ValueError("invalid minimum pass rate")
    if baseline.suite_fingerprint != candidate.suite_fingerprint:
        raise ValueError("cannot compare different inputs, labels or case order")
    before = {score.case_id: score for score in baseline.scores}
    reasons = []
    for score in candidate.scores:
        if before[score.case_id].passed and not score.passed:
            reasons.append(f"regressed:{score.case_id}")
        if score.case_id in candidate.critical_ids and not score.passed:
            reasons.append(f"critical_failed:{score.case_id}")
    if candidate.pass_rate < minimum_pass_rate:
        reasons.append("below_minimum_pass_rate")
    return GateResult(not reasons, tuple(reasons))


def report_dict(report: EvalReport) -> dict:
    # No question, raw answer, raw tool arguments, or API credentials in this export.
    return {
        "variant": report.variant, "suite_fingerprint": report.suite_fingerprint,
        "metrics": report.metrics(),
        "cases": [{**asdict(s), "passed": s.passed, "failures": s.failures} for s in report.scores],
        "runs": [{"run_id": r.run_id, "trace_id": r.trace.trace_id, "metadata": r.metadata, "error": r.error,
                  "model_calls": r.model_calls, "prompt_tokens": r.prompt_tokens,
                  "completion_tokens": r.completion_tokens} for r in report.runs],
    }
