import asyncio

from tiny_agent import (
    AgentInput,
    AgentSpec,
    ContextEnvelope,
    ContextPolicy,
    CoordinationState,
    DelegationPolicy,
    TeamRuntime,
)


def research(payload: AgentInput) -> str:
    policy = payload.context["private"].get("source_policy", "use reliable sources")
    return f"Evidence collected for: {payload.task} ({policy})"


def writer(payload: AgentInput) -> str:
    style = payload.context["private"].get("style", "concise")
    return f"Draft [{style}]: {payload.task}"


async def main() -> None:
    team = TeamRuntime(
        [
            AgentSpec("manager", "Owns the user-facing task.", lambda p: p.task),
            AgentSpec("research", "Finds evidence.", research),
            AgentSpec("writer", "Turns evidence into prose.", writer),
        ],
        delegation_policy=DelegationPolicy(
            {"manager": frozenset({"research", "writer"})}
        ),
        context_policy=ContextPolicy(
            {
                "research": frozenset({"question"}),
                "writer": frozenset({"question"}),
            }
        ),
    )
    state = CoordinationState(active_agent="manager")
    context = ContextEnvelope(
        shared={"question": "Why use multiple Agents?", "api_key": "never-share"},
        private_by_agent={
            "research": {"source_policy": "cite primary sources"},
            "writer": {"style": "teaching-friendly"},
        },
    )

    evidence = await team.delegate(
        source="manager",
        target="research",
        task="Collect evidence about multi-Agent tradeoffs.",
        context=context,
        state=state,
    )
    draft = await team.delegate(
        source="manager",
        target="writer",
        task=f"Use this specialist output to write the answer: {evidence.output}",
        context=context,
        state=state,
    )

    print("Active Agent:", state.active_agent)
    print("Research:", evidence.output)
    print("Writer:", draft.output)
    print("Calls:", state.agent_calls)


if __name__ == "__main__":
    asyncio.run(main())
