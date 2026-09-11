"""Optional Linux-container illustration: fixed checker, read-only file mounts.

Default: print the profile only. --run requires a local Docker Engine and an
already-present Python image. This is not a service for arbitrary hostile code.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import tempfile
from uuid import uuid4

from demo import FINAL_DRAFT
from report_check import analyze_report
from runner import CommandRunner
from workspace import AgentWorkspace


def build_command(checker: Path, report: Path, *, image: str, name: str) -> list[str]:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/:@-]*", image):
        raise ValueError("invalid Host-selected image reference")
    if not re.fullmatch(r"stage12-[a-f0-9]{32}", name):
        raise ValueError("invalid container name")
    sources = [checker.resolve(strict=True), report.resolve(strict=True)]
    if any(not path.is_file() or "," in str(path) or "\n" in str(path) for path in sources):
        raise ValueError("mount sources must be regular files without commas or newlines")
    return [
        "docker", "run", "--name", name, "--pull=never",
        "--network=none", "--read-only", "--user=65534:65534",
        "--cap-drop=ALL", "--security-opt=no-new-privileges",
        "--memory=128m", "--memory-swap=128m", "--cpus=0.5", "--pids-limit=32",
        "--tmpfs=/tmp:rw,noexec,nosuid,nodev,size=16m,mode=1777", "--workdir=/tmp",
        "--mount", f"type=bind,src={sources[0]},dst=/app/report_check.py,readonly",
        "--mount", f"type=bind,src={sources[1]},dst=/data/report.md,readonly",
        "--entrypoint=python", image, "-I", "-S", "-B", "/app/report_check.py", "/data/report.md",
    ]


def run_container(workspace: AgentWorkspace, command: list[str], *, name: str) -> dict:
    docker = shutil.which("docker")
    if docker is None:
        raise RuntimeError("Docker is not installed; no local execution fallback is used")
    runner = CommandRunner(workspace, allowed_executables={"docker": Path(docker).resolve()})
    try:
        result = runner.run(command, timeout_seconds=30.0)
    finally:
        # Killing the Docker CLI alone does not stop a daemon-managed container.
        cleanup = runner.run(["docker", "rm", "--force", name], timeout_seconds=5.0)
    if result.returncode not in {0, 2} or result.timed_out:
        raise RuntimeError(f"container did not run successfully: {result.stderr[:500]}")
    if (not result.output_complete or result.truncated or not result.cleanup_complete
            or cleanup.returncode != 0 or cleanup.timed_out or not cleanup.cleanup_complete):
        raise RuntimeError("complete output and container cleanup could not be confirmed")
    review = json.loads(result.stdout)
    expected = analyze_report(workspace.read_bytes("work/report.md"))
    if review != expected or result.returncode != (0 if expected["passed"] else 2):
        raise RuntimeError("container verdict does not match the staged report")
    return review


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="python:3.12-slim")
    parser.add_argument("--run", action="store_true", help="actually use the local Docker Engine")
    args = parser.parse_args()
    with AgentWorkspace.temporary() as workspace, tempfile.TemporaryDirectory() as trusted:
        report = workspace.write_text("work/report.md", FINAL_DRAFT)
        checker = Path(trusted) / "report_check.py"
        checker.write_bytes(Path(__file__).with_name("report_check.py").read_bytes())
        # These are newly created teaching files, not existing user files.
        checker.chmod(0o644)
        report.chmod(0o644)
        name = f"stage12-{uuid4().hex}"
        command = build_command(checker, report, image=args.image, name=name)
        if not args.run:
            print("PROFILE ONLY: no container started; mount paths below are temporary.")
            print(json.dumps(command, indent=2))
        else:
            print(json.dumps(run_container(workspace, command, name=name), indent=2))


if __name__ == "__main__":
    main()
