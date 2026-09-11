"""One report story, with deterministic drafting and explicit acceptance checks."""
from __future__ import annotations

import hashlib
from typing import Any

from ledger import StepResult, encode


STEP_NAMES = ("draft", "verify", "finalize")
OFFLINE_WORKFLOW = "support-report-offline-v2"
LIVE_WORKFLOW = "support-report-deepseek-v2"


def report_inputs() -> dict[str, Any]:
    return {
        "request": "Assess a pilot AI assistant for support staff; do not invent pilot results.",
        "sections": ["Background", "Risks", "Recommendation"],
        "facts": [
            "The proposed pilot includes 20 support staff.",
            "The assistant may suggest replies but may not issue refunds.",
            "No pilot results have been collected yet.",
        ],
    }


def draft_digest(draft: dict[str, str]) -> str:
    return hashlib.sha256(encode(draft).encode("utf-8")).hexdigest()


def validate_draft(inputs: dict, draft: Any) -> dict[str, str]:
    if not isinstance(draft, dict) or not draft or set(draft) - set(inputs["sections"]):
        raise ValueError("draft must be a non-empty object with known section names")
    if not all(isinstance(text, str) and text.strip() for text in draft.values()):
        raise ValueError("section contents must be non-empty text")
    return draft


def draft_result(inputs: dict, draft: Any) -> StepResult:
    return StepResult({
        "draft": validate_draft(inputs, draft),
        "review": None,  # A verdict about an earlier draft cannot approve a new draft.
        "reviewed_digest": None,
    })


def offline_draft(inputs: dict, progress: dict) -> StepResult:
    draft = {
        "Background": "A pilot assistant is proposed for 20 support staff; no results exist yet.",
        "Recommendation": "Start with suggested replies reviewed by staff; do not automate refunds.",
    }
    # Deliberately omit the risks section on the first round to expose real feedback.
    if progress.get("feedback"):
        draft["Risks"] = "Suggested replies may be inaccurate. Staff must check policy and facts."
    return draft_result(inputs, draft)


def review_result(inputs: dict, progress: dict, verdict: Any) -> StepResult:
    if (not isinstance(verdict, dict) or set(verdict) != {"ok", "feedback"}
            or type(verdict["ok"]) is not bool or not isinstance(verdict["feedback"], str)
            or (not verdict["ok"] and not verdict["feedback"].strip())):
        raise ValueError("review must contain boolean ok and usable text feedback")
    draft = validate_draft(inputs, progress.get("draft"))
    missing = [section for section in inputs["sections"] if section not in draft]
    if missing:
        verdict = {"ok": False, "feedback": "Missing required sections: " + ", ".join(missing)}
    data = {"review": verdict, "reviewed_digest": draft_digest(draft),
            "feedback": verdict["feedback"]}
    # The application chooses the restart destination; the model never supplies it.
    return StepResult(data, restart_step=None if verdict["ok"] else 0)


def offline_verify(inputs: dict, progress: dict) -> StepResult:
    # This checks only the teaching acceptance rule, not arbitrary factual accuracy.
    return review_result(inputs, progress, {"ok": True, "feedback": "Required sections present."})


def finalize(inputs: dict, progress: dict) -> StepResult:
    draft = validate_draft(inputs, progress.get("draft"))
    review = progress.get("review")
    if (not isinstance(review, dict) or review.get("ok") is not True
            or progress.get("reviewed_digest") != draft_digest(draft)
            or any(section not in draft for section in inputs["sections"])):
        raise ValueError("only the current, accepted draft may be finalized")
    text = "# Support assistant pilot\n\n" + "\n\n".join(
        f"## {section}\n\n{draft[section]}" for section in inputs["sections"]
    ) + "\n"
    return StepResult({"finalized": True}, artifact=text)


def offline_steps():
    return (offline_draft, offline_verify, finalize)
