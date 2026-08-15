"""Stage 03 example 6: express Stage 02 Planner–Executor as a graph.

The example is deterministic on purpose. It demonstrates orchestration state,
conditional recovery, and bounded replanning without adding LLM uncertainty.

Run:

    pip install -e ".[stage03]"
    python stages/03-stateful-orchestration/code/planner_executor_graph.py
"""

from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph


class PlanState(TypedDict, total=False):
    task: str
    plan: list[str]
    current_index: int
    completed: list[str]
    failure: str | None
    replans: int
    final_report: str


def plan_node(state: PlanState):
    return {
        "plan": [
            "check service health",
            "read primary logs",
            "write incident brief",
        ],
        "current_index": 0,
        "completed": [],
        "failure": None,
        "replans": 0,
    }


def execute_step(state: PlanState):
    step = state["plan"][state["current_index"]]

    # Simulate one environmental failure on the initial plan.
    if step == "read primary logs" and state["replans"] == 0:
        return {
            "failure": "primary log service unavailable",
        }

    completed = [*state["completed"], step]
    updates = {
        "completed": completed,
        "current_index": state["current_index"] + 1,
        "failure": None,
    }

    if step == "write incident brief":
        updates["final_report"] = (
            "Incident brief completed using: " + ", ".join(completed)
        )

    return updates


def route_after_execute(
    state: PlanState,
) -> Literal["execute", "replan", "end"]:
    if state.get("failure"):
        return "replan"
    if state["current_index"] >= len(state["plan"]):
        return "end"
    return "execute"


def replan_node(state: PlanState):
    if state["replans"] >= 1:
        raise RuntimeError("Replan budget exceeded")

    # Successful work is preserved. The new plan contains only remaining work.
    return {
        "plan": [
            "read fallback log archive",
            "write incident brief",
        ],
        "current_index": 0,
        "failure": None,
        "replans": state["replans"] + 1,
    }


builder = StateGraph(PlanState)
builder.add_node("plan", plan_node)
builder.add_node("execute", execute_step)
builder.add_node("replan", replan_node)

builder.add_edge(START, "plan")
builder.add_edge("plan", "execute")
builder.add_conditional_edges(
    "execute",
    route_after_execute,
    {
        "execute": "execute",
        "replan": "replan",
        "end": END,
    },
)
builder.add_edge("replan", "execute")

graph = builder.compile()


if __name__ == "__main__":
    initial = {"task": "Investigate checkout errors and write an incident brief."}

    print("Execution updates:")
    for update in graph.stream(initial, stream_mode="updates"):
        print(update)

    print("\nFinal state:")
    print(graph.invoke(initial))
