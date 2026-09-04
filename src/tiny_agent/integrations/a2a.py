from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True, slots=True)
class A2ASkillDescriptor:
    id: str
    name: str
    description: str
    tags: tuple[str, ...] = ()
    examples: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.id.strip() or not self.name.strip() or not self.description.strip():
            raise ValueError("A2A skill id, name, and description must be non-empty")


def build_agent_card(
    *,
    name: str,
    description: str,
    version: str,
    url: str,
    skills: Sequence[A2ASkillDescriptor],
    protocol_binding: str = "JSONRPC",
    protocol_version: str = "1.0",
    streaming: bool = False,
):
    """Build an A2A 1.0 AgentCard using the optional official Python SDK.

    The import stays inside the function so Tiny-Agent's lightweight core does
    not require the A2A SDK unless the Stage 11 interoperability extra is used.
    """

    if not name.strip() or not description.strip() or not version.strip() or not url.strip():
        raise ValueError("Agent Card identity fields must be non-empty")
    if not skills:
        raise ValueError("Agent Card should advertise at least one skill")

    try:
        from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill
    except ImportError as exc:  # pragma: no cover - exercised only without optional extra
        raise RuntimeError(
            "A2A integration requires the Stage 11 optional dependency: "
            "python -m pip install -e '.[stage11]'"
        ) from exc

    return AgentCard(
        name=name,
        description=description,
        version=version,
        supported_interfaces=[
            AgentInterface(
                url=url,
                protocol_binding=protocol_binding,
                protocol_version=protocol_version,
            )
        ],
        capabilities=AgentCapabilities(streaming=streaming),
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        skills=[
            AgentSkill(
                id=skill.id,
                name=skill.name,
                description=skill.description,
                tags=list(skill.tags),
                examples=list(skill.examples),
                input_modes=["text/plain"],
                output_modes=["text/plain"],
            )
            for skill in skills
        ],
    )
