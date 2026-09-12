"""Compare the baseline with a deliberately broken candidate or repaired version."""
import argparse
from dataclasses import asdict
import json
import hashlib
import platform
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from cases import default_cases
from evaluation import evaluate, regression_gate, report_dict
from scenario import run_offline
from tracing import trace_dict


def compare(version: str):
    cases = default_cases()
    baseline = evaluate(cases, lambda request: run_offline(request, version="baseline"), variant="baseline")
    candidate = evaluate(cases, lambda request: run_offline(request, version=version), variant=version)
    return baseline, candidate, regression_gate(baseline, candidate)


def save_bundle(path: Path, baseline, candidate, gate) -> None:
    path.mkdir(parents=True, exist_ok=False)
    dependencies = {}
    for package in ("openai", "opentelemetry-sdk"):
        try:
            dependencies[package] = version(package)
        except PackageNotFoundError:
            dependencies[package] = None
    manifest = {
        "python": platform.python_version(), "platform": platform.system(),
        "dependencies": dependencies, "grader_version": "contract-v1",
        "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in sorted(Path(__file__).parent.glob("*.py"))},
    }
    (path / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    for name, report in (("baseline", baseline), ("candidate", candidate)):
        (path / f"{name}.json").write_text(
            json.dumps(report_dict(report), ensure_ascii=False, indent=2), encoding="utf-8")
        for run in report.runs:
            (path / f"{run.run_id}.trace.json").write_text(
                json.dumps(trace_dict(run.trace), ensure_ascii=False, indent=2), encoding="utf-8")
    (path / "gate.json").write_text(json.dumps(asdict(gate), indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Exit 1 when the candidate fails the regression gate.")
    parser.add_argument("--candidate", choices=("candidate", "fixed"), default="candidate")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    baseline, candidate, gate = compare(args.candidate)
    for report in (baseline, candidate):
        print(report.variant, json.dumps(report.metrics(), ensure_ascii=False))
        for score in report.scores:
            print(" ", score.case_id, "PASS" if score.passed else ",".join(score.failures),
                  "run_id=" + score.run_id)
    print("gate:", "ACCEPT" if gate.accepted else "REJECT", gate.reasons)
    if args.output_dir:
        save_bundle(args.output_dir, baseline, candidate, gate)
        print("saved:", args.output_dir)
    return 0 if gate.accepted else 1


if __name__ == "__main__":
    raise SystemExit(main())
