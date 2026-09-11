from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

from report_check import analyze_report
from runner import CommandRunner
from workspace import AgentWorkspace


class ReportCheckError(RuntimeError):
    pass


class ArtifactError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ReportReview:
    relative_path: str
    sha256: str
    passed: bool
    missing_sections: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Artifact:
    path: Path
    sha256: str
    size_bytes: int


class ReportTools:
    """Only a fixed check_report action is exposed to the Agent."""

    def __init__(self, workspace: AgentWorkspace) -> None:
        self.workspace = workspace
        self.checker = Path(__file__).with_name("report_check.py").resolve()
        if self.checker.is_relative_to(workspace.root):
            raise ValueError("trusted checker must not live in the writable workspace")
        self.runner = CommandRunner(workspace, allowed_executables={"python": sys.executable})

    def execute(self, proposal: dict[str, Any]) -> ReportReview:
        if not isinstance(proposal, dict) or set(proposal) != {"action", "path"}:
            raise ValueError("expected exactly action and path")
        if proposal["action"] != "check_report":
            raise PermissionError("only check_report is available")
        if not isinstance(proposal["path"], str):
            raise ValueError("path must be a string")
        return self.check_report(proposal["path"])

    def check_report(self, relative_path: str) -> ReportReview:
        target = self.workspace.resolve(relative_path)
        local = target.relative_to(self.workspace.root)
        if local.parts[0] != "work" or target.suffix != ".md":
            raise ValueError("check_report accepts only a Markdown file under work/")
        self.workspace.read_bytes(relative_path)  # Check type and budget before launching.
        command = ["python", "-I", "-S", "-B", str(self.checker), str(target)]
        result = self.runner.run(command, timeout_seconds=5.0)
        if result.timed_out or not result.cleanup_complete or not result.output_complete:
            raise ReportCheckError("checker did not finish with complete output")
        if result.truncated or result.returncode not in {0, 2}:
            raise ReportCheckError(f"checker execution failed: {result.stderr[:300]}")
        try:
            actual = json.loads(result.stdout)
            # Re-read current bytes: a concurrent rewrite must not inherit an old verdict.
            expected = analyze_report(self.workspace.read_bytes(relative_path))
            if not isinstance(actual, dict) or set(actual) != set(expected):
                raise ValueError("invalid checker fields")
            if type(actual["passed"]) is not bool or actual != expected:
                raise ValueError("checker result does not match the current report")
            if result.returncode != (0 if actual["passed"] else 2):
                raise ValueError("exit code and verdict disagree")
        except (ValueError, OSError) as exc:
            raise ReportCheckError("invalid or stale checker output") from exc
        return ReportReview(
            local.as_posix(), actual["sha256"], actual["passed"], tuple(actual["missing_sections"])
        )


def export_report(workspace: AgentWorkspace, review: ReportReview, destination: Path) -> Artifact:
    """Host-only export of the checked bytes to a Host-selected destination.

    Structural validation is not authorization, factual verification or HTML sanitization.
    """
    if not review.passed:
        raise ArtifactError("report did not pass its structural check")
    target = workspace.resolve(review.relative_path)
    if target.relative_to(workspace.root).parts[0] != "work" or target.suffix != ".md":
        raise ArtifactError("export source must be a work/ Markdown report")
    payload = workspace.read_bytes(review.relative_path)
    digest = hashlib.sha256(payload).hexdigest()
    if digest != review.sha256 or not analyze_report(payload)["passed"]:
        raise ArtifactError("report changed after review; run check_report again")
    destination = Path(destination).absolute()
    resolved = destination.resolve()
    if resolved.is_relative_to(workspace.root):
        raise ArtifactError("export must outlive the temporary workspace")
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation: never silently replace an existing delivery or follow its symlink.
    with destination.open("xb") as stream:
        stream.write(payload)
    return Artifact(destination, digest, len(payload))
