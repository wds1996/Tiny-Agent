import unittest

from team import Delegation, Specialist, TeamBudget, TeamRuntime, project_context


class Stage11Checks(unittest.TestCase):
    def runtime(self):
        return TeamRuntime([
            Specialist("supervisor", "", "supervisor"),
            Specialist("a", "a", "A"),
            Specialist("b", "b", "B"),
        ])

    def test_context_projection_is_allowlist(self):
        self.assertEqual(project_context({"needed": "yes", "secret": "no"}, ("needed",)), {"needed": "yes"})

    def test_delegation_returns_result_without_changing_owner(self):
        result = self.runtime().delegate(
            caller="supervisor", delegation=Delegation("a", "work", ("x",)),
            shared_context={"x": "1"}, budget=TeamBudget()
        )
        self.assertIn("A", result)

    def test_handoff_changes_owner(self):
        result = self.runtime().handoff(
            caller="supervisor", target="b", task="continue",
            shared_context={}, context_keys=(), budget=TeamBudget()
        )
        self.assertEqual(result.owner, "b")

    def test_self_delegation_rejected(self):
        with self.assertRaises(ValueError):
            self.runtime().delegate(
                caller="a", delegation=Delegation("a", "loop"),
                shared_context={}, budget=TeamBudget()
            )

    def test_delegation_budget_stops_unbounded_team_loop(self):
        runtime = self.runtime()
        budget = TeamBudget(max_delegations=1)
        runtime.delegate(
            caller="supervisor", delegation=Delegation("a", "one"),
            shared_context={}, budget=budget
        )
        with self.assertRaises(RuntimeError):
            runtime.delegate(
                caller="supervisor", delegation=Delegation("b", "two"),
                shared_context={}, budget=budget
            )

    def test_handoff_budget_is_separate(self):
        with self.assertRaises(RuntimeError):
            self.runtime().handoff(
                caller="supervisor", target="a", task="take over",
                shared_context={}, context_keys=(), budget=TeamBudget(max_handoffs=0)
            )

    def test_unknown_agent_is_rejected(self):
        with self.assertRaises(KeyError):
            self.runtime().delegate(
                caller="supervisor", delegation=Delegation("missing", "work"),
                shared_context={}, budget=TeamBudget()
            )

    def test_fan_out_respects_each_context_projection(self):
        results = self.runtime().fan_out(
            caller="supervisor",
            delegations=[Delegation("a", "first", ("x",)), Delegation("b", "second", ("y",))],
            shared_context={"x": "1", "y": "2", "secret": "3"},
            budget=TeamBudget(max_delegations=2),
        )
        self.assertIn("x=1", results[0])
        self.assertNotIn("secret", results[0])
        self.assertIn("y=2", results[1])


if __name__ == "__main__":
    unittest.main(verbosity=2)
