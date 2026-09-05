from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class WorkspaceEscapeError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class AgentWorkspace:
    root: Path

    @classmethod
    def create(cls, root: str | Path) -> "AgentWorkspace":
        resolved = Path(root).resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        return cls(resolved)

    def resolve(self, relative_path: str | Path) -> Path:
        relative = Path(relative_path)
        if relative.is_absolute():
            raise WorkspaceEscapeError("absolute paths are not allowed")
        target = (self.root / relative).resolve()
        if target != self.root and self.root not in target.parents:
            raise WorkspaceEscapeError("path escapes workspace")
        return target

    def write_text(self, relative_path: str, content: str) -> Path:
        target = self.resolve(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def read_text(self, relative_path: str) -> str:
        return self.resolve(relative_path).read_text(encoding="utf-8")

    def list_files(self) -> tuple[str, ...]:
        return tuple(
            str(path.relative_to(self.root))
            for path in sorted(self.root.rglob("*"))
            if path.is_file()
        )
