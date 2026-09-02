import asyncio

from tiny_agent import (
    AgentInput,
    AgentSpec,
    ContextEnvelope,
    CoordinationState,
    DelegationPolicy,
    TeamRuntime,
)


def refund_agent(payload: AgentInput) -> str:
    return f"Refund specialist now owns: {payload.task}"


async def main() -> None:
    team = TeamRuntime(
        [
            AgentSpec("triage", "Routes support conversations.", lambda p: p.task),
            AgentSpec("refund", "Handles refund conversations.", refund_agent),
        ],
        delegation_policy=DelegationPolicy(
            {"triage": frozenset({"refund"})}
        ),
    )
    state = CoordinationState(active_agent="triage")

    result = await team.handoff(
        source="triage",
        target="refund",
        task="Customer wants a refund for order #42.",
        context=ContextEnvelope(),
        state=state,
    )

    print("Result:", result.output)
    print("Active Agent after handoff:", state.active_agent)
    print("Handoffs used:", state.handoffs)


if __name__ == "__main__":
    asyncio.run(main())
