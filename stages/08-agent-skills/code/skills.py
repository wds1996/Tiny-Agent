from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True, slots=True)
class SkillMetadata:
    name: str
    description: str
    path: Path


@dataclass(frozen=True, slots=True)
class ActivatedSkill:
    metadata: SkillMetadata
    instructions: str


def parse_frontmatter_lines(lines: list[str], *, path: Path) -> dict[str, str]:
    fields: dict[str, str] = {}
    for raw_line in lines:
        if not raw_line.strip():
            continue
        if ":" not in raw_line:
            raise ValueError(f"{path} has unsupported frontmatter line: {raw_line}")
        key, value = raw_line.split(":", 1)
        fields[key.strip()] = value.strip().strip('"').strip("'")
    return fields


def read_frontmatter(path: Path) -> dict[str, str]:
    """Read only the YAML-like header used during Skill discovery."""
    with path.open(encoding="utf-8") as file:
        if file.readline().strip() != "---":
            raise ValueError(f"{path} is missing YAML frontmatter")

        frontmatter: list[str] = []
        for line in file:
            if line.strip() == "---":
                return parse_frontmatter_lines(frontmatter, path=path)
            frontmatter.append(line)

    raise ValueError(f"{path} has incomplete frontmatter")


def parse_skill_file(path: Path) -> tuple[dict[str, str], str]:
    """Load a complete Skill only after it has been selected for activation."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"{path} is missing YAML frontmatter")
    try:
        _, frontmatter, body = text.split("---", 2)
    except ValueError as exc:
        raise ValueError(f"{path} has incomplete frontmatter") from exc

    fields = parse_frontmatter_lines(frontmatter.strip().splitlines(), path=path)
    return fields, body.strip()


class SkillCatalog:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()

    def discover(self) -> list[SkillMetadata]:
        skills: list[SkillMetadata] = []
        if not self.root.exists():
            return skills
        for skill_md in sorted(self.root.glob("*/SKILL.md")):
            fields = read_frontmatter(skill_md)
            name = fields.get("name", "")
            description = fields.get("description", "")
            directory_name = skill_md.parent.name

            if not _NAME_RE.fullmatch(name):
                raise ValueError(f"invalid skill name: {name!r}")
            if name != directory_name:
                raise ValueError(
                    f"skill name {name!r} must match directory {directory_name!r}"
                )
            if not description:
                raise ValueError(f"skill {name!r} needs a description")
            skills.append(SkillMetadata(name, description, skill_md.parent))
        return skills

    def activate(self, name: str) -> ActivatedSkill:
        skill_dir = (self.root / name).resolve()
        if skill_dir.parent != self.root:
            raise ValueError("invalid skill path")
        fields, body = parse_skill_file(skill_dir / "SKILL.md")
        if fields.get("name") != name:
            raise ValueError("skill metadata does not match requested name")
        return ActivatedSkill(
            SkillMetadata(name, fields["description"], skill_dir),
            body,
        )

    def read_resource(self, skill_name: str, relative_path: str) -> str:
        skill_root = (self.root / skill_name).resolve()
        target = (skill_root / relative_path).resolve()
        if target != skill_root and skill_root not in target.parents:
            raise ValueError("resource path escapes skill directory")
        if not target.is_file():
            raise FileNotFoundError(relative_path)
        return target.read_text(encoding="utf-8")
