from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
from typing import Any

from durable_workflow import SQLiteWorkflowStore, SupportCaseWorkflow
from memory import (
    ConservativeMemoryWritePolicy,
    MemoryCandidate,
    MemoryDecision,
    SQLiteMemoryStore,
    store_if_allowed,
)


INSTRUCTIONS = """You help prepare one fictional Acme support action.
Return JSON only with exactly these fields:
{
  "reply": string,
  "action": {"name": "create_support_case", "arguments": {"order_id": string, "reason": string}} | null,
  "memory": {"key": string, "value": object, "kind": "semantic" | "episodic" | "procedural"} | null
}
Propose create_support_case only when the user explicitly asks to create/open a case.
Copy an ACME-<digits> order ID only from the user's message. Never invent an order ID.
Propose memory only when the user explicitly asks to remember something.
A proposal is data for the application to validate; it is not approval or execution authority."""

_ORDER_ID = re.compile(r"ACME-\d+", flags=re.IGNORECASE)
_MEMORY_WORDS = ("remember", "记住", "记下", "保存偏好", "以后")
_SENSITIVE_WORDS = ("password", "secret", "token", "api_key", "银行卡", "密码", "密钥")


@dataclass(frozen=True, slots=True)
class ModelProposal:
    reply: str
    action: dict[str, Any] | None
    memory: dict[str, Any] | None


@dataclass(frozen=True, slots=True)
class PreparedRun:
    reply: str
    memory_decision: MemoryDecision | None
    approval_requested: bool


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
    return OpenAI(
        api_key=required_env("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com",
        timeout=30.0,
        max_retries=0,
    )


def parse_proposal(text: str) -> ModelProposal:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("DeepSeek did not return valid proposal JSON") from exc
    if not isinstance(data, dict) or set(data) != {"reply", "action", "memory"}:
        raise RuntimeError("proposal must contain exactly reply, action, and memory")
    if not isinstance(data["reply"], str) or not data["reply"].strip():
        raise RuntimeError("proposal.reply must be non-empty text")
    for name in ("action", "memory"):
        if data[name] is not None and not isinstance(data[name], dict):
            raise RuntimeError(f"proposal.{name} must be an object or null")
    return ModelProposal(data["reply"].strip(), data["action"], data["memory"])


class DeepSeekProposalModel:
    def __init__(self, *, client: Any, model: str) -> None:
        if not model.strip():
            raise ValueError("model must not be blank")
        self.client = client
        self.model = model

    def propose(self, user_message: str) -> ModelProposal:
        response = self.client.responses.create(
            model=self.model,
            instructions=INSTRUCTIONS,
            input=user_message,
            max_output_tokens=4096,
        )
        if response.status != "completed":
            raise RuntimeError(f"DeepSeek response did not complete: {response.status}")
        raw = response.output_text.strip()
        if not raw:
            raise RuntimeError("DeepSeek completed without usable proposal text")
        return parse_proposal(raw)


def validate_action(proposal: ModelProposal, *, user_message: str) -> dict[str, str] | None:
    if proposal.action is None:
        return None
    if set(proposal.action) != {"name", "arguments"}:
        raise RuntimeError("action must contain exactly name and arguments")
    if proposal.action["name"] != "create_support_case":
        raise RuntimeError("the proposed action is not allowed in this stage")
    arguments = proposal.action["arguments"]
    if not isinstance(arguments, dict) or set(arguments) != {"order_id", "reason"}:
        raise RuntimeError("action arguments must contain exactly order_id and reason")
    order_id = arguments["order_id"]
    reason = arguments["reason"]
    if not isinstance(order_id, str) or _ORDER_ID.fullmatch(order_id) is None:
        raise RuntimeError("the proposed order ID is invalid")
    mentioned = {match.group(0).upper() for match in _ORDER_ID.finditer(user_message)}
    if order_id.upper() not in mentioned:
        raise RuntimeError("the model proposed an order ID absent from the user message")
    if not isinstance(reason, str) or not reason.strip():
        raise RuntimeError("the support-case reason must be non-empty text")
    return {"order_id": order_id.upper(), "reason": " ".join(reason.split())}


def memory_candidate(
    proposal: ModelProposal,
    *,
    owner_id: str,
    thread_id: str,
    user_message: str,
) -> MemoryCandidate | None:
    if proposal.memory is None:
        return None
    if set(proposal.memory) != {"key", "value", "kind"}:
        raise RuntimeError("memory must contain exactly key, value, and kind")
    key = proposal.memory["key"]
    value = proposal.memory["value"]
    kind = proposal.memory["kind"]
    if not isinstance(key, str) or not key.strip() or not isinstance(value, dict):
        raise RuntimeError("memory key must be text and value must be an object")
    if kind not in ("semantic", "episodic", "procedural"):
        raise RuntimeError("memory kind is invalid")

    serialized = json.dumps(value, ensure_ascii=False).lower()
    lowered = user_message.lower()
    return MemoryCandidate(
        owner_id=owner_id,
        key=key.strip(),
        value=value,
        kind=kind,
        explicit_user_request=any(word in lowered for word in _MEMORY_WORDS),
        source_thread_id=thread_id,
        sensitive=any(word in key.lower() or word in serialized for word in _SENSITIVE_WORDS),
    )


def prepare_run(
    *,
    proposal: ModelProposal,
    user_message: str,
    db_path: Path,
    run_id: str,
    thread_id: str,
    owner_id: str,
) -> PreparedRun:
    memory = memory_candidate(
        proposal,
        owner_id=owner_id,
        thread_id=thread_id,
        user_message=user_message,
    )
    memory_decision = None
    if memory is not None:
        memory_decision = store_if_allowed(
            store=SQLiteMemoryStore(db_path),
            policy=ConservativeMemoryWritePolicy(),
            candidate=memory,
        )

    action = validate_action(proposal, user_message=user_message)
    if action is None:
        return PreparedRun(proposal.reply, memory_decision, False)

    SupportCaseWorkflow(SQLiteWorkflowStore(db_path)).start(
        run_id=run_id,
        thread_id=thread_id,
        owner_id=owner_id,
        order_id=action["order_id"],
        reason=action["reason"],
    )
    return PreparedRun(proposal.reply, memory_decision, True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stage 06 live DeepSeek proposal demo")
    parser.add_argument("--db", default="stage06-live.db")
    parser.add_argument("--run-id", default="acme-live-run-001")
    parser.add_argument("--thread-id", default="acme-live-thread-001")
    parser.add_argument("--owner-id", default="user-7")
    parser.add_argument(
        "--message",
        default=(
            "请为 ACME-1007 创建一个售后工单，原因是我在第 38 天申请原路退款；"
            "另外记住，以后请用简短中文回复我。"
        ),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    model = DeepSeekProposalModel(client=create_client(), model=required_env("DEEPSEEK_MODEL"))
    print("live DeepSeek: API usage applies")
    proposal = model.propose(args.message)
    prepared = prepare_run(
        proposal=proposal,
        user_message=args.message,
        db_path=Path(args.db),
        run_id=args.run_id,
        thread_id=args.thread_id,
        owner_id=args.owner_id,
    )
    print("assistant reply:", prepared.reply)
    print("memory decision:", prepared.memory_decision)
    print("approval requested:", prepared.approval_requested)
    if prepared.approval_requested:
        print("checkpoint saved; review with demo.py resume using the same --db and --run-id")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
