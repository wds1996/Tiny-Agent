"""Stage 02: deterministic routing before LLM routing.

Run from the repository root:

    python stages/02-planning-routing/code/deterministic_router.py

The point of this example is intentionally simple: if the application already has
reliable routing signals, ordinary code is the correct control system.
"""

from tiny_agent.workflows import RoutingWorkflow, RuleRouter


def billing_handler(request: str) -> str:
    return f"BILLING WORKFLOW received: {request}"


def technical_handler(request: str) -> str:
    return f"TECHNICAL WORKFLOW received: {request}"


def general_handler(request: str) -> str:
    return f"GENERAL WORKFLOW received: {request}"


router = RuleRouter(
    rules=[
        (
            "billing",
            lambda request: any(
                word in request.lower()
                for word in ("refund", "invoice", "charged twice")
            ),
        ),
        (
            "technical",
            lambda request: any(
                word in request.lower()
                for word in ("crash", "error code", "won't start")
            ),
        ),
    ],
    fallback="general",
)

workflow = RoutingWorkflow(
    router=router,
    handlers={
        "billing": billing_handler,
        "technical": technical_handler,
        "general": general_handler,
    },
)


if __name__ == "__main__":
    examples = [
        "I was charged twice and need help.",
        "The desktop app crashes after login.",
        "Which languages does the product support?",
    ]

    for request in examples:
        result = workflow.run(request)
        print(f"\nRequest: {request}")
        print(f"Route:   {result.decision.route}")
        print(f"Reason:  {result.decision.reason}")
        print(f"Output:  {result.output}")
