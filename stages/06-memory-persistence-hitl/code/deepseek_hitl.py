from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping

from approval import ApprovalDecision, ApprovalRequest, resolve_refund_arguments
from durable_workflow import RefundWorkflow, SQLiteCheckpointStore
from memory import (
    ConservativeMemoryWritePolicy,
    MemoryCandidate,
    MemoryDecision,
    MemoryKind,
    SQLiteMemoryStore,
)


MODEL_INSTRUCTIONS = """You assist a refund workflow. Return JSON only with exactly:
{
  "reply": string,
  "refund": {"order_id": string, "amount": string} | null,
  "memory": {"key": string, "value": object, "kind": "semantic" | "episodic" | "procedural"} | null
}
Propose refund only when the user explicitly asks to perform one. Copy an ORDER-<digits>
identifier only from the user message; never invent one. Propose memory only when the user
explicitly asks to remember information. A proposal is not an execution instruction."""

_ORDER_ID = re.compile(r"ORDER-\d+", flags=re.IGNORECASE)
_MEMORY_WORDS = ("remember", "记住", "记下", "保存偏好")
_SENSITIVE_WORDS = ("password", "secret", "token", "api_key", "银行卡", "密码", "密钥")


@dataclass(frozen=True, slots=True)
class ModelProposal:
    reply: str
    refund: dict[str, str] | None
    memory: dict[str, Any] | None


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Set {name} before running this example.")
    return value


def create_client() -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "Install Stage 06 dependencies first:\n"
            "python -m pip install -r stages/06-memory-persistence-hitl/code/requirements.txt"
        ) from exc
    return OpenAI(api_key=required_env("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")


def parse_proposal(content: str) -> ModelProposal:
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise RuntimeError("DeepSeek did not return valid proposal JSON.") from exc
    if not isinstance(data, dict) or set(data) != {"reply", "refund", "memory"}:
        raise RuntimeError("Proposal must contain exactly reply, refund, and memory.")
    if not isinstance(data["reply"], str) or not data["reply"].strip():
        raise RuntimeError("Proposal.reply must be non-empty text.")
    for name in ("refund", "memory"):
        if data[name] is not None and not isinstance(data[name], dict):
            raise RuntimeError(f"Proposal.{name} must be an object or null.")
    refund = data["refund"]
    if refund is not None and set(refund) != {"order_id", "amount"}:
        raise RuntimeError("Proposal.refund must contain exactly order_id and amount.")
    if refund is not None and (
        not isinstance(refund["order_id"], str) or not isinstance(refund["amount"], str)
    ):
        raise RuntimeError("Proposal.refund values must be text.")
    memory = data["memory"]
    if memory is not None and set(memory) != {"key", "value", "kind"}:
        raise RuntimeError("Proposal.memory must contain exactly key, value, and kind.")
    return ModelProposal(reply=data["reply"].strip(), refund=refund, memory=memory)


class DeepSeekProposalModel:
    def __init__(self, *, client: Any, model: str) -> None:
        self._client = client
        self._model = model
        self.last_interaction: tuple[str, str, str] | None = None

    def propose(self, user_message: str) -> ModelProposal:
        response = self._client.chat.completions.create(
            model=self._model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": MODEL_INSTRUCTIONS},
                {"role": "user", "content": user_message},
            ],
        )
        if not response.choices or response.choices[0].message.content is None:
            raise RuntimeError("DeepSeek did not return a proposal.")
        raw = response.choices[0].message.content.strip()
        proposal = parse_proposal(raw)
        self.last_interaction = (MODEL_INSTRUCTIONS, user_message, raw)
        return proposal


def validate_refund(*, proposal: ModelProposal, user_message: str) -> dict[str, str] | None:
    if proposal.refund is None:
        return None
    order_id = proposal.refund["order_id"]
    if not isinstance(order_id, str) or _ORDER_ID.fullmatch(order_id) is None:
        raise RuntimeError("The proposed order ID is invalid.")
    mentioned = {match.group(0).upper() for match in _ORDER_ID.finditer(user_message)}
    if order_id.upper() not in mentioned:
        raise RuntimeError("The model proposed an order ID absent from the user message.")
    return resolve_refund_arguments(
        {"order_id": order_id.upper(), "amount": proposal.refund["amount"]},
        ApprovalDecision(outcome="approve"),
    )


def memory_candidate(
    *, proposal: ModelProposal, owner_id: str, user_message: str
) -> MemoryCandidate | None:
    if proposal.memory is None:
        return None
    key, value, kind = proposal.memory["key"], proposal.memory["value"], proposal.memory["kind"]
    if not isinstance(key, str) or not key.strip() or not isinstance(value, dict):
        raise RuntimeError("The memory proposal has an invalid key or value.")
    if kind not in ("semantic", "episodic", "procedural"):
        raise RuntimeError("The memory proposal has an invalid kind.")
    serialized = json.dumps(value, ensure_ascii=False).lower()
    return MemoryCandidate(
        owner_id=owner_id,
        key=key.strip(),
        value=value,
        kind=kind,
        explicit_user_request=any(word in user_message.lower() for word in _MEMORY_WORDS),
        sensitive=any(word in key.lower() or word in serialized for word in _SENSITIVE_WORDS),
    )


def read_approval_decision() -> ApprovalDecision:
    while True:
        outcome = input("Review outcome [approve/edit/reject]: ").strip().lower()
        if outcome in ("approve", "reject"):
            return ApprovalDecision(outcome=outcome)
        if outcome == "edit":
            return ApprovalDecision(
                outcome="edit",
                edited_arguments={
                    "order_id": input("Edited order ID: ").strip(),
                    "amount": input("Edited refund amount: ").strip(),
                },
            )
        print("Enter approve, edit, or reject.")


def format_conversation(interaction: tuple[str, str, str]) -> str:
    instructions, user_message, raw = interaction
    return "\n".join((
        "=== reconstructed model conversation ===",
        "system (instructions):", f"  {instructions}",
        "user:", f"  {user_message}",
        "assistant (JSON proposal):", f"  {raw}",
    ))


def main() -> None:
    user_message = "Please refund ORDER-42 for 18.50, and remember that I prefer concise Chinese answers."
    model = DeepSeekProposalModel(client=create_client(), model=required_env("DEEPSEEK_MODEL"))
    proposal = model.propose(user_message)
    print("assistant reply:", proposal.reply)
    if model.last_interaction is not None:
        print("\n" + format_conversation(model.last_interaction))

    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "agent.db"
        candidate = memory_candidate(proposal=proposal, owner_id="user-7", user_message=user_message)
        if candidate is not None:
            decision: MemoryDecision = ConservativeMemoryWritePolicy().evaluate(candidate)
            print("\nmemory decision:", decision)
            if decision.store:
                SQLiteMemoryStore(db_path).put(candidate)

        arguments = validate_refund(proposal=proposal, user_message=user_message)
        if arguments is None:
            print("\nNo refund was proposed; no approval is requested.")
            return
        workflow = RefundWorkflow(SQLiteCheckpointStore(db_path))
        request: ApprovalRequest = workflow.start(run_id="run-001", **arguments)
        print("\npaused:", request)
        resumed = RefundWorkflow(SQLiteCheckpointStore(db_path))
        while True:
            try:
                final = resumed.resume("run-001", read_approval_decision())
            except ValueError as exc:
                print(f"Review input was rejected: {exc}")
                continue
            break
        print("resumed:", final.phase, final.result)


if __name__ == "__main__":
    main()
