from __future__ import annotations

from dataclasses import dataclass, field
import math
import os
from pathlib import Path
import signal
import subprocess
from threading import Lock, Thread
import time
from typing import BinaryIO, Mapping, Sequence

from workspace import AgentWorkspace


@dataclass(frozen=True, slots=True)
class CommandResult:
    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool
    stdout_truncated: bool
    stderr_truncated: bool
    output_complete: bool
    cleanup_complete: bool

    @property
    def truncated(self) -> bool:
        return self.stdout_truncated or self.stderr_truncated


@dataclass
class _Capture:
    limit: int
    data: bytearray = field(default_factory=bytearray)
    truncated: bool = False
    failed: bool = False
    lock: Lock = field(default_factory=Lock)

    def add(self, chunk: bytes) -> None:
        with self.lock:
            remaining = self.limit - len(self.data)
            self.data.extend(chunk[:remaining])
            self.truncated |= len(chunk) > remaining

    def snapshot(self) -> tuple[str, bool, bool]:
        with self.lock:
            return self.data.decode("utf-8", errors="replace"), self.truncated, self.failed


class CommandRunner:
    """Host-only subprocess plumbing, NOT an Agent-facing permission system.

    Only register audited programs. Free interpreter arguments can execute arbitrary
    code even with shell=False. Use the narrower ReportTools facade for proposals.
    """

    def __init__(
        self,
        workspace: AgentWorkspace,
        *,
        allowed_executables: Mapping[str, str | Path],
        max_output_bytes: int = 16_384,
    ) -> None:
        if type(max_output_bytes) is not int or max_output_bytes <= 0:
            raise ValueError("max_output_bytes must be a positive integer")
        self.workspace = workspace
        self.max_output_bytes = max_output_bytes
        self.executables: dict[str, Path] = {}
        for alias, value in allowed_executables.items():
            if not isinstance(alias, str) or not alias.isidentifier():
                raise ValueError("executable alias must be an identifier")
            path = Path(value)
            if not path.is_absolute() or not path.is_file():
                raise ValueError("Host must register an existing absolute executable path")
            if path.suffix.lower() in {".bat", ".cmd"}:
                raise ValueError("batch files are outside this runner's contract")
            self.executables[alias] = path.resolve()

    def run(self, command: Sequence[str], *, timeout_seconds: float = 5.0) -> CommandResult:
        if (isinstance(command, (str, bytes)) or not command
                or not all(isinstance(arg, str) and "\x00" not in arg for arg in command)):
            raise ValueError("command must be a nonempty sequence of string arguments")
        executable = self.executables.get(command[0])
        if executable is None:
            raise PermissionError(f"executable alias not registered: {command[0]}")
        if (isinstance(timeout_seconds, bool) or not math.isfinite(timeout_seconds)
                or timeout_seconds <= 0):
            raise ValueError("timeout_seconds must be finite and positive")

        # No automatic copying of HOME, PATH, API keys, PYTHONPATH, or proxy settings.
        env = {"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
        if os.name == "nt" and "SystemRoot" in os.environ:
            env["SystemRoot"] = os.environ["SystemRoot"]
        process = subprocess.Popen(
            [str(executable), *command[1:]],
            cwd=self.workspace.root,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            bufsize=0,
            start_new_session=(os.name == "posix"),
        )
        deadline = time.monotonic() + timeout_seconds
        captures = [_Capture(self.max_output_bytes), _Capture(self.max_output_bytes)]
        threads = [
            Thread(target=self._drain, args=(stream, capture), daemon=True)
            for stream, capture in zip((process.stdout, process.stderr), captures)
        ]
        for thread in threads:
            thread.start()
        timed_out = False
        try:
            process.wait(timeout=max(0.0, deadline - time.monotonic()))
            for thread in threads:
                thread.join(timeout=max(0.0, deadline - time.monotonic()))
            # A descendant can keep a pipe open even after the direct child exits.
            timed_out = any(thread.is_alive() for thread in threads)
        except subprocess.TimeoutExpired:
            timed_out = True
        except BaseException:
            self._stop(process)
            self._settle(process, threads)
            raise
        if timed_out:
            self._stop(process)
        cleanup_complete = self._settle(process, threads)
        out, out_cut, out_failed = captures[0].snapshot()
        err, err_cut, err_failed = captures[1].snapshot()
        return CommandResult(
            returncode=process.returncode,
            stdout=out,
            stderr=err,
            timed_out=timed_out,
            stdout_truncated=out_cut,
            stderr_truncated=err_cut,
            output_complete=not any(t.is_alive() for t in threads) and not (out_failed or err_failed),
            cleanup_complete=cleanup_complete,
        )

    @staticmethod
    def _drain(stream: BinaryIO | None, capture: _Capture) -> None:
        if stream is None:
            return
        try:
            with stream:
                while chunk := stream.read(4096):
                    capture.add(chunk)
        except OSError:
            with capture.lock:
                capture.failed = True

    @staticmethod
    def _stop(process: subprocess.Popen) -> None:
        try:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
        except ProcessLookupError:
            pass

    @staticmethod
    def _settle(process: subprocess.Popen, threads: list[Thread]) -> bool:
        # Bounded best-effort cleanup; this is not a process-tree security boundary.
        until = time.monotonic() + 1.0
        try:
            process.wait(timeout=max(0.0, until - time.monotonic()))
        except subprocess.TimeoutExpired:
            return False
        for thread in threads:
            thread.join(timeout=max(0.0, until - time.monotonic()))
        return not any(thread.is_alive() for thread in threads)
