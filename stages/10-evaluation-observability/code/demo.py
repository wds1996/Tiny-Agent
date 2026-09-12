"""Run one inspectable story, without credentials or network calls."""
import argparse

from cases import default_cases
from evaluation import score_case
from scenario import VERSIONS, run_offline
from tracing import format_trace


def main() -> None:
    cases = {c.id: c for c in default_cases()}
    parser = argparse.ArgumentParser(description="Inspect one real local execution and its score.")
    parser.add_argument("--case", choices=tuple(cases), default="within-window")
    parser.add_argument("--version", choices=VERSIONS, default="candidate")
    args = parser.parse_args()
    case = cases[args.case]
    run = run_offline(case.request, version=args.version)
    print("question:", case.request.question)
    print("answer:", run.answer)
    print(format_trace(run.trace))
    print("retrieved:", run.retrieved_ids)
    print("visible to answer step:", run.visible_ids)
    score = score_case(case, run)
    print("passed:", score.passed, "failed checks:", score.failures)
    print("latency_ms (this machine):", round(run.latency_ms, 3))
    print("model calls: 0; no model bill, no invented cost estimate")


if __name__ == "__main__":
    main()
