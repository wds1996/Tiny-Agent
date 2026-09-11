import unittest
from types import SimpleNamespace

from deepseek_team import dispatch_delegation
from team import (
    Delegation,
    Principal,
    Specialist,
    TeamBudget,
    TeamPolicy,
    TeamRuntime,
    project_context,
)


class Stage11Checks(unittest.TestCase):
    def runtime(self) -> TeamRuntime:
        return TeamRuntime(
            [
                Specialist("supervisor", "supervisor"),
                Specialist("a", "A"),
                Specialist("b", "B"),
            ],
            policy=TeamPolicy({"support": frozenset({"a", "b"})}),
        )

    def principal(self) -> Principal:
        return Principal("u1", frozenset({"support"}))

    def test_context_projection_is_allowlist(self) -> None:
        self.assertEqual(
            project_context({"needed": "yes", "secret": "no"}, ("needed",)),
            {"needed": "yes"},
        )

    def test_delegation_keeps_owner_with_caller_and_returns_structure(self) -> None:
        runtime = self.runtime()
        message = runtime.delegate(
            caller="supervisor",
            principal=self.principal(),
            delegation=Delegation("a", "work", ("x",)),
            shared_context={"x": "1"},
            budget=TeamBudget(),
        )
        self.assertEqual(message.agent, "a")
        self.assertEqual(message.status, "completed")
        self.assertEqual(message.provenance, ("specialist:a",))
        self.assertEqual(runtime.events[0].kind, "delegation")

    def test_handoff_changes_owner(self) -> None:
        result = self.runtime().handoff(
            caller="supervisor",
            principal=self.principal(),
            target="b",
            task="continue",
            shared_context={},
            context_keys=(),
            budget=TeamBudget(),
        )
        self.assertEqual(result.owner, "b")
        self.assertEqual(result.message.agent, "b")

    def test_self_delegation_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.runtime().delegate(
                caller="a",
                principal=self.principal(),
                delegation=Delegation("a", "loop"),
                shared_context={},
                budget=TeamBudget(),
            )

    def test_delegation_budget_stops_unbounded_team_loop(self) -> None:
        runtime = self.runtime()
        budget = TeamBudget(max_delegations=1)
        runtime.delegate(
            caller="supervisor",
            principal=self.principal(),
            delegation=Delegation("a", "one"),
            shared_context={},
            budget=budget,
        )
        with self.assertRaises(RuntimeError):
            runtime.delegate(
                caller="supervisor",
                principal=self.principal(),
                delegation=Delegation("b", "two"),
                shared_context={},
                budget=budget,
            )

    def test_handoff_budget_is_separate(self) -> None:
        with self.assertRaises(RuntimeError):
            self.runtime().handoff(
                caller="supervisor",
                principal=self.principal(),
                target="a",
                task="take over",
                shared_context={},
                context_keys=(),
                budget=TeamBudget(max_handoffs=0),
            )

    def test_unknown_agent_is_rejected(self) -> None:
        with self.assertRaises(KeyError):
            self.runtime().delegate(
                caller="supervisor",
                principal=self.principal(),
                delegation=Delegation("missing", "work"),
                shared_context={},
                budget=TeamBudget(),
            )

    def test_policy_is_default_deny(self) -> None:
        with self.assertRaises(PermissionError):
            self.runtime().delegate(
                caller="supervisor",
                principal=Principal("u2", frozenset({"intern"})),
                delegation=Delegation("a", "work"),
                shared_context={},
                budget=TeamBudget(),
            )

    def test_fan_out_respects_each_context_projection(self) -> None:
        results = self.runtime().fan_out(
            caller="supervisor",
            principal=self.principal(),
            delegations=[
                Delegation("a", "first", ("x",)),
                Delegation("b", "second", ("y",)),
            ],
            shared_context={"x": "1", "y": "2", "secret": "3"},
            budget=TeamBudget(max_delegations=2),
        )
        self.assertEqual(results[0].data, {"x": "1"})
        self.assertEqual(results[1].data, {"y": "2"})

    def test_deepseek_adapter_uses_runtime_projection_and_policy(self) -> None:
        runtime = TeamRuntime(
            [
                Specialist("supervisor", "supervisor"),
                Specialist("orders", "orders"),
                Specialist("policy", "policy"),
            ],
            policy=TeamPolicy({"support": frozenset({"orders", "policy"})}),
        )
        call = SimpleNamespace(
            function=SimpleNamespace(
                name="delegate_to_specialist",
                arguments='{"specialist": "orders", "task": "inspect"}',
            )
        )
        content = dispatch_delegation(
            runtime=runtime,
            principal=self.principal(),
            budget=TeamBudget(),
            context={"order_id": "ORDER-42", "internal_secret": "no"},
            call=call,
        )
        self.assertIn('"ok": true', content)
        self.assertIn("ORDER-42", content)
        self.assertNotIn("internal_secret", content)


if __name__ == "__main__":
    unittest.main(verbosity=2)
