"""A report assessment with visible delegation, conflict, failure and handoff."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json

from scenario import build_team, from_messages, make_context
from team import OwnershipError


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=("normal", "missing", "conflict", "failure", "handoff"), default="normal")
    parser.add_argument("--parallel", action="store_true")
    args = parser.parse_args()
    context = make_context(real_data=args.case == "handoff")
    handlers = {}
    if args.case == "missing":
        context.pop("policy_note")
    if args.case == "conflict":
        context["operations_note"]["refunds_allowed"] = True
    if args.case == "failure":
        def unavailable(task, view):
            raise ConnectionError("synthetic service error: do not put raw exceptions in model context")
        handlers["risk"] = unavailable
    runtime = build_team(context, handlers=handlers)
    print("mode:", "concurrent fan-out" if args.parallel else "sequential fan-out")
    print("owner before:", runtime.owner)
    messages = runtime.fan_out(caller="coordinator", targets=("operations", "risk"), parallel=args.parallel)
    for message in messages:
        print(json.dumps(asdict(message), ensure_ascii=False))
    assessment = from_messages(messages)
    print("assessment:", json.dumps(asdict(assessment), ensure_ascii=False))
    print("owner after delegation:", runtime.owner)
    if assessment.status == "needs_review":
        received = runtime.handoff(caller="coordinator", target="privacy")
        print("owner after handoff:", runtime.owner)
        try:
            runtime.finish(caller="coordinator", answer="I still own this.")
        except OwnershipError:
            print("former owner: rejected")
        print("reply:", runtime.finish(caller="privacy", answer=received.finding.summary))
    else:
        print("reply:", runtime.finish(caller="coordinator", answer=assessment.summary))
    print("events (metadata only):")
    for event in runtime.events:
        print(json.dumps(asdict(event), ensure_ascii=False))


if __name__ == "__main__":
    main()
