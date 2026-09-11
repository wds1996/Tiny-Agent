from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
import stat
import tempfile
from typing import Iterator


class WorkspaceEscapeError(ValueError):
    pass


class FileBudgetError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AgentWorkspace:
    """A file API for a trusted, private directory; not OS-level isolation."""

    root: Path
    max_file_bytes: int = 65_536

    @classmethod
    def create(cls, root: str | Path, *, max_file_bytes: int = 65_536) -> AgentWorkspace:
        if type(max_file_bytes) is not int or max_file_bytes <= 0:
            raise ValueError("max_file_bytes must be a positive integer")
        root = Path(root).absolute()
        # The Host chooses a new directory, never an existing user's workspace.
        root.mkdir(parents=True, exist_ok=False, mode=0o700)
        workspace = cls(root.resolve(), max_file_bytes)
        for name in ("inputs", "work", "artifacts"):
            (workspace.root / name).mkdir()
        return workspace

    @classmethod
    @contextmanager
    def temporary(cls, *, max_file_bytes: int = 65_536) -> Iterator[AgentWorkspace]:
        with tempfile.TemporaryDirectory(prefix="tiny-agent-stage12-") as parent:
            yield cls.create(Path(parent) / "run", max_file_bytes=max_file_bytes)

    def resolve(self, relative_path: str | Path) -> Path:
        raw = str(relative_path)
        relative = Path(raw)
        windows = PureWindowsPath(raw)
        if (not raw.strip() or relative.is_absolute() or windows.drive
                or windows.root or "\\" in raw or ":" in raw or "\x00" in raw):
            raise WorkspaceEscapeError("use a relative path with / separators")
        target = (self.root / relative).resolve()
        try:
            local = target.relative_to(self.root)
        except ValueError as exc:
            raise WorkspaceEscapeError("path escapes workspace") from exc
        if not local.parts or local.parts[0] not in {"inputs", "work", "artifacts"}:
            raise WorkspaceEscapeError("path must be inside inputs/, work/ or artifacts/")
        # Conservative policy: do not follow even internal symlinks via this API.
        current = self.root
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                raise WorkspaceEscapeError("symlinks are not accepted by this file API")
        return target

    def import_input(self, relative_path: str, content: str) -> Path:
        """Host-only setup operation; not an Agent tool."""
        target = self.resolve(relative_path)
        if target.relative_to(self.root).parts[0] != "inputs":
            raise WorkspaceEscapeError("inputs must be imported under inputs/")
        payload = self._encode(content)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(payload)
        return target

    def write_text(self, relative_path: str, content: str) -> Path:
        target = self.resolve(relative_path)
        if target.relative_to(self.root).parts[0] not in {"work", "artifacts"}:
            raise PermissionError("Agent writes cannot modify inputs/")
        payload = self._encode(content)
        if target.exists() and not stat.S_ISREG(target.stat().st_mode):
            raise ValueError("target must be a regular file")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        return target

    def read_bytes(self, relative_path: str | Path) -> bytes:
        target = self.resolve(relative_path)
        if not stat.S_ISREG(target.stat().st_mode):
            raise ValueError("source must be a regular file")
        with target.open("rb") as stream:
            payload = stream.read(self.max_file_bytes + 1)
        if len(payload) > self.max_file_bytes:
            raise FileBudgetError("file exceeds the read budget")
        return payload

    def read_text(self, relative_path: str | Path) -> str:
        return self.read_bytes(relative_path).decode("utf-8")

    def list_files(self) -> tuple[str, ...]:
        # No recursive symlink traversal. Inventory is not export authorization.
        def walk(directory: Path) -> Iterator[str]:
            for path in sorted(directory.iterdir()):
                if path.is_symlink():
                    continue
                checked = self.resolve(path.relative_to(self.root))
                if checked.is_dir():
                    yield from walk(checked)
                elif stat.S_ISREG(checked.stat().st_mode):
                    yield checked.relative_to(self.root).as_posix()
        return tuple(walk(self.root))

    def _encode(self, content: str) -> bytes:
        if not isinstance(content, str):
            raise TypeError("content must be text")
        payload = content.encode("utf-8")
        if len(payload) > self.max_file_bytes:
            raise FileBudgetError("file exceeds the write budget")
        return payload
