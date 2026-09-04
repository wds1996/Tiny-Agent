from __future__ import annotations

from typing import Any, TypedDict

from .tool import ToolRegistry
from .types import Model


class AgentGraphState(TypedDict):
    """Serializable state used by the Stage 03 LangGraph Agent."""

    messages: list[dict[str, Any]]
    pending_tool_calls: list[dict[str, Any]]
    final_answer: str | None
    error: str | None
    model_steps: int


def initial_agent_graph_state(
    user_input: str,
    *,
    system_prompt: str = "You are a helpful agent. Use tools when needed.",
) -> AgentGraphState:
    return {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ],
        "pending_tool_calls": [],
        "final_answer": None,
        "error": None,
        "model_steps": 0,
    }


def build_langgraph_agent(
    *,
    model: Model,
    tools: ToolRegistry,
    max_model_steps: int = 8,
):
    """Build a LangGraph version of Tiny-Agent's Stage 01 ReAct loop.

    LangGraph is an optional Stage 03 dependency, so the import happens inside
    this function. Installing the core Tiny-Agent package does not force a
    framework dependency on Stage 00/01 learners.

    The graph shape is intentionally small:

        START -> model -> tools -> model -> ...
                     \-> END

    The model node proposes actions. The tool node owns execution. A
    conditional edge reads explicit state to decide which node runs next.
    """

    if max_model_steps <= 0:
        raise ValueError("max_model_steps must be positive")

    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError(
            "LangGraph support is optional. Install Stage 03 dependencies with "
            '`pip install -e ".[stage03]"`.'
        ) from exc

    def model_node(state: AgentGraphState) -> dict[str, Any]:
        if state["model_steps"] >= max_model_steps:
            return {
                "error": f"Agent exceeded max_model_steps={max_model_steps}",
                "pending_tool_calls": [],
            }

        response = model.generate(state["messages"], tools.schemas())
        step = state["model_steps"] + 1

        if response.tool_calls:
            normalized_calls = [
                {
                    "id": call.id,
                    "name": call.name,
                    "arguments": dict(call.arguments),
                }
                for call in response.tool_calls
            ]
            assistant_message = {
                "role": "assistant",
                "tool_calls": normalized_calls,
            }
            return {
                "messages": [*state["messages"], assistant_message],
                "pending_tool_calls": normalized_calls,
                "final_answer": None,
                "error": None,
                "model_steps": step,
            }

        if response.final_answer is not None:
            answer = str(response.final_answer)
            return {
                "messages": [
                    *state["messages"],
                    {"role": "assistant", "content": answer},
                ],
                "pending_tool_calls": [],
                "final_answer": answer,
                "error": None,
                "model_steps": step,
            }

        return {
            "pending_tool_calls": [],
            "error": "Model produced neither tool calls nor a final answer",
            "model_steps": step,
        }

    def route_after_model(state: AgentGraphState) -> str:
        if state.get("error") is not None or state.get("final_answer") is not None:
            return "end"
        if state.get("pending_tool_calls"):
            return "tools"
        return "end"

    def tool_node(state: AgentGraphState) -> dict[str, Any]:
        messages = list(state["messages"])

        for call in state["pending_tool_calls"]:
            try:
                result = tools.execute(call["name"], call["arguments"])
                observation = str(result)
            except Exception as exc:
                # Stage 03 preserves the Stage 01 teaching behavior. Stage 09
                # will replace raw exception messages with governed error types.
                observation = f"ToolError[{type(exc).__name__}]: {exc}"

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "name": call["name"],
                    "content": observation,
                }
            )

        return {
            "messages": messages,
            "pending_tool_calls": [],
        }

    builder = StateGraph(AgentGraphState)
    builder.add_node("model", model_node)
    builder.add_node("tools", tool_node)
    builder.add_edge(START, "model")
    builder.add_conditional_edges(
        "model",
        route_after_model,
        {
            "tools": "tools",
            "end": END,
        },
    )
    builder.add_edge("tools", "model")

    return builder.compile()
