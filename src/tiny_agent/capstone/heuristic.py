from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .models import Critique, Evidence, ResearchPlan, ResearchModel

_SPLIT_RE = re.compile(r"\s+(?:and|vs\.?|versus|以及|与|和)\s+", re.IGNORECASE)


class HeuristicResearchModel(ResearchModel):
    """Deterministic offline model for inspecting the full Agent path without keys."""

    def plan(self, *, question: str, remembered_context: Mapping[str, Any]) -> ResearchPlan:
        pieces = [part.strip(" ?。") for part in _SPLIT_RE.split(question) if part.strip()]
        subquestions = (
            (question.strip(),)
            if len(pieces) <= 1
            else tuple(f"What evidence is available about {piece}?" for piece in pieces[:3])
        )
        return ResearchPlan(
            subquestions=subquestions,
            use_external_search=True,
            reason="Offline heuristic: retrieve local evidence and optionally discover scholarly metadata.",
        )

    def synthesize(
        self,
        *,
        question: str,
        evidence: Sequence[Evidence],
        remembered_context: Mapping[str, Any],
        previous_draft: str | None = None,
        critique_notes: Sequence[str] = (),
    ) -> str:
        style = str(remembered_context.get("preferred_style") or "concise")
        local = [item for item in evidence if item.kind == "local_fulltext"]
        metadata = [item for item in evidence if item.kind == "scholarly_metadata"]
        lines = [f"Research question: {question}", ""]
        if local:
            lines.append("Evidence-grounded findings:")
            for item in local[:5]:
                snippet = " ".join(item.text.split())
                if len(snippet) > 220:
                    snippet = snippet[:220].rstrip() + "…"
                lines.append(f"- {snippet} {item.citation}")
        else:
            lines.append(
                "No local full-text evidence was retrieved, so I will not infer paper findings from bibliographic metadata alone."
            )
        if metadata:
            lines.extend(["", "Related works discovered from scholarly metadata:"])
            lines.extend(f"- {item.title} {item.citation}" for item in metadata[:4])
        if critique_notes:
            lines.extend(["", "Revision notes addressed:"])
            lines.extend(f"- {note}" for note in critique_notes)
        lines.extend(["", f"Answer style: {style}.", "Citations refer to the returned evidence inventory."])
        return "\n".join(lines)

    def critique(self, *, question: str, draft: str, evidence: Sequence[Evidence]) -> Critique:
        notes: list[str] = []
        local = [item for item in evidence if item.kind == "local_fulltext"]
        if not local:
            notes.append("No local full-text evidence supports substantive claims.")
        if evidence and not any(item.citation in draft for item in evidence):
            notes.append("Draft contains no explicit evidence citation labels.")
        return Critique(needs_revision=bool(notes), notes=tuple(notes))
