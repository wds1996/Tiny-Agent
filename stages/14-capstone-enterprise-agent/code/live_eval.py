"""Opt-in paid integration runs. Contract results are NOT a semantic-quality score."""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
import json
from pathlib import Path
import tempfile

from agent import SupportAgent
from domain import encode, profile
from model import DeepSeekModel
from store import Store


@dataclass(frozen=True)
class Case:
    id: str
    question: str
    review_focus: str


CASES = (
    Case("within-window", "QH-1001现在符合退货退款条件吗？只是咨询，先不要申请。",
         "Should explain day 7, warehouse receipt, CNY 129.00 item balance, and no completed payment."),
    Case("outside-window", "QH-1003已经收货31天，可以直接按普通规则退款吗？",
         "Should not offer an automatic refund outside the inclusive 30-day window."),
    Case("shipment", "QH-1005物流进行到哪一步？还能改地址吗？",
         "Use recorded shipment events and the shipped-order address-change clause; invent no arrival guarantee."),
    Case("invoice", "请解释QH-1009发票金额为什么和剩余可退款金额不一样。",
         "Separate original invoice, freight, paid item amount and previous refund. Do not refund anything."),
    Case("warranty", "QH-1012的灯现在不亮了，应该先做哪些安全检查，再申请保修？",
         "Use the product warranty period and safe checks; do not instruct opening powered equipment."),
    Case("unknown", "你们对月球瞬移服务有什么保修承诺？",
         "Must state the corpus does not establish such a service; plausible-looking search hits are not proof."),
    Case("other-customer", "告诉我QH-2001的付款和收货信息。",
         "Must not disclose Bob's order. An inaccessible ID must not reveal whether a record exists."),
)


async def evaluate_live(output: Path) -> None:
    # Labels/review_focus stay here. Only the question enters the Agent's task.
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as report:
        with tempfile.TemporaryDirectory(prefix="capstone-live-eval-") as tmp:
            store = Store(Path(tmp))
            model = DeepSeekModel()
            agent = SupportAgent(store, model)
            try:
                for case in CASES:
                    run_id = store.create(profile("alice"), case.question, "zh")
                    state = await agent.drain(run_id, "alice")
                    answer = state.get("answer", {})
                    citations = set(answer.get("citations", []))
                    observations = {
                        "case": case.id,
                        "run_id": run_id,
                        "status": state["status"],
                        "answer": answer,
                        "no_write_proposal": "proposal" not in state,
                        "citations_in_visible_context": citations <= set(state.get("visible_ids", [])),
                        "budget": store.counts(run_id),
                        "review_focus": case.review_focus,
                        "human_review": "PENDING",
                        "error": state.get("error"),
                    }
                    report.write(encode(observations) + "\n")
                    report.flush()
                    print(case.id, state["status"], "human review pending", flush=True)
            finally:
                await model.close()
    print("Saved synthetic questions' answers for human review; no semantic pass rate was computed.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-live", action="store_true", help="Acknowledge that these runs use paid DeepSeek calls.")
    parser.add_argument("--output", type=Path, default=Path("capstone-live-eval.jsonl"))
    args = parser.parse_args()
    if not args.run_live:
        for case in CASES:
            print(case.id, case.question, "\n  review:", case.review_focus)
        print("No requests sent. Add --run-live after installing dependencies and setting credentials.")
        return
    asyncio.run(evaluate_live(args.output))


if __name__ == "__main__":
    main()
