from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping, Sequence

from ..multi_agent import (
    AgentInput,
    AgentSpec,
    ContextEnvelope,
    ContextPolicy,
    CoordinationBudget,
    CoordinationState,
    DelegationPolicy,
    TeamRuntime,
)
from .models import Evidence, ResearchModel


@dataclass(frozen=True, slots=True)
class ReviewOutcome:
    draft: str
    needs_revision: bool
    notes: tuple[str, ...]
    agent_calls: int
    model_calls: int
    revisions: int


class ResearchReviewTeam:
    """Bounded supervisor -> critic -> writer coordination using Stage 11 core."""

    def __init__(self, model: ResearchModel) -> None:
        self.model = model

        def supervisor_handler(payload: AgentInput) -> str:
            return payload.task

        def critic_handler(payload: AgentInput) -> str:
            shared = payload.context["shared"]
            critique = self.model.critique(
                question=str(shared["question"]),
                draft=str(shared["draft"]),
                evidence=shared["evidence"],
            )
            return json.dumps(
                {"needs_revision": critique.needs_revision, "notes": list(critique.notes)},
                ensure_ascii=False,
            )

        def writer_handler(payload: AgentInput) -> str:
            shared = payload.context["shared"]
            return self.model.synthesize(
                question=str(shared["question"]),
                evidence=shared["evidence"],
                remembered_context=shared["remembered_context"],
                previous_draft=str(shared["draft"]),
                critique_notes=shared["critique_notes"],
            )

        self.runtime = TeamRuntime(
            [
                AgentSpec("supervisor", "Owns review control and fan-in.", supervisor_handler),
                AgentSpec("critic", "Checks evidence grounding and overclaiming.", critic_handler),
                AgentSpec("writer", "Revises using bounded critique notes.", writer_handler),
            ],
            delegation_policy=DelegationPolicy(
                allowed_targets={"supervisor": frozenset({"critic", "writer"})}
            ),
            context_policy=ContextPolicy(
                allowed_shared_keys={
                    "critic": frozenset({"question", "draft", "evidence"}),
                    "writer": frozenset(
                        {"question", "draft", "evidence", "remembered_context", "critique_notes"}
                    ),
                }
            ),
        )

    async def review(
        self,
        *,
        question: str,
        draft: str,
        evidence: Sequence[Evidence],
        remembered_context: Mapping[str, Any],
    ) -> ReviewOutcome:
        state = CoordinationState(
            active_agent="supervisor",
            budget=CoordinationBudget(
                max_agent_calls=2,
                max_handoffs=1,
                max_parallel=2,
                max_same_handoff_edge=1,
            ),
        )
        base_context = ContextEnvelope(
            shared={
                "question": question,
                "draft": draft,
                "evidence": tuple(evidence),
                "remembered_context": dict(remembered_context),
            }
        )
        critic = await self.runtime.delegate(
            source="supervisor",
            target="critic",
            task="Review the draft against available evidence.",
            context=base_context,
            state=state,
        )
        if not critic.ok or critic.output is None:
            return ReviewOutcome(draft, False, ("critic_failed",), state.agent_calls, 1, 0)

        try:
            payload = json.loads(critic.output)
        except json.JSONDecodeError:
            return ReviewOutcome(draft, False, ("critic_invalid_output",), state.agent_calls, 1, 0)
        notes = tuple(str(item) for item in payload.get("notes", []))
        needs_revision = bool(payload.get("needs_revision"))
        if not needs_revision:
            return ReviewOutcome(draft, False, notes, state.agent_calls, 1, 0)

        revision_context = ContextEnvelope(
            shared={
                "question": question,
                "draft": draft,
                "evidence": tuple(evidence),
                "remembered_context": dict(remembered_context),
                "critique_notes": notes,
            }
        )
        writer = await self.runtime.delegate(
            source="supervisor",
            target="writer",
            task="Revise the draft using the critic notes.",
            context=revision_context,
            state=state,
        )
        if not writer.ok or writer.output is None:
            return ReviewOutcome(draft, True, (*notes, "writer_failed"), state.agent_calls, 2, 0)
        return ReviewOutcome(writer.output, True, notes, state.agent_calls, 2, 1)
