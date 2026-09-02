"""Build both OpenAI Agents SDK multi-Agent patterns without calling a model.

Install with:
    python -m pip install -e ".[stage09]"
"""

from agents import Agent


refund_agent = Agent(
    name="Refund specialist",
    instructions="Handle refund questions only.",
)

# Pattern 1: specialist stays behind the manager.
refund_tool = refund_agent.as_tool(
    tool_name="refund_expert",
    tool_description="Ask the refund specialist for a bounded subtask.",
)
manager = Agent(
    name="Support manager",
    instructions="Keep ownership of the user conversation and use specialists as tools.",
    tools=[refund_tool],
)

# Pattern 2: specialist takes over the conversation.
triage = Agent(
    name="Triage",
    instructions="Transfer refund conversations to the refund specialist.",
    handoffs=[refund_agent],
)

print("Manager pattern tool:", manager.tools[0].name)
print("Handoff targets:", len(triage.handoffs))
print("No API call was made: this example inspects orchestration structure only.")
