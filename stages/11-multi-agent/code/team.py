"""Small, in-process team orchestration. Handlers and the driver are trusted code."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
import json
import math
import time
from typing import Any, Callable, Mapping, Sequence


class TeamError(RuntimeError):
    pass


class PolicyDenied(TeamError):
    pass


class BudgetExceeded(TeamError):
    pass


class OwnershipError(TeamError):
    pass


class InvalidResult(TeamError):
    pass


def json_copy(value: Any, *, limit: int = 16_000) -> Any:
    """Copy JSON data, rejecting oversized/non-JSON input rather than truncating it."""
    encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
    if len(encoded) > limit:
        raise ValueError("JSON character budget exceeded")
    return json.loads(encoded)


def project_context(context: Mapping[str, Any], keys: Sequence[str]) -> dict[str, Any]:
    return json_copy({key: context[key] for key in keys if key in context})


@dataclass(frozen=True)
class Principal:
    id: str
    roles: frozenset[str]

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id.strip():
            raise ValueError("principal id is required")
        if not isinstance(self.roles, frozenset) or not all(
            isinstance(role, str) and role for role in self.roles
        ):
            raise ValueError("roles must be a frozenset of nonempty strings")


@dataclass(frozen=True)
class Finding:
    status: str
    summary: str
    facts: dict[str, Any] = field(default_factory=dict)
    evidence_ids: tuple[str, ...] = ()


def validate_finding(value: Finding) -> Finding:
    if not isinstance(value, Finding) or value.status not in {"ok", "needs_input", "failed"}:
        raise InvalidResult("invalid finding status or type")
    if not isinstance(value.summary, str) or not value.summary.strip():
        raise InvalidResult("a finding needs a nonempty summary")
    if not isinstance(value.facts, dict):
        raise InvalidResult("facts must be an object")
    if not isinstance(value.evidence_ids, tuple) or not all(
        isinstance(item, str) and item for item in value.evidence_ids
    ):
        raise InvalidResult("evidence_ids must be a tuple of nonempty strings")
    if len(set(value.evidence_ids)) != len(value.evidence_ids):
        raise InvalidResult("duplicate evidence id")
    try:
        payload = json_copy(
            {"summary": value.summary, "facts": value.facts,
             "evidence_ids": value.evidence_ids}, limit=8_000
        )
    except (TypeError, ValueError) as exc:
        raise InvalidResult("finding is not bounded JSON") from exc
    return Finding(value.status, payload["summary"], payload["facts"], tuple(payload["evidence_ids"]))


@dataclass(frozen=True)
class AgentSpec:
    name: str
    assignment: str
    context_keys: tuple[str, ...]
    run: Callable[[str, dict[str, Any]], Finding]
    handoff_sources: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("agent name is required")
        if not isinstance(self.assignment, str) or not self.assignment.strip():
            raise ValueError("assignment is required")
        if not isinstance(self.context_keys, tuple) or not all(
            isinstance(key, str) and key for key in self.context_keys
        ) or len(set(self.context_keys)) != len(self.context_keys):
            raise ValueError("context keys must be unique strings")
        if not isinstance(self.handoff_sources, tuple) or not all(
            isinstance(source, str) and source for source in self.handoff_sources
        ):
            raise ValueError("handoff sources must be a tuple of agent names")
        if not callable(self.run):
            raise ValueError("run must be callable")


@dataclass(frozen=True)
class TeamPolicy:
    # (operation, caller, target) -> allowed authenticated roles
    grants: Mapping[tuple[str, str, str], frozenset[str]]

    def allows(self, principal: Principal, kind: str, caller: str, target: str) -> bool:
        return bool(principal.roles & self.grants.get((kind, caller, target), frozenset()))


@dataclass(frozen=True)
class TeamLimits:
    max_delegations: int = 4
    max_handoffs: int = 1
    max_workers: int = 2
    deadline_seconds: float = 90.0

    def __post_init__(self) -> None:
        for count in (self.max_delegations, self.max_handoffs, self.max_workers):
            if type(count) is not int or count < 0:
                raise ValueError("counts must be nonnegative integers")
        if self.max_workers < 1:
            raise ValueError("at least one worker is required")
        if (type(self.deadline_seconds) not in (int, float)
                or not math.isfinite(self.deadline_seconds) or self.deadline_seconds <= 0):
            raise ValueError("deadline must be positive and finite")


@dataclass(frozen=True)
class AgentMessage:
    run_id: str
    request_id: str
    agent: str
    finding: Finding
    error_code: str | None = None


@dataclass(frozen=True)
class TeamEvent:
    run_id: str
    request_id: str
    kind: str
    caller: str
    target: str
    status: str
    context_keys: tuple[str, ...]
    elapsed_ms: float
    error_code: str | None = None


class TeamRuntime:
    """One trusted driver per run; parallel handlers never mutate runtime state."""

    def __init__(
        self, agents: Sequence[AgentSpec], *, run_id: str, principal: Principal,
        context: dict[str, Any], policy: TeamPolicy, owner: str = "coordinator",
        limits: TeamLimits = TeamLimits(), clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if (not isinstance(run_id, str) or not run_id.strip()
                or not isinstance(owner, str) or not owner.strip()):
            raise ValueError("run_id and owner are required")
        self._agents = {agent.name: agent for agent in agents}
        if len(self._agents) != len(agents):
            raise ValueError("duplicate agent name")
        self.run_id = run_id
        self._principal = principal
        self._policy = TeamPolicy({key: frozenset(roles) for key, roles in policy.grants.items()})
        self._context = json_copy(context)
        self._owner = owner
        self._handoff_path = [owner]
        self._limits = limits
        self._clock = clock
        self._deadline = clock() + limits.deadline_seconds
        self._delegations = 0
        self._handoffs = 0
        self._sequence = 0
        self._messages: list[AgentMessage] = []
        self._events: list[TeamEvent] = []
        self._closed = False

    @property
    def owner(self) -> str:
        return self._owner

    @property
    def calls_used(self) -> int:
        return self._delegations + self._handoffs

    @property
    def events(self) -> tuple[TeamEvent, ...]:
        return tuple(self._events)

    @property
    def messages(self) -> tuple[AgentMessage, ...]:
        return tuple(
            AgentMessage(m.run_id, m.request_id, m.agent, validate_finding(m.finding), m.error_code)
            for m in self._messages
        )

    def _check_owner(self, caller: str) -> None:
        if self._closed or caller != self._owner:
            raise OwnershipError("only the active owner may continue this run")

    def _prepare(self, kind: str, caller: str, target: str) -> tuple[AgentSpec, dict[str, Any]]:
        self._check_owner(caller)
        if self._clock() >= self._deadline:
            raise BudgetExceeded("run deadline reached")
        if target == caller:
            raise OwnershipError("self delegation or handoff is not allowed")
        if kind == "handoff" and target in self._handoff_path:
            raise OwnershipError("handoff would revisit an earlier owner")
        if target not in self._agents:
            raise PolicyDenied("unknown target")
        if not self._policy.allows(self._principal, kind, caller, target):
            raise PolicyDenied("team edge is not authorized")
        spec = self._agents[target]
        return spec, project_context(self._context, spec.context_keys)

    def _reserve(self, kind: str, count: int) -> list[str]:
        if kind == "delegate":
            if self._delegations + count > self._limits.max_delegations:
                raise BudgetExceeded("delegation budget exhausted")
            self._delegations += count
        else:
            if self._handoffs + count > self._limits.max_handoffs:
                raise BudgetExceeded("handoff budget exhausted")
            self._handoffs += count
        ids = []
        for _ in range(count):
            self._sequence += 1
            ids.append(f"{self.run_id}:{self._sequence}")
        return ids

    def _invoke(self, spec: AgentSpec, context: dict[str, Any]) -> tuple[Finding, str | None, float]:
        started = self._clock()
        error = None
        try:
            if started >= self._deadline:
                raise BudgetExceeded("run deadline reached before invocation")
            finding = validate_finding(spec.run(spec.assignment, context))
            if self._clock() >= self._deadline:
                raise BudgetExceeded("late result")
        except Exception as exc:
            error = ("deadline_exceeded" if isinstance(exc, BudgetExceeded) else
                     "invalid_result" if isinstance(exc, InvalidResult) else "execution_error")
            # Exception text can contain credentials or private response bodies.
            finding = Finding("failed", "The specialist did not return an accepted result.")
        return finding, error, max(0.0, self._clock() - started) * 1000

    def _record(self, kind: str, caller: str, spec: AgentSpec, request_id: str,
                context_keys: tuple[str, ...], outcome: tuple[Finding, str | None, float]) -> AgentMessage:
        finding, error, elapsed = outcome
        message = AgentMessage(self.run_id, request_id, spec.name, finding, error)
        self._messages.append(message)
        self._events.append(TeamEvent(self.run_id, request_id, kind, caller, spec.name,
                                      finding.status, context_keys, elapsed, error))
        return AgentMessage(self.run_id, request_id, spec.name, validate_finding(finding), error)

    def _denied(self, kind: str, caller: str, target: str, exc: TeamError) -> None:
        code = ("ownership_denied" if isinstance(exc, OwnershipError) else
                "budget_denied" if isinstance(exc, BudgetExceeded) else "policy_denied")
        self._events.append(TeamEvent(self.run_id, "", kind, caller, target,
                                      "denied", (), 0.0, code))

    def delegate(self, *, caller: str, target: str) -> AgentMessage:
        return self.fan_out(caller=caller, targets=(target,))[0]

    def fan_out(self, *, caller: str, targets: Sequence[str], parallel: bool = False) -> tuple[AgentMessage, ...]:
        if isinstance(targets, (str, bytes)) or not all(isinstance(t, str) and t for t in targets):
            raise ValueError("targets must be a sequence of nonempty names")
        targets = tuple(targets)
        if not targets or len(set(targets)) != len(targets):
            raise ValueError("targets must be nonempty and unique")
        try:
            prepared = [self._prepare("delegate", caller, target) for target in targets]
            request_ids = self._reserve("delegate", len(prepared))
        except TeamError as exc:
            self._denied("delegate", caller, ",".join(targets), exc)
            raise
        # Reserve the whole batch before launching anything. No worker touches counters.
        keys = [tuple(sorted(context)) for _, context in prepared]
        if parallel:
            with ThreadPoolExecutor(max_workers=self._limits.max_workers) as pool:
                futures = [pool.submit(self._invoke, spec, context) for spec, context in prepared]
                outcomes = [future.result() for future in futures]
        else:
            outcomes = [self._invoke(spec, context) for spec, context in prepared]
        # Merge in request order, not completion order. Agents do not update shared state.
        return tuple(self._record("delegate", caller, spec, rid, visible, outcome)
                     for (spec, _), rid, visible, outcome in zip(prepared, request_ids, keys, outcomes))

    def handoff(self, *, caller: str, target: str) -> AgentMessage:
        try:
            spec, context = self._prepare("handoff", caller, target)
            context["handoff"] = {
                "previous_owner": caller,
                "findings": [{"agent": m.agent, "status": m.finding.status,
                              "summary": m.finding.summary, "facts": m.finding.facts,
                              "evidence_ids": m.finding.evidence_ids}
                             for m in self._messages if m.agent in spec.handoff_sources],
            }
            context = json_copy(context)
            request_id = self._reserve("handoff", 1)[0]
        except TeamError as exc:
            self._denied("handoff", caller, target, exc)
            raise
        self._owner = target
        self._handoff_path.append(target)
        # Ownership stays with the target even when its execution fails.
        return self._record("handoff", caller, spec, request_id, tuple(sorted(context)),
                            self._invoke(spec, context))

    def finish(self, *, caller: str, answer: str) -> str:
        self._check_owner(caller)
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError("answer is required")
        self._closed = True
        return answer
