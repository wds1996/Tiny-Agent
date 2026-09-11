from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from uuid import uuid4

from report_tools import ReportTools, export_report
from workspace import AgentWorkspace

BRIEF = """Prepare a support-assistant pilot report.
The proposed pilot includes 20 support staff.
The assistant suggests replies; it cannot execute refunds.
There are no pilot results yet. Do not invent performance numbers.
Include Background, Risks and Recommendation, with content under each heading.
"""

FIRST_DRAFT = """# Support-assistant pilot

## Background
The proposed pilot includes 20 support staff. No pilot results are available yet.

## Recommendation
Start a supervised trial. The assistant suggests replies, but cannot execute refunds.
"""

FINAL_DRAFT = """# Support-assistant pilot

## Background
The proposed pilot includes 20 support staff. No pilot results are available yet.

## Risks
Suggested replies may be inaccurate. Staff must review them before sending.
Do not expose customer information unnecessarily or allow the assistant to execute refunds.

## Recommendation
Start a supervised trial and measure results before deciding whether to expand it.
"""


def run_demo(output_dir: Path) -> Path:
    destination = Path(output_dir).absolute() / f"report-{uuid4().hex[:12]}.md"
    with AgentWorkspace.temporary() as workspace:
        workspace.import_input("inputs/brief.txt", BRIEF)
        workspace.write_text("work/report.md", FIRST_DRAFT)
        root = workspace.root
        print("workspace:", root)
        print("files:", workspace.list_files())

        tools = ReportTools(workspace)
        proposal = {"action": "check_report", "path": "work/report.md"}
        first = tools.execute(proposal)
        print("first check:", first.passed, "missing:", first.missing_sections)
        if first.passed or first.missing_sections != ("Risks",):
            raise RuntimeError("the incomplete fixture must fail for missing Risks")

        # Fixed teaching revision, not an online model call or arbitrary generated code.
        workspace.write_text("work/report.md", FINAL_DRAFT)
        final = tools.execute(proposal)
        print("second check:", final.passed)
        artifact = export_report(workspace, final, destination)
        print("exported:", artifact.path)
        print("sha256:", artifact.sha256, "bytes:", artifact.size_bytes)

    print("workspace removed:", not root.exists())
    print("export survives:", artifact.path.is_file())
    if hashlib.sha256(artifact.path.read_bytes()).hexdigest() != artifact.sha256:
        raise RuntimeError("exported bytes do not match the checked report")
    return artifact.path


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare, check and export one pilot report.")
    parser.add_argument("--output-dir", type=Path, default=Path("stage12-output"))
    args = parser.parse_args()
    run_demo(args.output_dir)


if __name__ == "__main__":
    main()
