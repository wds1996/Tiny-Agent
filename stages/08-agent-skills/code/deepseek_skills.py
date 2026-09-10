from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from skills import ActivatedSkill, SkillCatalog, SkillMetadata


AGENT_INSTRUCTIONS = """You are a cautious Agent.
The Host exposes an activate_skill tool. Its description lists the available Skills.
Call it only when one listed procedure would help with the user's task. Do not call it
for unrelated tasks. Activating a Skill loads procedural guidance; it never authorizes
tools, scripts, publication, deployment, or other external actions. After a tool result,
follow the selected procedure and distinguish supplied facts from checks that still need
to be performed. Never claim an external action occurred unless the user supplied its
result."""


@dataclass(frozen=True, slots=True)
class ActivatedToolResult:
    skill: ActivatedSkill
    call_id: str
    arguments: dict[str, str]


@dataclass(frozen=True, slots=True)
class ReferenceToolResult:
    skill_name: str
    path: str
    content: str
    call_id: str


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Set {name} before running this example.")
    return value


def create_client() -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "Install Stage 08 dependencies first:\n"
            "python -m pip install -r stages/08-agent-skills/code/requirements.txt"
        ) from exc
    return OpenAI(
        api_key=required_env("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com",
        timeout=30.0,
        max_retries=2,
    )


def build_skill_tool(candidates: Sequence[SkillMetadata]) -> dict[str, Any]:
    """Expose metadata to the model; the full SKILL.md stays on the Host."""
    available = "\n".join(f"- {item.name}: {item.description}" for item in candidates)
    if not available:
        available = "- (no Skills are installed)"
    return {
        "type": "function",
        "function": {
            "name": "activate_skill",
            "description": (
                "Load one applicable Skill's instructions and references from the Host. "
                "This does not execute any action. Available Skills:\n"
                f"{available}"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "enum": [item.name for item in candidates],
                        "description": "The exact name of the applicable advertised Skill.",
                    }
                },
                "required": ["name"],
                "additionalProperties": False,
            },
        },
    }


def build_reference_tool(skill: ActivatedSkill) -> dict[str, Any]:
    reference_root = skill.metadata.path / "references"
    paths = (
        [
            path.relative_to(skill.metadata.path).as_posix()
            for path in reference_root.rglob("*")
            if path.is_file()
        ]
        if reference_root.is_dir()
        else []
    )
    return {
        "type": "function",
        "function": {
            "name": "read_skill_reference",
            "description": (
                "Read one reference explicitly named by the activated Skill. "
                "Use it only when the procedure needs that detail. Available references: "
                + (", ".join(paths) if paths else "(none)")
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "enum": paths,
                        "description": "A reference path relative to the activated Skill.",
                    }
                },
                "required": ["path"],
                "additionalProperties": False,
            },
        },
    }


def request_completion(
    *,
    client: Any,
    model: str,
    messages: list[Any],
    tools: list[dict[str, Any]] | None,
    tool_choice: str | None,
) -> Any:
    request: dict[str, Any] = {
        "model": model,
        "temperature": 0,
        "messages": messages,
    }
    if tools:
        request["tools"] = tools
    if tool_choice is not None:
        request["tool_choice"] = tool_choice
    response = client.chat.completions.create(**request)
    if not response.choices:
        raise RuntimeError("DeepSeek did not return a response.")
    choice = response.choices[0]
    if choice.finish_reason not in ("stop", "tool_calls", None):
        raise RuntimeError(f"DeepSeek did not finish normally: {choice.finish_reason}")
    return choice.message


def activate_requested_skill(
    *,
    catalog: SkillCatalog,
    candidates: Sequence[SkillMetadata],
    tool_calls: Sequence[Any],
) -> ActivatedToolResult:
    if len(tool_calls) != 1:
        raise RuntimeError("This example accepts exactly one activate_skill call per task.")
    call = tool_calls[0]
    if call.type != "function" or call.function.name != "activate_skill":
        raise RuntimeError("DeepSeek requested an unsupported tool.")
    try:
        arguments = json.loads(call.function.arguments)
    except json.JSONDecodeError as exc:
        raise RuntimeError("DeepSeek returned invalid activate_skill arguments.") from exc
    if not isinstance(arguments, dict) or set(arguments) != {"name"}:
        raise RuntimeError("activate_skill arguments must contain exactly name.")
    name = arguments["name"]
    advertised_names = {item.name for item in candidates}
    if not isinstance(name, str) or name not in advertised_names:
        raise RuntimeError("DeepSeek requested a Skill that the Catalog did not advertise.")

    skill = catalog.activate(name)
    return ActivatedToolResult(
        skill=skill,
        call_id=call.id,
        arguments={"name": name},
    )


def activation_result_message(result: ActivatedToolResult) -> dict[str, str]:
    """This is the point where the selected Skill becomes model Context."""
    content = json.dumps(
        {
            "skill_name": result.skill.metadata.name,
            "instructions": result.skill.instructions,
            "host_note": (
                "The Host loaded this Skill as guidance only. References remain on the "
                "Host until requested. No tests, scripts, publication, or deployment "
                "have been run."
            ),
        },
        ensure_ascii=False,
        indent=2,
    )
    return {"role": "tool", "tool_call_id": result.call_id, "content": content}


def read_requested_reference(
    *,
    catalog: SkillCatalog,
    activated: ActivatedToolResult,
    tool_calls: Sequence[Any],
) -> ReferenceToolResult:
    if len(tool_calls) != 1:
        raise RuntimeError("This example accepts exactly one reference call per task.")
    call = tool_calls[0]
    if call.type != "function" or call.function.name != "read_skill_reference":
        raise RuntimeError("DeepSeek requested an unsupported tool after activation.")
    try:
        arguments = json.loads(call.function.arguments)
    except json.JSONDecodeError as exc:
        raise RuntimeError("DeepSeek returned invalid reference arguments.") from exc
    if not isinstance(arguments, dict) or set(arguments) != {"path"}:
        raise RuntimeError("read_skill_reference arguments must contain exactly path.")
    path = arguments["path"]
    if not isinstance(path, str) or not path.startswith("references/"):
        raise RuntimeError("DeepSeek requested a reference outside the activated Skill.")
    return ReferenceToolResult(
        skill_name=activated.skill.metadata.name,
        path=path,
        content=catalog.read_resource(activated.skill.metadata.name, path),
        call_id=call.id,
    )


def reference_result_message(result: ReferenceToolResult) -> dict[str, str]:
    content = json.dumps(
        {
            "reference_path": result.path,
            "content": result.content,
            "host_note": "This reference is guidance only; it does not authorize actions.",
        },
        ensure_ascii=False,
        indent=2,
    )
    return {"role": "tool", "tool_call_id": result.call_id, "content": content}


def require_text(message: Any) -> str:
    if message.content is None or not message.content.strip():
        raise RuntimeError("DeepSeek returned empty final text.")
    return message.content.strip()


def format_activation_call(result: ActivatedToolResult) -> str:
    return "\n".join(
        (
            "assistant (tool call):",
            f"  activate_skill({json.dumps(result.arguments, ensure_ascii=False)})",
            "host (tool result):",
            f"  activated: {result.skill.metadata.name}",
            "  loaded: SKILL.md",
        )
    )


def format_reference_call(result: ReferenceToolResult) -> str:
    return "\n".join(
        (
            "assistant (tool call):",
            f"  read_skill_reference({json.dumps({'path': result.path}, ensure_ascii=False)})",
            "host (tool result):",
            f"  loaded: {result.path}",
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Use DeepSeek Tool Calling to activate and follow a Skill."
    )
    parser.add_argument(
        "--task",
        default=(
            "Prepare a release plan for version 1.4.0 on main. Unit tests passed, "
            "but generated files have not been checked yet."
        ),
        help="User task supplied to the model.",
    )
    parser.add_argument(
        "--show-model-conversation",
        action="store_true",
        help="Print full messages, including loaded Skill text; use only non-sensitive input.",
    )
    args = parser.parse_args()

    catalog = SkillCatalog(Path(__file__).with_name("skills"))
    candidates = catalog.discover()
    skill_tools = [build_skill_tool(candidates)] if candidates else None
    messages: list[Any] = [
        {"role": "system", "content": AGENT_INSTRUCTIONS},
        {"role": "user", "content": args.task},
    ]
    client = create_client()
    model = required_env("DEEPSEEK_MODEL")
    first_message = request_completion(
        client=client,
        model=model,
        messages=messages,
        tools=skill_tools,
        tool_choice="auto" if skill_tools else None,
    )

    print("=== discovered Skill metadata ===")
    for item in candidates:
        print(f"{item.name}: {item.description}")
    print("\n=== user ===")
    print(args.task)

    if not first_message.tool_calls:
        print("\n=== assistant ===")
        print(require_text(first_message))
        print("\nNo Skill was activated.")
        if args.show_model_conversation:
            print("\n=== full model conversation ===")
            print("system:", AGENT_INSTRUCTIONS)
            print("user:", args.task)
            print("assistant:", require_text(first_message))
        return

    activated = activate_requested_skill(
        catalog=catalog,
        candidates=candidates,
        tool_calls=first_message.tool_calls,
    )
    messages.append(first_message)
    messages.append(activation_result_message(activated))
    reference_tool = build_reference_tool(activated.skill)
    reference_paths = reference_tool["function"]["parameters"]["properties"]["path"][
        "enum"
    ]
    second_message = request_completion(
        client=client,
        model=model,
        messages=messages,
        tools=[reference_tool] if reference_paths else None,
        tool_choice="auto" if reference_paths else None,
    )

    print("\n=== Skill activation ===")
    print(format_activation_call(activated))

    if second_message.tool_calls:
        reference = read_requested_reference(
            catalog=catalog,
            activated=activated,
            tool_calls=second_message.tool_calls,
        )
        messages.append(second_message)
        messages.append(reference_result_message(reference))
        final_message = request_completion(
            client=client,
            model=model,
            messages=messages,
            tools=[reference_tool],
            tool_choice="none",
        )
        if final_message.tool_calls:
            raise RuntimeError("DeepSeek requested another tool after reading a reference.")
        print("\n=== Skill reference ===")
        print(format_reference_call(reference))
    else:
        final_message = second_message

    print("\n=== assistant ===")
    print(require_text(final_message))
    print("\nNo tests, scripts, publication, or deployment were executed by this example.")

    if args.show_model_conversation:
        print("\n=== full model conversation ===")
        print("system:", AGENT_INSTRUCTIONS)
        print("user:", args.task)
        print(format_activation_call(activated))
        print("activation result content:", messages[3]["content"])
        if second_message.tool_calls:
            print(format_reference_call(reference))
            print("reference result content:", messages[-1]["content"])
        print("assistant:", require_text(final_message))


if __name__ == "__main__":
    main()
