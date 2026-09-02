import asyncio

from tiny_agent import (
    AgentInput,
    AgentSpec,
    ContextEnvelope,
    CoordinationState,
    DelegationPolicy,
    TeamRuntime,
)


def analyst(payload: AgentInput) -> str:
    return f"Analyst notes: break down {payload.task} into evidence and assumptions."


def reviewer(payload: AgentInput) -> str:
    return f"Reviewer notes: challenge unsupported claims in {payload.task}."


async def main() -> None:
    team = TeamRuntime(
        [
            AgentSpec("supervisor", "Owns synthesis and user communication.", lambda p: p.task),
            AgentSpec("analyst", "Analyzes evidence.", analyst),
            AgentSpec("reviewer", "Reviews risks and gaps.", reviewer),
        ],
        delegation_policy=DelegationPolicy(
            {"supervisor": frozenset({"analyst", "reviewer"})}
        ),
    )
    state = CoordinationState(active_agent="supervisor")
    context = ContextEnvelope()

    analysis = await team.delegate(
        source="supervisor",
        target="analyst",
        task="Should this application use multiple Agents?",
        context=context,
        state=state,
    )
    review = await team.delegate(
        source="supervisor",
        target="reviewer",
        task=analysis.output or "No analysis available",
        context=context,
        state=state,
    )

    # The supervisor remains the only user-facing owner and combines results.
    synthesis = (
        "Supervisor synthesis:\n"
        f"- {analysis.output}\n"
        f"- {review.output}\n"
        "- Decision: add specialists only if evaluation beats a simpler baseline."
    )
    print(synthesis)
    print("Active Agent:", state.active_agent)


if __name__ == "__main__":
    asyncio.run(main())
