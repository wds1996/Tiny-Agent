from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Sequence


class WorkspacePathError(ValueError):
    """A requested path escapes the application-owned Agent workspace."""


@dataclass(frozen=True, slots=True)
class WorkspaceArtifact:
    relative_path: str
    size_bytes: int


class AgentWorkspace:
    """Least-privilege filesystem view rooted at one application-owned directory."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve(self, relative_path: str | Path) -> Path:
        raw = Path(relative_path)
        if raw.is_absolute():
            raise WorkspacePathError("workspace paths must be relative")
        target = (self.root / raw).resolve()
        try:
            target.relative_to(self.root)
        except ValueError as exc:
            raise WorkspacePathError("workspace path escapes configured root") from exc
        return target

    def read_text(self, relative_path: str | Path, *, max_chars: int = 200_000) -> str:
        if max_chars <= 0:
            raise ValueError("max_chars must be positive")
        target = self.resolve(relative_path)
        text = target.read_text(encoding="utf-8")
        if len(text) > max_chars:
            raise ValueError("workspace file exceeds configured read limit")
        return text

    def write_text(
        self,
        relative_path: str | Path,
        content: str,
        *,
        overwrite: bool = False,
    ) -> WorkspaceArtifact:
        target = self.resolve(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        mode = "w" if overwrite else "x"
        with target.open(mode, encoding="utf-8") as handle:
            handle.write(content)
        return WorkspaceArtifact(
            relative_path=str(target.relative_to(self.root)),
            size_bytes=target.stat().st_size,
        )

    def list_files(self) -> tuple[WorkspaceArtifact, ...]:
        artifacts: list[WorkspaceArtifact] = []
        for path in sorted(item for item in self.root.rglob("*") if item.is_file()):
            resolved = path.resolve()
            try:
                relative = resolved.relative_to(self.root)
            except ValueError:
                continue
            artifacts.append(
                WorkspaceArtifact(str(relative), resolved.stat().st_size)
            )
        return tuple(artifacts)


@dataclass(frozen=True, slots=True)
class DockerSandboxPolicy:
    image: str = "python:3.12-slim"
    memory: str = "512m"
    cpus: float = 1.0
    pids_limit: int = 128
    timeout_seconds: float = 30.0
    network_enabled: bool = False
    user: str = "65534:65534"
    max_output_chars: int = 100_000

    def __post_init__(self) -> None:
        if not self.image.strip():
            raise ValueError("sandbox image must be non-empty")
        if self.cpus <= 0 or self.pids_limit <= 0 or self.timeout_seconds <= 0:
            raise ValueError("sandbox CPU/PID/timeout limits must be positive")
        if self.max_output_chars <= 0:
            raise ValueError("max_output_chars must be positive")


@dataclass(frozen=True, slots=True)
class SandboxResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False


class DockerSandboxRunner:
    """Container-backed execution baseline for model-generated or risky commands.

    This is intentionally stronger than `subprocess`, but it is still a baseline,
    not a claim that Docker alone is a perfect hostile-code sandbox. Production
    deployments should add hardened runtime/VM isolation, image governance,
    egress policy, seccomp/AppArmor/SELinux, secrets separation, and auditing.
    """

    def __init__(self, workspace: AgentWorkspace, policy: DockerSandboxPolicy | None = None) -> None:
        self.workspace = workspace
        self.policy = policy or DockerSandboxPolicy()

    def build_command(self, argv: Sequence[str]) -> list[str]:
        if not argv or any(not isinstance(part, str) or not part for part in argv):
            raise ValueError("sandbox argv must contain non-empty strings")
        command = [
            "docker",
            "run",
            "--rm",
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--pids-limit",
            str(self.policy.pids_limit),
            "--memory",
            self.policy.memory,
            "--cpus",
            str(self.policy.cpus),
            "--user",
            self.policy.user,
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=64m",
            "--volume",
            f"{self.workspace.root}:/workspace:rw",
            "--workdir",
            "/workspace",
        ]
        command.extend(["--network", "bridge" if self.policy.network_enabled else "none"])
        command.append(self.policy.image)
        command.extend(argv)
        return command

    def run(self, argv: Sequence[str]) -> SandboxResult:
        command = self.build_command(argv)
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                timeout=self.policy.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
            stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
            return SandboxResult(
                returncode=124,
                stdout=stdout[: self.policy.max_output_chars],
                stderr=stderr[: self.policy.max_output_chars],
                timed_out=True,
            )
        return SandboxResult(
            returncode=completed.returncode,
            stdout=completed.stdout[: self.policy.max_output_chars],
            stderr=completed.stderr[: self.policy.max_output_chars],
        )
