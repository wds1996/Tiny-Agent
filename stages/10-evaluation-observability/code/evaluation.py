from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence


@dataclass(frozen=True, slots=True)
class EvalCase:
    id: str
    question: str
    expected_answer_contains: tuple[str, ...]
    expected_tools: tuple[str, ...] = ()
    should_abstain: bool = False


@dataclass(frozen=True, slots=True)
class AgentRun:
    answer: str
    tools: tuple[str, ...]
    retrieved_ids: tuple[str, ...] = ()
    abstained: bool = False
    latency_ms: float = 0.0


@dataclass(frozen=True, slots=True)
class CaseScore:
    case_id: str
    answer_ok: bool
    tool_trajectory_ok: bool
    abstention_ok: bool

    @property
    def passed(self) -> bool:
        return self.answer_ok and self.tool_trajectory_ok and self.abstention_ok


@dataclass(frozen=True, slots=True)
class EvalReport:
    scores: tuple[CaseScore, ...]
    pass_rate: float
    unnecessary_tool_rate: float
    average_latency_ms: float


def score_case(case: EvalCase, run: AgentRun) -> CaseScore:
    normalized = run.answer.lower()
    answer_ok = all(piece.lower() in normalized for piece in case.expected_answer_contains)
    tool_ok = run.tools == case.expected_tools
    abstention_ok = run.abstained is case.should_abstain
    return CaseScore(case.id, answer_ok, tool_ok, abstention_ok)


def evaluate(cases: Sequence[EvalCase], runner: Callable[[EvalCase], AgentRun]) -> EvalReport:
    scores: list[CaseScore] = []
    unnecessary = 0
    total_tool_calls = 0
    total_latency = 0.0

    for case in cases:
        run = runner(case)
        scores.append(score_case(case, run))
        total_latency += run.latency_ms
        total_tool_calls += len(run.tools)
        if not case.expected_tools:
            unnecessary += len(run.tools)
        elif len(run.tools) > len(case.expected_tools):
            unnecessary += len(run.tools) - len(case.expected_tools)

    pass_rate = sum(score.passed for score in scores) / len(scores) if scores else 0.0
    unnecessary_tool_rate = unnecessary / total_tool_calls if total_tool_calls else 0.0
    average_latency_ms = total_latency / len(cases) if cases else 0.0
    return EvalReport(tuple(scores), pass_rate, unnecessary_tool_rate, average_latency_ms)


def recall_at_k(ranked_ids: Sequence[str], relevant_ids: set[str], *, k: int) -> float:
    if not relevant_ids:
        return 1.0
    retrieved = set(ranked_ids[:k])
    return len(retrieved & relevant_ids) / len(relevant_ids)
