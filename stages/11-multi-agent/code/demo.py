from team import Delegation, Specialist, TeamBudget, TeamRuntime


def main() -> None:
    runtime = TeamRuntime([
        Specialist("supervisor", "", "supervisor"),
        Specialist("policy", "policy", "policy specialist"),
        Specialist("orders", "order", "order specialist"),
    ])
    context = {
        "user_id": "user-7",
        "order_id": "ORDER-42",
        "policy_excerpt": "Refunds within 30 days may use the original payment method.",
        "internal_secret": "should-not-be-shared",
    }
    budget = TeamBudget(max_delegations=3, max_handoffs=1)

    results = runtime.fan_out(
        caller="supervisor",
        delegations=[
            Delegation("orders", "Check the order status.", ("order_id",)),
            Delegation("policy", "Interpret the refund rule.", ("policy_excerpt",)),
        ],
        shared_context=context,
        budget=budget,
    )
    print("delegated results:")
    for result in results:
        print("-", result)

    handed = runtime.handoff(
        caller="supervisor", target="orders",
        task="Take ownership of the order follow-up.",
        shared_context=context, context_keys=("order_id", "user_id"), budget=budget,
    )
    print("\nhandoff owner:", handed.owner)
    print("handoff answer:", handed.answer)


if __name__ == "__main__":
    main()
