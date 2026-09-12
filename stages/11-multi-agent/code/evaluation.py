"""Compare the same deterministic rules; this is not a live-model benchmark."""
from __future__ import annotations

from dataclasses import asdict
import json
import time

from scenario import ASSIGNMENTS, CONTEXT_KEYS, build_team, combine, from_messages, make_context, operations, risk
from team import project_context


def evaluate() -> list[dict]:
    cases = []
    normal = make_context()
    cases.append(("normal", normal, "ready_for_draft"))
    missing = make_context()
    missing.pop("policy_note")
    cases.append(("missing-policy", missing, "needs_input"))
    conflict = make_context()
    conflict["operations_note"]["refunds_allowed"] = True
    cases.append(("conflicting-refund-rule", conflict, "conflict"))
    cases.append(("real-conversations", make_context(real_data=True), "needs_review"))
    rows = []
    for name, context, expected in cases:
        for mode in ("single", "team", "parallel-team"):
            start = time.perf_counter()
            if mode == "single":
                # One trusted controller applies both rules; no specialist messages.
                finding_map = {
                    "operations": operations(ASSIGNMENTS["operations"], project_context(context, CONTEXT_KEYS["operations"])),
                    "risk": risk(ASSIGNMENTS["risk"], project_context(context, CONTEXT_KEYS["risk"])),
                }
                result = combine(finding_map)
                boundary_calls = 0
            else:
                runtime = build_team(context, run_id=name)
                messages = runtime.fan_out(caller="coordinator", targets=("operations", "risk"), parallel=mode == "parallel-team")
                result = from_messages(messages)
                boundary_calls = runtime.calls_used
            expected_sources = ("ops-01",) if name == "missing-policy" else ("ops-01", "policy-01")
            no_leak = context["private_note"] not in json.dumps(asdict(result))
            passed = result.status == expected and result.evidence_ids == expected_sources and no_leak
            rows.append({"case": name, "mode": mode, "passed": passed,
                         "status": result.status, "boundary_calls": boundary_calls,
                         "latency_ms": round((time.perf_counter() - start) * 1000, 3),
                         "model_requests": 0, "model_tokens": None, "model_cost": None})
    return rows


def main() -> None:
    rows = evaluate()
    for row in rows:
        print(json.dumps(row, ensure_ascii=False))
    print(f"{sum(row['passed'] for row in rows)}/{len(rows)} deterministic comparisons passed")
    print("Equal scripted rules do not prove a multi-agent quality gain. Live token/cost metrics are not measured.")
    if not all(row["passed"] for row in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
