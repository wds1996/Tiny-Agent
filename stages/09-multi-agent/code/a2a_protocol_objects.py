"""Inspect A2A 1.0 discovery/message objects without starting a server."""

from a2a.types import Message, Part, Role, SendMessageRequest

from tiny_agent.integrations.a2a import A2ASkillDescriptor, build_agent_card


card = build_agent_card(
    name="Tiny Research Agent",
    description="An opaque remote Agent that offers evidence-grounded research.",
    version="0.1.0",
    url="https://example.com/a2a",
    streaming=True,
    skills=[
        A2ASkillDescriptor(
            id="research",
            name="Research",
            description="Find and synthesize evidence for a focused question.",
            tags=("research", "evidence"),
            examples=("Compare two Agent orchestration patterns.",),
        )
    ],
)

message = Message(
    role=Role.ROLE_USER,
    message_id="message-1",
    parts=[Part(text="Compare manager delegation with handoffs.")],
)
request = SendMessageRequest(message=message)

print("Agent Card:", card.name)
print("Protocol:", card.supported_interfaces[0].protocol_version)
print("Binding:", card.supported_interfaces[0].protocol_binding)
print("Skill:", card.skills[0].name)
print("Message:", request.message.parts[0].text)
print("A2A exposes the remote Agent's contract, not its private tools or memory.")
