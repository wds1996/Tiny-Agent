"""Create the MkDocs source tree from the repository's canonical lessons."""

from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / ".site-source"
SITE_URL = "https://wds1996.github.io/Tiny-Agent/"


def copy_tree(source: Path, destination: Path) -> None:
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".venv", "venv"),
    )


def page_url(path: Path) -> str:
    relative_path = path.relative_to(SOURCE)
    if relative_path.name == "README.md":
        relative_path = relative_path.parent
    else:
        relative_path = relative_path.with_suffix("")
    relative = relative_path.as_posix()
    return SITE_URL if relative in (".", "index") else f"{SITE_URL}{relative}/"


def main() -> None:
    if SOURCE.exists():
        shutil.rmtree(SOURCE)
    SOURCE.mkdir()

    copy_tree(ROOT / "assets", SOURCE / "assets")
    copy_tree(ROOT / "stages", SOURCE / "stages")

    english_home = (ROOT / "README.md").read_text(encoding="utf-8")
    english_home = english_home.replace("](README.zh-CN.md)", "](zh/index.md)")
    (SOURCE / "index.md").write_text(english_home, encoding="utf-8")

    chinese_home = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
    chinese_home = chinese_home.replace("](stages/", "](../stages/")
    chinese_home = chinese_home.replace("](README.md)", "](../index.md)")
    chinese_home = chinese_home.replace("assets/", "../assets/")
    chinese_directory = SOURCE / "zh"
    chinese_directory.mkdir()
    (chinese_directory / "index.md").write_text(chinese_home, encoding="utf-8")

    markdown_pages = [SOURCE / "index.md", SOURCE / "zh" / "index.md"]
    markdown_pages.extend((SOURCE / "stages").glob("*/README*.md"))
    urls = "\n".join(
        f"  <url><loc>{page_url(page)}</loc></url>" for page in sorted(markdown_pages)
    )
    (SOURCE / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}\n"
        "</urlset>\n",
        encoding="utf-8",
    )
    (SOURCE / "robots.txt").write_text(
        "User-agent: *\nAllow: /\n"
        f"Sitemap: {SITE_URL}sitemap.xml\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
