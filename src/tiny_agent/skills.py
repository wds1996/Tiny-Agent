from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Mapping


_SKILL_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class SkillFormatError(ValueError):
    """A SKILL.md file violates the subset of the Agent Skills spec we enforce."""


@dataclass(frozen=True, slots=True)
class SkillDescriptor:
    name: str
    description: str
    root: Path
    license: str | None = None
    compatibility: str | None = None
    metadata: Mapping[str, str] | None = None
    allowed_tools: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ActivatedSkill:
    descriptor: SkillDescriptor
    instructions: str
    references: tuple[Path, ...]
    scripts: tuple[Path, ...]
    assets: tuple[Path, ...]


class SkillCatalog:
    """Discover Agent Skills with progressive disclosure.

    Discovery loads only metadata. Activation loads SKILL.md instructions and
    enumerates bundled resources. `allowed-tools` is surfaced as metadata only;
    it is never treated as Tiny-Agent authorization.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._skills: dict[str, SkillDescriptor] = {}

    def discover(self) -> tuple[SkillDescriptor, ...]:
        skills: dict[str, SkillDescriptor] = {}
        for directory in sorted(path for path in self.root.iterdir() if path.is_dir()):
            resolved = directory.resolve()
            _ensure_within(self.root, resolved)
            skill_file = resolved / "SKILL.md"
            if not skill_file.is_file():
                continue
            descriptor, _ = _parse_skill_file(skill_file)
            if descriptor.name != directory.name:
                raise SkillFormatError(
                    f"skill name {descriptor.name!r} must match directory {directory.name!r}"
                )
            if descriptor.name in skills:
                raise SkillFormatError(f"duplicate skill name: {descriptor.name}")
            skills[descriptor.name] = descriptor
        self._skills = skills
        return tuple(skills[name] for name in sorted(skills))

    def get(self, name: str) -> SkillDescriptor:
        if not self._skills:
            self.discover()
        try:
            return self._skills[name]
        except KeyError as exc:
            raise KeyError(f"unknown skill: {name}") from exc

    def metadata_prompt(self) -> str:
        """Return startup-sized metadata, not full skill instructions."""

        if not self._skills:
            self.discover()
        return "\n".join(
            f"- {skill.name}: {skill.description}"
            for skill in (self._skills[name] for name in sorted(self._skills))
        )

    def activate(self, name: str) -> ActivatedSkill:
        descriptor = self.get(name)
        _, body = _parse_skill_file(descriptor.root / "SKILL.md")
        return ActivatedSkill(
            descriptor=descriptor,
            instructions=body.strip(),
            references=_safe_files(descriptor.root, "references"),
            scripts=_safe_files(descriptor.root, "scripts"),
            assets=_safe_files(descriptor.root, "assets"),
        )


def _parse_skill_file(path: Path) -> tuple[SkillDescriptor, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise SkillFormatError(f"{path} must start with YAML frontmatter")
    try:
        _, frontmatter, body = text.split("---", 2)
    except ValueError as exc:
        raise SkillFormatError(f"{path} has incomplete YAML frontmatter") from exc

    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - exercised in core-only installs
        raise RuntimeError(
            "Agent Skills parsing requires: python -m pip install -e '.[stage06b]'"
        ) from exc

    data = yaml.safe_load(frontmatter) or {}
    if not isinstance(data, dict):
        raise SkillFormatError("SKILL.md frontmatter must be a mapping")

    name = str(data.get("name") or "")
    description = str(data.get("description") or "")
    if not _SKILL_NAME.fullmatch(name) or len(name) > 64:
        raise SkillFormatError("skill name must be 1-64 lowercase alphanumeric/hyphen characters")
    if not description.strip() or len(description) > 1024:
        raise SkillFormatError("skill description must be 1-1024 non-empty characters")

    compatibility = data.get("compatibility")
    if compatibility is not None and len(str(compatibility)) > 500:
        raise SkillFormatError("skill compatibility must be at most 500 characters")

    metadata_raw = data.get("metadata") or {}
    if not isinstance(metadata_raw, dict):
        raise SkillFormatError("skill metadata must be a mapping")
    metadata = {str(key): str(value) for key, value in metadata_raw.items()}

    allowed_tools_raw = data.get("allowed-tools") or ""
    if not isinstance(allowed_tools_raw, str):
        raise SkillFormatError("allowed-tools must be a space-separated string")

    descriptor = SkillDescriptor(
        name=name,
        description=description.strip(),
        root=path.parent.resolve(),
        license=str(data["license"]) if data.get("license") is not None else None,
        compatibility=str(compatibility) if compatibility is not None else None,
        metadata=metadata,
        allowed_tools=tuple(part for part in allowed_tools_raw.split() if part),
    )
    return descriptor, body


def _safe_files(root: Path, child: str) -> tuple[Path, ...]:
    directory = root / child
    if not directory.exists():
        return ()
    resolved_directory = directory.resolve()
    _ensure_within(root, resolved_directory)
    files: list[Path] = []
    for path in sorted(item for item in directory.rglob("*") if item.is_file()):
        resolved = path.resolve()
        _ensure_within(root, resolved)
        files.append(resolved)
    return tuple(files)


def _ensure_within(root: Path, target: Path) -> None:
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise SkillFormatError("skill path escapes the configured catalog root") from exc
