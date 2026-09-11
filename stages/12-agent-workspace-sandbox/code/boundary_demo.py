"""Harmless negative probes using only files created by this demonstration."""
from __future__ import annotations

from pathlib import Path
import sys
import tempfile

from demo import FIRST_DRAFT
from report_tools import ReportTools
from runner import CommandRunner
from workspace import AgentWorkspace, WorkspaceEscapeError


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="stage12-probes-") as parent:
        outside = Path(parent) / "host-canary.txt"
        outside.write_text("SYNTHETIC CANARY: not a real secret", encoding="utf-8")
        workspace = AgentWorkspace.create(Path(parent) / "run")
        try:
            workspace.read_text("../host-canary.txt")
        except WorkspaceEscapeError:
            print("1. Workspace API rejects ../host-canary.txt")
        else:
            raise RuntimeError("path escape should have been rejected")

        runner = CommandRunner(workspace, allowed_executables={"python": sys.executable})
        # Trusted diagnostic only. This raw interpreter command is NOT an Agent tool.
        observed = runner.run([
            "python", "-I", "-S", "-c",
            "from pathlib import Path; import sys; print(Path(sys.argv[1]).read_text())",
            str(outside),
        ])
        if observed.returncode != 0 or "SYNTHETIC CANARY" not in observed.stdout:
            raise RuntimeError("the local-boundary diagnostic did not complete")
        print("2. Direct child can still read the Host-created canary:", observed.stdout.strip())

        literal = runner.run([
            "python", "-I", "-S", "-c", "import sys; print(sys.argv[1])", "hello && echo not-a-command",
        ])
        print("3. shell=False passes one literal argument:", literal.stdout.strip())

        workspace.write_text("work/report.md", FIRST_DRAFT)
        try:
            ReportTools(workspace).execute({
                "action": "check_report", "path": "work/report.md", "args": ["-c", "print(42)"],
            })
        except ValueError:
            print("4. Report tool rejects extra interpreter arguments before launch")
        else:
            raise RuntimeError("extra arguments should have been rejected")
    print("probe files removed:", not outside.exists())


if __name__ == "__main__":
    main()
