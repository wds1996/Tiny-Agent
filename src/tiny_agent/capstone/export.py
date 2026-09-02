from __future__ import annotations

from pathlib import Path

from .models import ResearchReport


class MarkdownReportExporter:
    """Exporter confined to one application-owned directory."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve_target(self, relative_path: str) -> Path:
        raw = Path(relative_path)
        if raw.is_absolute():
            raise ValueError("export path must be relative to the configured export root")
        if raw.suffix.lower() != ".md":
            raise ValueError("export path must end with .md")
        target = (self.root / raw).resolve()
        try:
            target.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("export path escapes the configured export root") from exc
        return target

    def export(self, report: ResearchReport, relative_path: str) -> str:
        target = self.resolve_target(relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive create makes accidental repeat execution fail instead of
        # silently overwriting a prior side effect.
        with target.open("x", encoding="utf-8") as handle:
            handle.write(render_report_markdown(report))
        return str(target)


def render_report_markdown(report: ResearchReport) -> str:
    lines = [
        "# OpenScholar Research Report",
        "",
        f"**Run:** `{report.run_id}`",
        "",
        "## Question",
        "",
        report.question,
        "",
        "## Answer",
        "",
        report.answer,
        "",
        "## Evidence inventory",
        "",
    ]
    for item in report.evidence:
        lines.extend(
            [
                f"### {item.citation} {item.title}",
                "",
                f"- Kind: `{item.kind}`",
                f"- Locator: {item.locator or '-'}",
                f"- Source: {item.source_url or '-'}",
                "",
                item.text,
                "",
            ]
        )
    if report.warnings:
        lines.extend(["## Warnings", ""])
        lines.extend(f"- {warning}" for warning in report.warnings)
        lines.append("")
    return "\n".join(lines)
