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


def inspect_context(payload: AgentInput) -> str:
    return repr(dict(payload.context))


async def main() -> None:
    team = TeamRuntime(
        [
            AgentSpec("manager", "Owns the full application context.", lambda p: p.task),
            AgentSpec("research", "Sees research-safe context only.", inspect_context),
            AgentSpec("billing", "Sees billing-safe context only.", inspect_context),
        ],
        delegation_policy=DelegationPolicy(
            {"manager": frozenset({"research", "billing"})}
        ),
        context_policy=ContextPolicy(
            {
                "research": frozenset({"question", "language"}),
                "billing": frozenset({"customer_id"}),
            }
        ),
    )
    envelope = ContextEnvelope(
        shared={
            "question": "Compare Agent patterns",
            "language": "zh",
            "customer_id": "cust-42",
            "api_key": "do-not-share",
        },
        private_by_agent={
            "research": {"source_policy": "primary sources"},
            "billing": {"invoice_scope": "read-only"},
        },
    )
    state = CoordinationState(active_agent="manager")

    research = await team.delegate(source="manager", target="research", task="inspect", context=envelope, state=state)
    billing = await team.delegate(source="manager", target="billing", task="inspect", context=envelope, state=state)

    print("Research view:", research.output)
    print("Billing view:", billing.output)
    print("The api_key and the other Agent's private namespace never enter either view.")


if __name__ == "__main__":
    asyncio.run(main())
