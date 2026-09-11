"""Trusted report checker. It reads data; it never executes report content."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import stat
import sys

REQUIRED_SECTIONS = ("Background", "Risks", "Recommendation")
MAX_REPORT_BYTES = 65_536


def analyze_report(payload: bytes) -> dict:
    if len(payload) > MAX_REPORT_BYTES:
        raise ValueError("report exceeds 65536 bytes")
    text = payload.decode("utf-8")
    sections: dict[str, list[str]] = {}
    current: str | None = None
    in_code = False
    for line in text.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            in_code = not in_code
            continue
        if in_code:
            continue
        if line.startswith("## "):
            current = line[3:].strip()
            if current in sections:
                raise ValueError(f"duplicate section: {current}")
            sections[current] = []
        elif current is not None and line.strip():
            sections[current].append(line.strip())
    if in_code:
        raise ValueError("unclosed code fence")
    missing = [name for name in REQUIRED_SECTIONS if not sections.get(name)]
    return {
        "passed": not missing,
        "missing_sections": missing,
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check required report sections.")
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    try:
        if not stat.S_ISREG(args.report.stat().st_mode):
            raise ValueError("report must be a regular file")
        with args.report.open("rb") as stream:
            payload = stream.read(MAX_REPORT_BYTES + 1)
        review = analyze_report(payload)
    except (OSError, ValueError) as exc:
        print(f"report check could not run: {exc}", file=sys.stderr)
        return 3
    print(json.dumps(review, ensure_ascii=True))
    return 0 if review["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
