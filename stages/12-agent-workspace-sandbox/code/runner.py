from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
from typing import Mapping, Sequence

from workspace import AgentWorkspace


@dataclass(frozen=True, slots=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool
    truncated: bool


class CommandRunner:
    """A bounded subprocess wrapper, not a security sandbox."""

    def __init__(
        self,
        workspace: AgentWorkspace,
        *,
        allowed_executables: set[str],
        max_output_chars: int = 4000,
    ) -> None:
        self.workspace = workspace
        self.allowed_executables = set(allowed_executables)
        self.max_output_chars = max_output_chars

    def run(
        self,
        command: Sequence[str],
        *,
        timeout_seconds: float = 5.0,
        extra_env: Mapping[str, str] | None = None,
    ) -> CommandResult:
        if not command:
            raise ValueError("command must not be empty")
        executable_name = Path(command[0]).name
        if executable_name not in self.allowed_executables:
            raise PermissionError(f"executable not allowed: {executable_name}")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONIOENCODING": "utf-8",
        }
        env.update(dict(extra_env or {}))

        try:
            completed = subprocess.run(
                list(command),
                cwd=self.workspace.root,
                env=env,
                text=True,
                capture_output=True,
                timeout=timeout_seconds,
                shell=False,
                check=False,
            )
            stdout, out_truncated = self._truncate(completed.stdout)
            stderr, err_truncated = self._truncate(completed.stderr)
            return CommandResult(
                completed.returncode,
                stdout,
                stderr,
                False,
                out_truncated or err_truncated,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = self._decode_timeout_stream(exc.stdout)
            stderr = self._decode_timeout_stream(exc.stderr)
            stdout, out_truncated = self._truncate(stdout)
            stderr, err_truncated = self._truncate(stderr)
            return CommandResult(-1, stdout, stderr, True, out_truncated or err_truncated)

    def _truncate(self, text: str) -> tuple[str, bool]:
        if len(text) <= self.max_output_chars:
            return text, False
        return text[: self.max_output_chars] + "\n...[truncated]", True

    @staticmethod
    def _decode_timeout_stream(value: str | bytes | None) -> str:
        if value is None:
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return value
