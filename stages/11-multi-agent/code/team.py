from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol, Sequence


class Agent(Protocol):
    name: str
    def run(self, task: str, context: Mapping[str, str]) -> str: ...


@dataclass(frozen=True, slots=True)
class Specialist:
    name: str
    keyword: str
    response_prefix: str

    def run(self, task: str, context: Mapping[str, str]) -> str:
        visible = ", ".join(f"{k}={v}" for k, v in sorted(context.items()))
        suffix = f" | context: {visible}" if visible else ""
        return f"{self.response_prefix}: {task}{suffix}"


@dataclass(frozen=True, slots=True)
class Delegation:
    target: str
    task: str
    context_keys: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class TeamResult:
    owner: str
    answer: str
    delegations: tuple[str, ...]


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


def project_context(context: Mapping[str, str], allowed_keys: Sequence[str]) -> dict[str, str]:
    return {key: context[key] for key in allowed_keys if key in context}


class TeamRuntime:
    def __init__(self, agents: Sequence[Agent]) -> None:
        self._agents = {agent.name: agent for agent in agents}
        if len(self._agents) != len(agents):
            raise ValueError("agent names must be unique")

    def delegate(
        self, *, caller: str, delegation: Delegation,
        shared_context: Mapping[str, str], budget: TeamBudget
    ) -> str:
        if caller not in self._agents:
            raise KeyError(f"unknown caller: {caller}")
        target = self._agents.get(delegation.target)
        if target is None:
            raise KeyError(f"unknown target: {delegation.target}")
        if caller == delegation.target:
            raise ValueError("an agent cannot delegate to itself")
        budget.use_delegation()
        projected = project_context(shared_context, delegation.context_keys)
        return target.run(delegation.task, projected)

    def handoff(
        self, *, caller: str, target: str, task: str,
        shared_context: Mapping[str, str], context_keys: Sequence[str],
        budget: TeamBudget
    ) -> TeamResult:
        if caller == target:
            raise ValueError("an agent cannot hand off to itself")
        agent = self._agents.get(target)
        if agent is None:
            raise KeyError(f"unknown target: {target}")
        budget.use_handoff()
        projected = project_context(shared_context, context_keys)
        answer = agent.run(task, projected)
        return TeamResult(owner=target, answer=answer, delegations=(target,))

    def fan_out(
        self, *, caller: str, delegations: Sequence[Delegation],
        shared_context: Mapping[str, str], budget: TeamBudget
    ) -> tuple[str, ...]:
        # Sequential on purpose: fan-out semantics do not require concurrency.
        return tuple(
            self.delegate(
                caller=caller, delegation=item,
                shared_context=shared_context, budget=budget,
            )
            for item in delegations
        )
