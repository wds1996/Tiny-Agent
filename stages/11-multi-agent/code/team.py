from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol, Sequence


@dataclass(frozen=True, slots=True)
class Principal:
    """The user or service identity on whose behalf the team is working."""

    id: str
    roles: frozenset[str]


@dataclass(frozen=True, slots=True)
class AgentMessage:
    """A structured result returned across an Agent boundary."""

    agent: str
    task: str
    status: str
    summary: str
    data: Mapping[str, str]
    provenance: tuple[str, ...]


class Agent(Protocol):
    name: str

    def run(self, task: str, context: Mapping[str, str]) -> AgentMessage: ...


@dataclass(frozen=True, slots=True)
class Specialist:
    name: str
    response_prefix: str

    def run(self, task: str, context: Mapping[str, str]) -> AgentMessage:
        visible = ", ".join(f"{key}={value}" for key, value in sorted(context.items()))
        suffix = f" | context: {visible}" if visible else ""
        return AgentMessage(
            agent=self.name,
            task=task,
            status="completed",
            summary=f"{self.response_prefix}: {task}{suffix}",
            data=dict(context),
            provenance=(f"specialist:{self.name}",),
        )


@dataclass(frozen=True, slots=True)
class Delegation:
    target: str
    task: str
    context_keys: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TeamResult:
    owner: str
    message: AgentMessage
    delegations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TeamEvent:
    kind: str
    caller: str
    target: str
    context_keys: tuple[str, ...]
    status: str


@dataclass(slots=True)
class TeamBudget:
    max_delegations: int = 4
    max_handoffs: int = 1
    delegations: int = 0
    handoffs: int = 0

    def use_delegation(self) -> None:
        if self.delegations >= self.max_delegations:
            raise RuntimeError("delegation budget exhausted")
        self.delegations += 1

    def use_handoff(self) -> None:
        if self.handoffs >= self.max_handoffs:
            raise RuntimeError("handoff budget exhausted")
        self.handoffs += 1


@dataclass(frozen=True, slots=True)
class TeamPolicy:
    """Default-deny permission policy for entering a specialist boundary."""

    grants: Mapping[str, frozenset[str]]

    def allows(self, principal: Principal, target: str) -> bool:
        return any(target in self.grants.get(role, frozenset()) for role in principal.roles)


def project_context(context: Mapping[str, str], allowed_keys: Sequence[str]) -> dict[str, str]:
    return {key: context[key] for key in allowed_keys if key in context}


class TeamRuntime:
    def __init__(self, agents: Sequence[Agent], *, policy: TeamPolicy) -> None:
        self._agents = {agent.name: agent for agent in agents}
        if len(self._agents) != len(agents):
            raise ValueError("agent names must be unique")
        self._policy = policy
        self.events: list[TeamEvent] = []

    def _get_agent(self, name: str) -> Agent:
        agent = self._agents.get(name)
        if agent is None:
            raise KeyError(f"unknown agent: {name}")
        return agent

    def _authorize(self, principal: Principal, target: str) -> None:
        if not self._policy.allows(principal, target):
            raise PermissionError(
                f"principal {principal.id!r} is not allowed to delegate to {target!r}"
            )

    def delegate(
        self,
        *,
        caller: str,
        principal: Principal,
        delegation: Delegation,
        shared_context: Mapping[str, str],
        budget: TeamBudget,
    ) -> AgentMessage:
        self._get_agent(caller)
        target = self._get_agent(delegation.target)
        if caller == delegation.target:
            raise ValueError("an agent cannot delegate to itself")
        self._authorize(principal, delegation.target)
        budget.use_delegation()
        projected = project_context(shared_context, delegation.context_keys)
        message = target.run(delegation.task, projected)
        self.events.append(
            TeamEvent(
                kind="delegation",
                caller=caller,
                target=delegation.target,
                context_keys=delegation.context_keys,
                status=message.status,
            )
        )
        return message

    def handoff(
        self,
        *,
        caller: str,
        principal: Principal,
        target: str,
        task: str,
        shared_context: Mapping[str, str],
        context_keys: Sequence[str],
        budget: TeamBudget,
    ) -> TeamResult:
        self._get_agent(caller)
        if caller == target:
            raise ValueError("an agent cannot hand off to itself")
        agent = self._get_agent(target)
        self._authorize(principal, target)
        budget.use_handoff()
        projected = project_context(shared_context, context_keys)
        message = agent.run(task, projected)
        self.events.append(
            TeamEvent(
                kind="handoff",
                caller=caller,
                target=target,
                context_keys=tuple(context_keys),
                status=message.status,
            )
        )
        return TeamResult(owner=target, message=message, delegations=(target,))

    def fan_out(
        self,
        *,
        caller: str,
        principal: Principal,
        delegations: Sequence[Delegation],
        shared_context: Mapping[str, str],
        budget: TeamBudget,
    ) -> tuple[AgentMessage, ...]:
        # Sequential on purpose: fan-out semantics do not require concurrency.
        return tuple(
            self.delegate(
                caller=caller,
                principal=principal,
                delegation=item,
                shared_context=shared_context,
                budget=budget,
            )
            for item in delegations
        )
