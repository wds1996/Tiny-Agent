from tiny_agent.integrations.a2a import A2ASkillDescriptor, build_agent_card


def test_openai_agents_sdk_manager_and_handoff_objects_build_offline():
    from agents import Agent

    refund_agent = Agent(
        name="Refund specialist",
        instructions="Handle refund questions only.",
    )

    refund_tool = refund_agent.as_tool(
        tool_name="refund_expert",
        tool_description="Ask the refund specialist for a bounded subtask.",
    )
    assert refund_tool.name == "refund_expert"
    assert "refund specialist" in refund_tool.description.lower()

    manager = Agent(
        name="Support manager",
        instructions="Own the user conversation and call specialists when useful.",
        tools=[refund_tool],
    )
    assert len(manager.tools) == 1

    triage = Agent(
        name="Triage",
        instructions="Transfer refund conversations to the refund specialist.",
        handoffs=[refund_agent],
    )
    assert len(triage.handoffs) == 1


def test_a2a_1_agent_card_builder_uses_current_interface_shape():
    card = build_agent_card(
        name="Tiny Research Agent",
        description="Answers evidence-grounded research questions.",
        version="0.1.0",
        url="https://example.com/a2a",
        streaming=True,
        skills=[
            A2ASkillDescriptor(
                id="research",
                name="Research",
                description="Find and synthesize evidence.",
                tags=("research", "evidence"),
                examples=("Compare two approaches.",),
            )
        ],
    )

    assert card.name == "Tiny Research Agent"
    assert card.capabilities.streaming is True
    assert len(card.supported_interfaces) == 1
    assert card.supported_interfaces[0].protocol_binding == "JSONRPC"
    assert card.supported_interfaces[0].protocol_version == "1.0"
    assert card.skills[0].id == "research"


def test_a2a_message_and_request_objects_build_without_network():
    from a2a.types import Message, Part, Role, SendMessageRequest

    message = Message(
        role=Role.ROLE_USER,
        message_id="message-1",
        parts=[Part(text="Please summarize the report.")],
    )
    request = SendMessageRequest(message=message)

    assert request.message.message_id == "message-1"
    assert request.message.parts[0].text == "Please summarize the report."
