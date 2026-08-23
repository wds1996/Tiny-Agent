from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


TrustLevel = Literal["trusted_policy", "user_input", "external_untrusted"]


@dataclass(frozen=True, slots=True)
class ContentEnvelope:
    """Carry source/trust metadata separately from the content itself."""

    source: str
    text: str
    trust_level: TrustLevel = "external_untrusted"

    def __post_init__(self) -> None:
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("source must be a non-empty string")
        if not isinstance(self.text, str):
            raise ValueError("text must be a string")
        if self.trust_level not in {"trusted_policy", "user_input", "external_untrusted"}:
            raise ValueError("invalid trust_level")

    def render_for_model(self) -> str:
        """Label external data without pretending labeling alone solves injection."""

        if self.trust_level != "external_untrusted":
            return self.text
        return (
            f"<external_untrusted source={self.source!r}>\n"
            f"{self.text}\n"
            "</external_untrusted>"
        )


@dataclass(frozen=True, slots=True)
class InjectionSignal:
    suspicious: bool
    matched_patterns: tuple[str, ...]


_INSTRUCTION_LIKE_PATTERNS = (
    "ignore previous",
    "ignore all previous",
    "system message",
    "developer message",
    "reveal your prompt",
    "send all secrets",
    "exfiltrate",
    "bypass approval",
)


def detect_instruction_like_content(text: str) -> InjectionSignal:
    """Tiny heuristic for telemetry/demos, never an authorization boundary.

    Prompt injection is semantic and adversarial. Regex/substring detection is
    bypassable, so callers must not use this function as the sole decision for
    privileged tool access.
    """

    if not isinstance(text, str):
        raise ValueError("text must be a string")
    lowered = text.casefold()
    matches = tuple(pattern for pattern in _INSTRUCTION_LIKE_PATTERNS if pattern in lowered)
    return InjectionSignal(bool(matches), matches)
