import asyncio

from tiny_agent import (
    AgentInput,
    AgentSpec,
    ContextEnvelope,
    CoordinationBudget,
    CoordinationState,
    DelegationDeniedError,
    DelegationPolicy,
    HandoffLoopError,
    TeamRuntime,
)


async def main() -> None:
    team = TeamRuntime(
        [
            AgentSpec("triage", "Routes support.", lambda p: f"triage:{p.task}"),
            AgentSpec("billing", "Handles billing.", lambda p: f"billing:{p.task}"),
        ],
        delegation_policy=DelegationPolicy(
            {
                "triage": frozenset({"billing"}),
                "billing": frozenset({"triage"}),
            }
        ),
    )
    state = CoordinationState(
        active_agent="triage",
        budget=CoordinationBudget(
            max_agent_calls=4,
            max_handoffs=4,
            max_same_handoff_edge=1,
        ),
    )

    await team.handoff(source="triage", target="billing", task="Need invoice help", context=ContextEnvelope(), state=state)
    await team.handoff(source="billing", target="triage", task="Need general support", context=ContextEnvelope(), state=state)

    try:
        await team.handoff(source="triage", target="billing", task="Ping-pong again", context=ContextEnvelope(), state=state)
    except HandoffLoopError as exc:
        print("Loop blocked:", type(exc).__name__)

    try:
        await team.delegate(source="triage", target="triage", task="Self delegation", context=ContextEnvelope(), state=state)
    except DelegationDeniedError as exc:
        print("Self delegation blocked:", type(exc).__name__)

    print("Calls consumed:", state.agent_calls)
    print("Control plane rules are code, not polite suggestions in a prompt.")


if __name__ == "__main__":
    asyncio.run(main())
