from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from approval import ApprovalDecision, ApprovalRequest
from deepseek_hitl import (
    DeepSeekProposalModel,
    ModelProposal,
    create_client,
    format_conversation,
    memory_candidate,
    read_approval_decision,
    required_env,
    validate_refund,
)
from durable_workflow import RefundWorkflow, SQLiteCheckpointStore
from memory import ConservativeMemoryWritePolicy, MemoryDecision, SQLiteMemoryStore


class HITLGraphState(TypedDict, total=False):
    user_message: str
    owner_id: str
    proposal: ModelProposal
    reply: str
    memory_decision: MemoryDecision | None
    approval_request: ApprovalRequest | None
    refund_arguments: dict[str, str] | None


def build_graph(*, model: DeepSeekProposalModel, db_path: Path):
    """Build propose -> memory-policy -> checkpointed-approval preparation."""

    def propose(state: HITLGraphState) -> dict[str, Any]:
        proposal = model.propose(state["user_message"])
        return {"proposal": proposal, "reply": proposal.reply}

    def evaluate_memory(state: HITLGraphState) -> dict[str, Any]:
        candidate = memory_candidate(
            proposal=state["proposal"],
            owner_id=state["owner_id"],
            user_message=state["user_message"],
        )
        if candidate is None:
            return {"memory_decision": None}
        decision = ConservativeMemoryWritePolicy().evaluate(candidate)
        if decision.store:
            SQLiteMemoryStore(db_path).put(candidate)
        return {"memory_decision": decision}

    def prepare_approval(state: HITLGraphState) -> dict[str, Any]:
        arguments = validate_refund(
            proposal=state["proposal"], user_message=state["user_message"]
        )
        if arguments is None:
            return {"refund_arguments": None, "approval_request": None}
        workflow = RefundWorkflow(SQLiteCheckpointStore(db_path))
        request = workflow.start(run_id="run-001", **arguments)
        return {"refund_arguments": arguments, "approval_request": request}

    builder = StateGraph(HITLGraphState)
    builder.add_node("propose", propose)
    builder.add_node("evaluate_memory", evaluate_memory)
    builder.add_node("prepare_approval", prepare_approval)
    builder.add_edge(START, "propose")
    builder.add_edge("propose", "evaluate_memory")
    builder.add_edge("evaluate_memory", "prepare_approval")
    builder.add_edge("prepare_approval", END)
    return builder.compile()


def initial_state(user_message: str) -> HITLGraphState:
    return {"user_message": user_message, "owner_id": "user-7"}


def main() -> None:
    user_message = "Please refund ORDER-42 for 18.50, and remember that I prefer concise Chinese answers."
    model = DeepSeekProposalModel(client=create_client(), model=required_env("DEEPSEEK_MODEL"))

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "agent.db"
        graph = build_graph(model=model, db_path=db_path)
        state = initial_state(user_message)
        print("=== graph updates (debug trace) ===")
        for update in graph.stream(state, stream_mode="updates", config={"recursion_limit": 10}):
            print(update)
            for values in update.values():
                state.update(values)

        print("\nassistant reply:", state["reply"])
        if model.last_interaction is not None:
            print("\n" + format_conversation(model.last_interaction))
        print("\nmemory decision:", state.get("memory_decision"))

        request = state.get("approval_request")
        if request is None:
            print("\nNo refund was proposed; no approval is requested.")
            return
        print("\npaused:", request)
        workflow = RefundWorkflow(SQLiteCheckpointStore(db_path))
        while True:
            try:
                final = workflow.resume("run-001", read_approval_decision())
            except ValueError as exc:
                print(f"Review input was rejected: {exc}")
                continue
            break
        print("resumed:", final.phase, final.result)


if __name__ == "__main__":
    main()
