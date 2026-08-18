import asyncio

import pytest

from tiny_agent import Tool, ToolRegistry


def test_async_registry_executes_sync_handler() -> None:
    registry = ToolRegistry(
        [
            Tool(
                name="add",
                description="Add two integers.",
                parameters={"type": "object"},
                handler=lambda a, b: a + b,
            )
        ]
    )

    result = asyncio.run(registry.aexecute("add", {"a": 2, "b": 3}))
    assert result == 5


def test_async_registry_awaits_async_handler() -> None:
    async def multiply(a: int, b: int) -> int:
        return a * b

    registry = ToolRegistry(
        [
            Tool(
                name="multiply",
                description="Multiply two integers.",
                parameters={"type": "object"},
                handler=multiply,
            )
        ]
    )

    result = asyncio.run(registry.aexecute("multiply", {"a": 4, "b": 5}))
    assert result == 20


def test_sync_execute_rejects_async_handler_instead_of_returning_coroutine() -> None:
    async def remote_tool() -> str:
        return "remote"

    registry = ToolRegistry(
        [
            Tool(
                name="remote",
                description="An async remote capability.",
                parameters={"type": "object"},
                handler=remote_tool,
            )
        ]
    )

    with pytest.raises(RuntimeError, match="asynchronous"):
        registry.execute("remote", {})
