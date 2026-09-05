from pathlib import Path

from skills import SkillCatalog


def main() -> None:
    root = Path(__file__).with_name("skills")
    catalog = SkillCatalog(root)

    for skill in catalog.discover():
        print("discovered:", skill.name, "->", skill.description)

    active = catalog.activate("release-check")
    print("\nactivated instructions:\n", active.instructions)

    reference = catalog.read_resource(
        "release-check",
        "references/checklist.md",
    )
    print("\non-demand reference:\n", reference)


if __name__ == "__main__":
    main()
