"""The primary entry uses real DeepSeek requests and an MCP stdio subprocess."""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from agent import SupportAgent
from business import Commerce
from domain import BoundaryError, encode, profile, text
from mcp_bridge import connect
from model import DeepSeekModel
from store import Store

DEFAULT_STATE = Path(__file__).with_name(".state")


def parser():
    p = argparse.ArgumentParser(
        description="Fictional Qinghe support capstone. Live LLM by default; no automatic approval.",
    )
    p.add_argument("--state-dir", type=Path, default=DEFAULT_STATE)
    p.add_argument("--profile", default="alice", help="Trusted LOCAL demo profile, not a production login.")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    ask = sub.add_parser("ask")
    ask.add_argument("question")
    ask.add_argument("--language", choices=["zh", "en"])
    ask.add_argument("--one-step", action="store_true")
    resume = sub.add_parser("resume")
    resume.add_argument("run_id")
    resume.add_argument("--one-step", action="store_true")
    resume.add_argument("--retry", action="store_true")
    inspect = sub.add_parser("inspect")
    inspect.add_argument("run_id")
    review_info = sub.add_parser("review-info")
    review_info.add_argument("run_id")
    review = sub.add_parser("review")
    review.add_argument("run_id")
    review.add_argument("--digest", required=True)
    group = review.add_mutually_exclusive_group(required=True)
    group.add_argument("--approve", action="store_true")
    group.add_argument("--reject", action="store_true")
    remember = sub.add_parser("remember")
    remember.add_argument("--language", choices=["zh", "en"], required=True)
    remember.add_argument("--consent", action="store_true")
    ticket = sub.add_parser("create-ticket")
    ticket.add_argument("order_id")
    ticket.add_argument("summary")
    ticket.add_argument("--key", required=True)
    sub.add_parser("mcp-tools")
    return p


def show(state, store, identity):
    visible = ("id", "phase", "status", "answer", "proposal", "approval_digest", "receipt", "artifact", "error")
    output = {key: state[key] for key in visible if key in state}
    output["budget"] = store.counts(state["id"])
    print(encode(output))
    print(encode(store.events(state["id"], identity)))


async def main_async(args):
    identity = profile(args.profile)
    store = Store(args.state_dir)
    if args.command == "init":
        Commerce(store.root, identity)
        print("Initialized fictional data; existing orders and runs were not reset.")
        return
    if args.command == "remember":
        store.remember(identity, args.language, consent=args.consent)
        print("Consented language preference saved.")
        return
    if args.command == "inspect":
        show(store.get(args.run_id, identity), store, identity)
        return
    if args.command == "review-info":
        print(encode(store.approval_for(args.run_id, identity)))
        return
    if args.command == "review":
        store.review(args.run_id, identity, args.digest, approve=args.approve)
        print("Decision saved. Approval queues settlement; it does not call the payment service yet.")
        return
    if args.command in {"mcp-tools", "create-ticket"}:
        async with connect(store.root, args.profile) as bridge:
            if args.command == "mcp-tools":
                print(sorted(await bridge.discover()))
            else:
                print(encode(await bridge.call("create_ticket", {
                    "order_id": args.order_id,
                    "summary": args.summary,
                    "idempotency_key": args.key,
                })))
        return
    model = DeepSeekModel()
    agent = SupportAgent(store, model)
    try:
        if args.command == "ask":
            language = args.language or store.preference(identity).get("language", "zh")
            run_id = store.create(identity, text(args.question, maximum=1800), language)
            print("run_id:", run_id, flush=True)
        else:
            run_id = args.run_id
            if args.retry:
                store.retry(run_id, identity)
        if args.one_step:
            state = await agent.work_once(run_id, args.profile)
        else:
            state = await agent.drain(run_id, args.profile)
        show(state, store, identity)
        if state["status"] == "failed":
            raise SystemExit(1)
    finally:
        await model.close()


def main():
    args = parser().parse_args()
    try:
        asyncio.run(main_async(args))
    except BoundaryError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
