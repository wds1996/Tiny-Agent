from __future__ import annotations

import asyncio
import inspect
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Literal, Mapping, Sequence


InteractionMode = Literal["delegate", "handoff"]
InvocationStatus = Literal["ok", "failed"]
AgentHandler = Callable[["AgentInput"], Awaitable[str] | str]


class MultiAgentError(RuntimeError):
    """Base class for deterministic multi-Agent coordination failures."""


class UnknownAgentError(MultiAgentError):
    pass


class DelegationDeniedError(MultiAgentError):
    pass


class CoordinationBudgetExceeded(MultiAgentError):
    pass


class HandoffLoopError(MultiAgentError):
    pass


class AgentOutputError(MultiAgentError):
    pass


@dataclass(frozen=True, slots=True)
class AgentInput:
    """A small, explicitly projected payload passed to one specialist Agent."""

    task: str
    context: Mapping[str, Any]
    delegated_by: str
    mode: InteractionMode


@dataclass(frozen=True, slots=True)
class AgentSpec:
    name: str
    description: str
    handler: AgentHandler

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("agent name must be non-empty")
        if not self.description.strip():
            raise ValueError("agent description must be non-empty")
        if not callable(self.handler):
            raise TypeError("agent handler must be callable")


@dataclass(frozen=True, slots=True)
class ContextEnvelope:
    """Context split into explicitly shareable and Agent-private namespaces."""

    shared: Mapping[str, Any] = field(default_factory=dict)
    private_by_agent: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ContextPolicy:
    """Projects the minimum context each Agent is allowed to receive.

    Unknown Agents receive no shared keys. An Agent may receive its own private
    namespace, but never another Agent's private namespace. This is structural
    field projection, not a process/memory security sandbox; nested mutable
    objects remain ordinary application objects.
    """

    allowed_shared_keys: Mapping[str, frozenset[str]] = field(default_factory=dict)
    include_agent_private: bool = True

    def project(self, agent_name: str, envelope: ContextEnvelope) -> dict[str, Any]:
        allowed = self.allowed_shared_keys.get(agent_name, frozenset())
        shared = {
            key: envelope.shared[key]
            for key in allowed
            if key in envelope.shared
        }
        private = (
            dict(envelope.private_by_agent.get(agent_name, {}))
            if self.include_agent_private
            else {}
        )
        return {"shared": shared, "private": private}


@dataclass(frozen=True, slots=True)
class DelegationPolicy:
    """Default-deny allowlist for Agent-to-Agent control edges."""

    allowed_targets: Mapping[str, frozenset[str]] = field(default_factory=dict)

    def enforce(self, source: str, target: str) -> None:
        if source == target:
            raise DelegationDeniedError("An Agent cannot delegate to itself.")
        if target not in self.allowed_targets.get(source, frozenset()):
            raise DelegationDeniedError(
                f"Delegation edge {source!r} -> {target!r} is not allowed."
            )


@dataclass(frozen=True, slots=True)
class CoordinationBudget:
    max_agent_calls: int = 8
    max_handoffs: int = 4
    max_parallel: int = 4
    max_same_handoff_edge: int = 1

    def __post_init__(self) -> None:
        for name, value in (
            ("max_agent_calls", self.max_agent_calls),
            ("max_handoffs", self.max_handoffs),
            ("max_parallel", self.max_parallel),
            ("max_same_handoff_edge", self.max_same_handoff_edge),
        ):
            if value <= 0:
                raise ValueError(f"{name} must be positive")


@dataclass(frozen=True, slots=True)
class AgentInteraction:
    source: str
    target: str
    mode: InteractionMode
    status: InvocationStatus
    error_type: str | None = None


@dataclass(slots=True)
class CoordinationState:
    """Run-scoped mutable state for one multi-Agent execution.

    `agent_calls` and `handoffs` are budget-consumption counters. An attempted
    Agent invocation or handoff consumes capacity even if the target later
    fails, because failed attempts still consume compute/latency and can be
    abused. Successful transfers are derived from interaction status.
    """

    active_agent: str
    budget: CoordinationBudget = field(default_factory=CoordinationBudget)
    agent_calls: int = 0
    handoffs: int = 0
    interactions: list[AgentInteraction] = field(default_factory=list)
    _handoff_edges: dict[tuple[str, str], int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.active_agent.strip():
            raise ValueError("active_agent must be non-empty")

    def ensure_source(self, source: str) -> None:
        if source != self.active_agent:
            raise DelegationDeniedError(
                f"Only active Agent {self.active_agent!r} can initiate coordination; "
                f"received source {source!r}."
            )

    def ensure_call_capacity(self, count: int = 1) -> None:
        if count < 0:
            raise ValueError("count must be non-negative")
        if self.agent_calls + count > self.budget.max_agent_calls:
            raise CoordinationBudgetExceeded("Agent-call budget exhausted.")

    def reserve(self, source: str, target: str, mode: InteractionMode) -> None:
        self.ensure_source(source)
        self.ensure_call_capacity(1)

        if mode == "handoff":
            if self.handoffs >= self.budget.max_handoffs:
                raise CoordinationBudgetExceeded("Handoff budget exhausted.")
            edge = (source, target)
            seen = self._handoff_edges.get(edge, 0)
            if seen >= self.budget.max_same_handoff_edge:
                raise HandoffLoopError(
                    f"Repeated handoff edge {source!r} -> {target!r} exceeded its limit."
                )
            self._handoff_edges[edge] = seen + 1
            self.handoffs += 1

        self.agent_calls += 1

    def record(self, interaction: AgentInteraction) -> None:
        self.interactions.append(interaction)


@dataclass(frozen=True, slots=True)
class AgentInvocation:
    source: str
    target: str
    mode: InteractionMode
    status: InvocationStatus
    output: str | None
    error_type: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == "ok"


class TeamRuntime:
    """Small framework-neutral runtime for explicit multi-Agent coordination.

    Application code owns the Agent registry, allowed edges, context projection,
    and run-scoped budgets. Model output can propose a destination, but it does
    not create new authority or bypass these controls.

    Async Agent handlers are awaited directly. Sync handlers run in a worker
    thread so `fan_out()` does not block the event loop. As in Stage 07, thread
    isolation is not hard termination or a security sandbox.
    """

    def __init__(
        self,
        agents: Sequence[AgentSpec],
        *,
        delegation_policy: DelegationPolicy,
        context_policy: ContextPolicy | None = None,
    ) -> None:
        registry: dict[str, AgentSpec] = {}
        for agent in agents:
            if agent.name in registry:
                raise ValueError(f"duplicate Agent name: {agent.name!r}")
            registry[agent.name] = agent
        if not registry:
            raise ValueError("at least one Agent is required")
        self._agents = registry
        self._delegation_policy = delegation_policy
        self._context_policy = context_policy or ContextPolicy()

    def get(self, name: str) -> AgentSpec:
        try:
            return self._agents[name]
        except KeyError as exc:
            raise UnknownAgentError(f"Unknown Agent {name!r}.") from exc

    async def delegate(
        self,
        *,
        source: str,
        target: str,
        task: str,
        context: ContextEnvelope,
        state: CoordinationState,
    ) -> AgentInvocation:
        self._prepare(source, target, "delegate", state)
        return await self._invoke_reserved(
            source=source,
            target=target,
            task=task,
            context=context,
            mode="delegate",
            state=state,
        )

    async def handoff(
        self,
        *,
        source: str,
        target: str,
        task: str,
        context: ContextEnvelope,
        state: CoordinationState,
    ) -> AgentInvocation:
        self._prepare(source, target, "handoff", state)
        result = await self._invoke_reserved(
            source=source,
            target=target,
            task=task,
            context=context,
            mode="handoff",
            state=state,
        )
        if result.ok:
            state.active_agent = target
        return result

    async def fan_out(
        self,
        *,
        source: str,
        assignments: Sequence[tuple[str, str]],
        context: ContextEnvelope,
        state: CoordinationState,
    ) -> tuple[AgentInvocation, ...]:
        """Run independent specialist delegations concurrently.

        The entire batch is validated before state is mutated, so a denied or
        unknown destination cannot partially consume coordination budget.
        `asyncio.gather` preserves assignment order in the returned tuple; it
        does not define application-level fan-in or result acceptance policy.
        """

        if len(assignments) > state.budget.max_parallel:
            raise CoordinationBudgetExceeded(
                f"Parallel batch size {len(assignments)} exceeds "
                f"max_parallel={state.budget.max_parallel}."
            )

        state.ensure_source(source)
        state.ensure_call_capacity(len(assignments))
        self.get(source)
        for target, _task in assignments:
            self.get(target)
            self._delegation_policy.enforce(source, target)

        for target, _task in assignments:
            state.reserve(source, target, "delegate")

        results = await asyncio.gather(
            *(
                self._invoke_reserved(
                    source=source,
                    target=target,
                    task=task,
                    context=context,
                    mode="delegate",
                    state=state,
                )
                for target, task in assignments
            )
        )
        return tuple(results)

    def _prepare(
        self,
        source: str,
        target: str,
        mode: InteractionMode,
        state: CoordinationState,
    ) -> None:
        self.get(source)
        self.get(target)
        self._delegation_policy.enforce(source, target)
        state.reserve(source, target, mode)

    async def _invoke_reserved(
        self,
        *,
        source: str,
        target: str,
        task: str,
        context: ContextEnvelope,
        mode: InteractionMode,
        state: CoordinationState,
    ) -> AgentInvocation:
        agent = self.get(target)
        projected = self._context_policy.project(target, context)
        payload = AgentInput(
            task=task,
            context=projected,
            delegated_by=source,
            mode=mode,
        )

        try:
            if inspect.iscoroutinefunction(agent.handler):
                value = await agent.handler(payload)
            else:
                value = await asyncio.to_thread(agent.handler, payload)
                if inspect.isawaitable(value):
                    value = await value
            if not isinstance(value, str):
                raise AgentOutputError("Agent handlers must return text in Stage 09 core.")
            result = AgentInvocation(source, target, mode, "ok", value, None)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # preserve type, do not leak arbitrary exception text
            result = AgentInvocation(
                source=source,
                target=target,
                mode=mode,
                status="failed",
                output=None,
                error_type=type(exc).__name__,
            )

        state.record(
            AgentInteraction(
                source=result.source,
                target=result.target,
                mode=result.mode,
                status=result.status,
                error_type=result.error_type,
            )
        )
        return result


def coordination_metrics(state: CoordinationState) -> dict[str, float]:
    """Convert run-scoped coordination state into Stage 08-style metrics."""

    participants = {state.active_agent}
    failures = 0
    successful_handoffs = 0
    for interaction in state.interactions:
        participants.add(interaction.source)
        participants.add(interaction.target)
        if interaction.status == "failed":
            failures += 1
        if interaction.mode == "handoff" and interaction.status == "ok":
            successful_handoffs += 1

    return {
        "agent_call_attempts": float(state.agent_calls),
        "handoff_attempts": float(state.handoffs),
        "successful_handoffs": float(successful_handoffs),
        "unique_agents": float(len(participants)),
        "failed_agent_calls": float(failures),
    }
