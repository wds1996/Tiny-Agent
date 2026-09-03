from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
ZH_SUFFIX = ".zh-CN.md"
LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


def _zh_counterpart(path: Path) -> Path:
    assert path.suffix == ".md"
    return path.with_name(f"{path.stem}.zh-CN.md")


def _english_counterpart(path: Path) -> Path:
    assert path.name.endswith(ZH_SUFFIX)
    return path.with_name(path.name[: -len(ZH_SUFFIX)] + ".md")


def _managed_english_docs() -> list[Path]:
    docs: set[Path] = {
        ROOT / "README.md",
        ROOT / "CONTRIBUTING.md",
    }

    docs.update(
        path
        for path in (ROOT / "docs").glob("*.md")
        if not path.name.endswith(ZH_SUFFIX)
    )

    for stage in (ROOT / "stages").iterdir():
        if not stage.is_dir():
            continue

        readme = stage / "README.md"
        if readme.exists():
            docs.add(readme)

        for section in ("theory", "exercises", "advanced"):
            section_dir = stage / section
            if not section_dir.exists():
                continue
            docs.update(
                path
                for path in section_dir.rglob("*.md")
                if not path.name.endswith(ZH_SUFFIX)
            )

    return sorted(docs)


def _managed_chinese_docs() -> list[Path]:
    docs: set[Path] = {
        ROOT / "README.zh-CN.md",
        ROOT / "CONTRIBUTING.zh-CN.md",
    }
    docs.update((ROOT / "docs").glob(f"*{ZH_SUFFIX}"))
    docs.update((ROOT / "stages").rglob(f"*{ZH_SUFFIX}"))
    return sorted(path for path in docs if path.exists())


def test_every_managed_english_learning_doc_has_chinese_counterpart() -> None:
    missing = [
        path.relative_to(ROOT)
        for path in _managed_english_docs()
        if not _zh_counterpart(path).exists()
    ]
    assert not missing, "Missing Chinese counterparts:\n" + "\n".join(map(str, missing))


def test_every_chinese_doc_has_english_source() -> None:
    orphaned = [
        path.relative_to(ROOT)
        for path in _managed_chinese_docs()
        if not _english_counterpart(path).exists()
    ]
    assert not orphaned, "Orphaned Chinese docs:\n" + "\n".join(map(str, orphaned))


def _iter_local_links(markdown: Path):
    in_fence = False
    for line in markdown.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        for match in LINK_RE.finditer(line):
            raw = match.group(1).strip()
            if not raw:
                continue
            # Markdown may use <path> or append an optional title after whitespace.
            if raw.startswith("<") and ">" in raw:
                raw = raw[1 : raw.index(">")]
            else:
                raw = raw.split()[0]

            if raw.startswith(("http://", "https://", "mailto:", "tel:", "#")):
                continue

            target = unquote(raw.split("#", 1)[0].split("?", 1)[0])
            if target:
                yield target


def test_chinese_docs_have_no_broken_local_links() -> None:
    broken: list[str] = []
    root_resolved = ROOT.resolve()

    for doc in _managed_chinese_docs():
        for target in _iter_local_links(doc):
            candidate = (
                ROOT / target.lstrip("/")
                if target.startswith("/")
                else doc.parent / target
            ).resolve()

            try:
                candidate.relative_to(root_resolved)
            except ValueError:
                # A relative link intentionally leaving the repository is not a
                # repository-integrity concern for this test.
                continue

            if not candidate.exists():
                broken.append(f"{doc.relative_to(ROOT)} -> {target}")

    assert not broken, "Broken local links in Chinese docs:\n" + "\n".join(broken)
