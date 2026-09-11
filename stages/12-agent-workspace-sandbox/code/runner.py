from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import subprocess
from threading import Thread
from typing import Mapping, Sequence, TextIO

from workspace import AgentWorkspace


@dataclass(frozen=True, slots=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool
    truncated: bool


@dataclass(slots=True)
class _StreamCapture:
    max_chars: int
    chunks: list[str] = field(default_factory=list)
    chars: int = 0
    truncated: bool = False

    def add(self, chunk: str) -> None:
        remaining = self.max_chars - self.chars
        if remaining <= 0:
            self.truncated = True
            return
        kept = chunk[:remaining]
        self.chunks.append(kept)
        self.chars += len(kept)
        if len(kept) != len(chunk):
            self.truncated = True

    def text(self) -> str:
        value = "".join(self.chunks)
        return value + "\n...[truncated]" if self.truncated else value


class CommandRunner:
    """A bounded subprocess wrapper, not a security sandbox.

    The Host registers trusted executable paths under short command aliases. A model or
    script may request an alias such as ``python`` but cannot choose a replacement path.
    """

    def __init__(
        self,
        workspace: AgentWorkspace,
        *,
        allowed_executables: Mapping[str, str | Path],
        max_output_chars: int = 4000,
    ) -> None:
        if max_output_chars <= 0:
            raise ValueError("max_output_chars must be positive")
        self.workspace = workspace
        self.allowed_executables = {
            alias: Path(executable).resolve()
            for alias, executable in allowed_executables.items()
        }
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
        executable = self.allowed_executables.get(command[0])
        if executable is None:
            raise PermissionError(f"executable alias not allowed: {command[0]}")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONIOENCODING": "utf-8",
        }
        env.update(dict(extra_env or {}))
        stdout_capture = _StreamCapture(self.max_output_chars)
        stderr_capture = _StreamCapture(self.max_output_chars)

        process = subprocess.Popen(
            [str(executable), *command[1:]],
            cwd=self.workspace.root,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
        )
        stdout_thread = Thread(
            target=self._drain_limited,
            args=(process.stdout, stdout_capture),
            daemon=True,
        )
        stderr_thread = Thread(
            target=self._drain_limited,
            args=(process.stderr, stderr_capture),
            daemon=True,
        )
        stdout_thread.start()
        stderr_thread.start()
        timed_out = False
        try:
            returncode = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.kill()
            returncode = -1
            process.wait()
        finally:
            stdout_thread.join()
            stderr_thread.join()

        return CommandResult(
            returncode=returncode,
            stdout=stdout_capture.text(),
            stderr=stderr_capture.text(),
            timed_out=timed_out,
            truncated=stdout_capture.truncated or stderr_capture.truncated,
        )

    @staticmethod
    def _drain_limited(stream: TextIO | None, capture: _StreamCapture) -> None:
        if stream is None:
            return
        try:
            while chunk := stream.read(4096):
                capture.add(chunk)
        finally:
            stream.close()
