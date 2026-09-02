import asyncio

from tiny_agent import (
    AgentInput,
    AgentSpec,
    ContextEnvelope,
    CoordinationBudget,
    CoordinationState,
    DelegationPolicy,
    TeamRuntime,
)


async def make_worker(label: str, payload: AgentInput) -> str:
    await asyncio.sleep(0.01)
    return f"{label}: {payload.task}"


async def main() -> None:
    team = TeamRuntime(
        [
            AgentSpec("manager", "Coordinates independent analyses.", lambda p: p.task),
            AgentSpec("quality", "Checks quality.", lambda p: make_worker("quality", p)),
            AgentSpec("cost", "Checks cost.", lambda p: make_worker("cost", p)),
            AgentSpec("risk", "Checks risk.", lambda p: make_worker("risk", p)),
        ],
        delegation_policy=DelegationPolicy(
            {"manager": frozenset({"quality", "cost", "risk"})}
        ),
    )
    state = CoordinationState(
        active_agent="manager",
        budget=CoordinationBudget(max_parallel=3),
    )

    results = await team.fan_out(
        source="manager",
        assignments=(
            ("quality", "Evaluate answer quality."),
            ("cost", "Estimate coordination overhead."),
            ("risk", "Find delegation risks."),
        ),
        context=ContextEnvelope(),
        state=state,
    )

    print("Fan-out results (assignment order is preserved):")
    for item in results:
        print(f"- {item.target}: {item.output}")
    print("\nFan-in belongs to the manager/application, not to asyncio.gather().")


if __name__ == "__main__":
    asyncio.run(main())
