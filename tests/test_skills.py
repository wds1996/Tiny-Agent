from pathlib import Path

import pytest

pytest.importorskip("yaml")

from tiny_agent.skills import SkillCatalog, SkillFormatError


def test_skill_catalog_progressive_disclosure(tmp_path: Path) -> None:
    skill = tmp_path / "research-review"
    (skill / "references").mkdir(parents=True)
    (skill / "SKILL.md").write_text(
        "---\nname: research-review\ndescription: Review grounded research drafts.\nallowed-tools: Read Search\n---\n\nDetailed procedure.",
        encoding="utf-8",
    )
    (skill / "references" / "RUBRIC.md").write_text("rubric", encoding="utf-8")

    catalog = SkillCatalog(tmp_path)
    descriptors = catalog.discover()
    assert descriptors[0].description == "Review grounded research drafts."
    assert "Detailed procedure" not in catalog.metadata_prompt()

    active = catalog.activate("research-review")
    assert active.instructions == "Detailed procedure."
    assert active.descriptor.allowed_tools == ("Read", "Search")
    assert active.references[0].name == "RUBRIC.md"


def test_skill_name_must_match_directory(tmp_path: Path) -> None:
    skill = tmp_path / "wrong-dir"
    skill.mkdir()
    (skill / "SKILL.md").write_text(
        "---\nname: actual-name\ndescription: A valid description.\n---\nbody",
        encoding="utf-8",
    )
    with pytest.raises(SkillFormatError):
        SkillCatalog(tmp_path).discover()
