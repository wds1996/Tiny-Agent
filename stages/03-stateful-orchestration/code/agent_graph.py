"""The weather model/tool loop expressed as state updates and two graph nodes."""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import asdict, dataclass
import json
from operator import add
from typing import Annotated, Any, Callable, Protocol

from state_graph import END, START, MiniStateGraph
from workflow import NOTICES, TEACHING_WEATHER, fahrenheit, finite_number, read_weather


@dataclass(frozen=True)
class ToolCall:
    call_id: str
    name: str
    arguments: dict[str, Any]

    def __post_init__(self) -> None:
        if any(not isinstance(value, str) or not value.strip() for value in (self.call_id, self.name)):
            raise ValueError("Call ID and name must be nonempty strings")
        if not isinstance(self.arguments, dict):
            raise ValueError("Call arguments must be an object")
        json.dumps(self.arguments, allow_nan=False)


@dataclass(frozen=True)
class ModelTurn:
    final_answer: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    provider_items: tuple[dict[str, Any], ...] = ()

    def __post_init__(self) -> None:
        if type(self.tool_calls) is not tuple or any(not isinstance(c, ToolCall) for c in self.tool_calls):
            raise ValueError("tool_calls must be a tuple of ToolCall values")
        if (self.final_answer is not None) == bool(self.tool_calls):
            raise ValueError("Return a final answer or tool calls, not both or neither")
        if self.final_answer is not None and (not isinstance(self.final_answer, str) or not self.final_answer.strip()):
            raise ValueError("The final answer must be nonempty text")
        ids = [call.call_id for call in self.tool_calls]
        if len(set(ids)) != len(ids):
            raise ValueError("Call IDs must be unique within a turn")
        if type(self.provider_items) is not tuple or any(not isinstance(i, dict) for i in self.provider_items):
            raise ValueError("Provider items must be a tuple of dictionaries")


class Model(Protocol):
    def generate(self, messages: list[dict[str, Any]]) -> ModelTurn: ...


def request_for(city: str, task: str, language: str) -> str:
    if city not in TEACHING_WEATHER or task not in {"greet", "weather", "convert"} or language not in NOTICES:
        raise ValueError("Unsupported task options")
    if task == "greet":
        return "你好。" if language == "zh-CN" else "Hello."
    if language == "zh-CN":
        suffix = "再调用换算工具给出华氏度。" if task == "convert" else "只需要摄氏度，不要换算。"
        return f"请读取 {city} 的教学天气，告诉我温度和天气状况。{suffix}请用中文回答，并说明不是实时天气。"
    suffix = "Then use the conversion tool for Fahrenheit." if task == "convert" else "Celsius only; do not convert."
    return f"Read {city}'s teaching temperature and condition. {suffix} Answer in English and label it as not live weather."


def initial_state(question: str) -> dict[str, Any]:
    if not isinstance(question, str) or not question.strip():
        raise ValueError("question must be nonempty text")
    return {"messages": [{"role": "user", "content": question}], "pending_tool_calls": [],
            "final_answer": None, "error": None, "model_steps": 0, "tool_calls": 0,
            "events": [], "diagnostic_tag": "local teaching run"}


def tool_definitions() -> list[dict[str, Any]]:
    return [
        {"type": "function", "name": "get_teaching_weather",
         "description": "Read the fixed teaching temperature and condition for Tokyo or Paris, not live weather.",
         "parameters": {"type": "object", "properties": {"city": {"type": "string", "enum": ["Tokyo", "Paris"]}},
                        "required": ["city"], "additionalProperties": False}, "strict": True},
        {"type": "function", "name": "celsius_to_fahrenheit",
         "description": "Convert the Celsius value returned by the weather tool to Fahrenheit.",
         "parameters": {"type": "object", "properties": {"temperature_c": {"type": "number"}},
                        "required": ["temperature_c"], "additionalProperties": False}, "strict": True},
    ]


def validate_call(call: ToolCall) -> None:
    ToolCall(call.call_id, call.name, call.arguments)
    if call.name == "get_teaching_weather":
        if set(call.arguments) != {"city"} or call.arguments["city"] not in TEACHING_WEATHER:
            raise ValueError("Weather tool requires one supported city")
    elif call.name == "celsius_to_fahrenheit":
        if set(call.arguments) != {"temperature_c"}:
            raise ValueError("Conversion requires temperature_c")
        finite_number(call.arguments["temperature_c"])
    else:
        raise ValueError("Unknown tool")


def execute_tool(call: ToolCall) -> dict[str, Any]:
    validate_call(call)
    if call.name == "get_teaching_weather":
        return read_weather(call.arguments["city"])
    return {"temperature_f": fahrenheit(call.arguments["temperature_c"])}


def make_nodes(model: Model, *, max_model_steps: int = 6, max_tool_calls: int = 6,
               executor: Callable[[ToolCall], dict[str, Any]] = execute_tool):
    if type(max_model_steps) is not int or max_model_steps < 1:
        raise ValueError("max_model_steps must be a positive integer")
    if type(max_tool_calls) is not int or max_tool_calls < 0:
        raise ValueError("max_tool_calls must be a nonnegative integer")

    def model_node(state: dict[str, Any]) -> dict[str, Any]:
        if state["model_steps"] >= max_model_steps:
            return {"error": "model_budget_exhausted", "pending_tool_calls": [], "events": ["model budget exhausted"]}
        count = state["model_steps"] + 1
        try:
            turn = model.generate(deepcopy(state["messages"]))
            if not isinstance(turn, ModelTurn):
                raise ValueError("Expected ModelTurn")
            turn = ModelTurn(turn.final_answer, turn.tool_calls, turn.provider_items)
            seen = {call["call_id"] for msg in state["messages"] for call in msg.get("tool_calls", [])}
            if any(call.call_id in seen for call in turn.tool_calls):
                raise ValueError("Repeated call ID")
        except Exception as exc:
            return {"model_steps": count, "error": f"model_failed:{type(exc).__name__}",
                    "pending_tool_calls": [], "events": ["model turn failed"]}
        message = {"role": "assistant", "content": turn.final_answer or "",
                   "tool_calls": [asdict(call) for call in turn.tool_calls],
                   "provider_items": deepcopy(list(turn.provider_items))}
        return {"messages": [message], "pending_tool_calls": deepcopy(list(turn.tool_calls)),
                "final_answer": turn.final_answer, "model_steps": count,
                "events": ["model proposed tools" if turn.tool_calls else "model answered"]}

    def tool_node(state: dict[str, Any]) -> dict[str, Any]:
        calls = state["pending_tool_calls"]
        if len(calls) > max_tool_calls - state["tool_calls"]:
            return {"pending_tool_calls": [], "error": "tool_budget_exhausted", "events": ["tool budget exhausted"]}
        try:
            for call in calls:
                validate_call(call)
        except Exception as exc:
            return {"pending_tool_calls": [], "error": f"invalid_tool_request:{type(exc).__name__}",
                    "events": ["tool batch rejected before execution"]}
        observations: list[dict[str, Any]] = []
        used = state["tool_calls"]
        error = None
        for call in calls:
            used += 1
            try:
                result = executor(deepcopy(call))
                if not isinstance(result, dict):
                    raise ValueError("Tool output must be an object")
                content = json.dumps(result, ensure_ascii=False, allow_nan=False)
            except Exception as exc:
                error = f"tool_failed:{type(exc).__name__}"
                content = json.dumps({"error": error})
            observations.append({"role": "tool", "tool_call_id": call.call_id,
                                 "name": call.name, "content": content})
            if error:
                break
        return {"messages": observations, "pending_tool_calls": [], "tool_calls": used,
                "error": error, "events": ["tools failed" if error else "tools completed"]}

    def route_after_model(state: dict[str, Any]) -> str:
        if state["error"] is not None:
            return "end"
        return "tools" if state["pending_tool_calls"] else "end"

    def route_after_tools(state: dict[str, Any]) -> str:
        return "end" if state["error"] is not None else "model"

    return model_node, tool_node, route_after_model, route_after_tools


def build_agent_graph(*, model: Model, engine: str = "langgraph", **limits: Any):
    model_node, tool_node, after_model, after_tools = make_nodes(model, **limits)
    if engine == "mini":
        builder = MiniStateGraph(reducers={"messages": add, "events": add})
    elif engine == "langgraph":
        from typing_extensions import TypedDict
        from langgraph_workflow import state_graph_type

        class AgentState(TypedDict):
            messages: Annotated[list[dict[str, Any]], add]
            pending_tool_calls: list[ToolCall]
            final_answer: str | None
            error: str | None
            model_steps: int
            tool_calls: int
            events: Annotated[list[str], add]
            diagnostic_tag: str

        builder = state_graph_type()(AgentState)
    else:
        raise ValueError("engine must be mini or langgraph")
    builder.add_node("model", model_node)
    builder.add_node("tools", tool_node)
    builder.add_edge(START, "model")
    builder.add_conditional_edges("model", after_model, {"tools": "tools", "end": END})
    builder.add_conditional_edges("tools", after_tools, {"model": "model", "end": END})
    return builder.compile()


class ScriptedModel:
    """A scenario-specific test double, not a natural-language interpreter."""
    def __init__(self, city: str = "Tokyo", task: str = "convert", language: str = "zh-CN") -> None:
        request_for(city, task, language)
        self.city, self.task, self.language = city, task, language

    def generate(self, messages: list[dict[str, Any]]) -> ModelTurn:
        if self.task == "greet":
            return ModelTurn(final_answer="你好。" if self.language == "zh-CN" else "Hello.")
        observations = {msg["name"]: json.loads(msg["content"]) for msg in messages if msg["role"] == "tool"}
        if "get_teaching_weather" not in observations:
            return ModelTurn(tool_calls=(ToolCall("weather-1", "get_teaching_weather", {"city": self.city}),))
        weather = observations["get_teaching_weather"]
        if self.task == "convert" and "celsius_to_fahrenheit" not in observations:
            return ModelTurn(tool_calls=(ToolCall("convert-1", "celsius_to_fahrenheit",
                                                  {"temperature_c": weather["temperature_c"]}),))
        units = f"{weather['temperature_c']:.1f}°C"
        if self.task == "convert":
            units += f" / {observations['celsius_to_fahrenheit']['temperature_f']:.1f}°F"
        return ModelTurn(final_answer=f"{weather['city']}: {units}, {weather['condition']}. {NOTICES[self.language]}")


def parse_agent_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the teaching-weather model/tool graph.")
    parser.add_argument("--city", choices=tuple(TEACHING_WEATHER), default="Tokyo")
    parser.add_argument("--task", choices=("greet", "weather", "convert"), default="convert")
    parser.add_argument("--language", choices=tuple(NOTICES), default="zh-CN")
    parser.add_argument("--engine", choices=("mini", "langgraph"), default="langgraph")
    parser.add_argument("--max-model-steps", type=int, default=6)
    parser.add_argument("--max-tool-calls", type=int, default=6)
    parser.add_argument("--show-updates", action="store_true")
    return parser.parse_args()


def run_demo(model: Model, args: argparse.Namespace) -> dict[str, Any]:
    graph = build_agent_graph(model=model, engine=args.engine,
                              max_model_steps=args.max_model_steps, max_tool_calls=args.max_tool_calls)
    state = initial_state(request_for(args.city, args.task, args.language))
    limit = 2 * args.max_model_steps + 4
    if args.engine == "mini":
        result = graph.invoke(state, max_steps=limit)
        if args.show_updates:
            for step in result.steps:
                print(step.node, "updated:", sorted(step.update))
        final = result.state
    else:
        from langgraph_workflow import run_stream
        final = run_stream(graph, state, show_updates=args.show_updates, recursion_limit=limit)
    print("model calls:", final["model_steps"], "tool attempts:", final["tool_calls"])
    print("roles:", [message["role"] for message in final["messages"]])
    print("pending:", len(final["pending_tool_calls"]), "error:", final["error"])
    print(final["final_answer"] or "No final answer.")
    return final
