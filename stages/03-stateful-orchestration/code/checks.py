from __future__ import annotations

import unittest

from langgraph_agent import build_agent_graph, initial_state as initial_agent_state
from langgraph_workflow import build_graph as build_langgraph_workflow
from langgraph_workflow import initial_state as initial_workflow_state
from state_graph import END, START, MiniStateGraph, append_events, build_support_graph


class Stage03Checks(unittest.TestCase):
    def test_partial_update_keeps_existing_state(self) -> None:
        builder = MiniStateGraph()
        builder.add_node("set_answer", lambda state: {"answer": 42})
        builder.add_edge(START, "set_answer")
        builder.add_edge("set_answer", END)

        result = builder.compile().invoke({"question": "6 * 7"})

        self.assertEqual(
            result.state,
            {"question": "6 * 7", "answer": 42},
        )

    def test_reducer_accumulates_updates(self) -> None:
        builder = MiniStateGraph(reducers={"events": append_events})
        builder.add_node("one", lambda state: {"events": ["one"]})
        builder.add_node("two", lambda state: {"events": ["two"]})
        builder.add_edge(START, "one")
        builder.add_edge("one", "two")
        builder.add_edge("two", END)

        result = builder.compile().invoke({"events": []})

        self.assertEqual(result.state["events"], ["one", "two"])

    def test_unknown_conditional_route_is_rejected(self) -> None:
        builder = MiniStateGraph()
        builder.add_node("route", lambda state: {"route": "missing"})
        builder.add_edge(START, "route")
        builder.add_conditional_edges(
            "route",
            lambda state: state["route"],
            {"known": END},
        )

        with self.assertRaisesRegex(RuntimeError, "allowed routes"):
            builder.compile().invoke({})

    def test_cycle_is_bounded_by_application(self) -> None:
        builder = MiniStateGraph()
        builder.add_node(
            "tick",
            lambda state: {"count": state.get("count", 0) + 1},
        )
        builder.add_edge(START, "tick")
        builder.add_edge("tick", "tick")

        with self.assertRaisesRegex(RuntimeError, "max_steps=3"):
            builder.compile().invoke({}, max_steps=3)

    def test_handwritten_workflow_visits_revision_loop_once(self) -> None:
        result = build_support_graph().invoke(
            {
                "request": "I was charged twice and need a refund.",
                "revisions": 0,
                "events": [],
            }
        )

        self.assertEqual(
            result.trace,
            ("classify", "draft", "review", "revise", "review", "finish"),
        )
        self.assertEqual(result.state["revisions"], 1)
        self.assertEqual(result.state["review"], "accept")

    def test_langgraph_workflow_matches_handwritten_behavior(self) -> None:
        graph = build_langgraph_workflow()
        result = graph.invoke(
            initial_workflow_state(),
            config={"recursion_limit": 20},
        )

        self.assertEqual(result["category"], "billing")
        self.assertEqual(result["revisions"], 1)
        self.assertEqual(result["review"], "accept")
        self.assertEqual(
            result["events"],
            [
                "classified as billing",
                "drafted first response",
                "review requested one revision",
                "revised response",
                "review accepted response",
                "finished workflow",
            ],
        )

    def test_langgraph_stream_exposes_node_updates(self) -> None:
        graph = build_langgraph_workflow()
        updates = list(
            graph.stream(
                initial_workflow_state(),
                stream_mode="updates",
                config={"recursion_limit": 20},
            )
        )

        self.assertTrue(any("classify" in update for update in updates))
        self.assertTrue(any("review" in update for update in updates))
        self.assertTrue(any("finish" in update for update in updates))

    def test_react_graph_keeps_model_and_tool_responsibilities_separate(self) -> None:
        graph = build_agent_graph(max_model_steps=4)
        result = graph.invoke(
            initial_agent_state("What is 6 * 7?"),
            config={"recursion_limit": 20},
        )

        self.assertEqual(result["final_answer"], "6 * 7 = 42")
        self.assertEqual(result["model_steps"], 2)
        self.assertEqual(
            [message["role"] for message in result["messages"]],
            ["user", "assistant", "tool", "assistant"],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
