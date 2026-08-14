"""Stage 02: schema-constrained semantic routing with a real model.

Run from the repository root:

    pip install -e ".[openai]"
    export OPENAI_API_KEY="..."
    python stages/02-planning-routing/code/openai_router.py

The LLM chooses exactly one allowed route. Python code still owns dispatch.
"""

from tiny_agent.models.openai_structured import OpenAIStructuredDecisionModel
from tiny_agent.workflows import LLMRouter, RoutingWorkflow


def billing_handler(request: str) -> str:
    return f"BILLING WORKFLOW received: {request}"


def technical_handler(request: str) -> str:
    return f"TECHNICAL WORKFLOW received: {request}"


def general_handler(request: str) -> str:
    return f"GENERAL WORKFLOW received: {request}"


model = OpenAIStructuredDecisionModel(
    model="gpt-5.6-luna",
    reasoning_effort="none",
)

router = LLMRouter(
    model=model,
    routes={
        "billing": (
            "Refunds, invoices, subscriptions, duplicate charges, and payment issues."
        ),
        "technical": (
            "Software bugs, crashes, error messages, login failures caused by product "
            "malfunction, and other technical problems."
        ),
        "general": (
            "Ordinary product information and questions that are neither billing nor "
            "technical support incidents."
        ),
    },
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
        "I see two identical card charges for the same subscription renewal.",
        "After I sign in, the desktop client immediately closes without a message.",
        "Does the product support Japanese?",
    ]

    for request in examples:
        result = workflow.run(request)
        print(f"\nRequest: {request}")
        print(f"Route:   {result.decision.route}")
        print(f"Reason:  {result.decision.reason}")
        print(f"Output:  {result.output}")
