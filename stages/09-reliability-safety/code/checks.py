from __future__ import annotations

import time
import unittest

from guardrails import (
    ExecutionBudget,
    ExecutionContext,
    GuardedExecutor,
    PermissionPolicy,
    Principal,
    ToolFailure,
    ToolSpec,
    redact_error,
)


class Stage09Checks(unittest.TestCase):
    def make_executor(self, handler, *, safe_to_retry=False, tool_name="tool"):
        return GuardedExecutor(
            [ToolSpec(tool_name, {"value": str}, handler, safe_to_retry=safe_to_retry)],
            permissions=PermissionPolicy({"user": {tool_name}}),
        )

    def principal(self):
        return Principal("u1", frozenset({"user"}))

    def test_unknown_field_rejected_before_handler(self):
        called = False
        def handler(*, context, value):
            nonlocal called
            called = True
            return value
        result = self.make_executor(handler).execute(
            principal=self.principal(), tool_name="tool",
            arguments={"value": "x", "extra": "no"}, budget=ExecutionBudget()
        )
        self.assertFalse(result.ok)
        self.assertFalse(called)

    def test_default_deny(self):
        executor = GuardedExecutor(
            [ToolSpec("danger", {}, lambda *, context: "boom")],
            permissions=PermissionPolicy({}),
        )
        result = executor.execute(
            principal=self.principal(), tool_name="danger", arguments={}, budget=ExecutionBudget()
        )
        self.assertFalse(result.ok)
        self.assertIn("not allowed", result.error)

    def test_retryable_read_retries_once(self):
        attempts = 0
        def handler(*, context, value):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise ToolFailure("temporary", retryable=True)
            return value
        result = self.make_executor(handler, safe_to_retry=True).execute(
            principal=self.principal(), tool_name="tool", arguments={"value": "ok"},
            budget=ExecutionBudget(max_retries=1, max_same_call=3)
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.attempts, 2)

    def test_non_retryable_failure_stops(self):
        def handler(*, context, value):
            raise ToolFailure("bad input", retryable=False)
        result = self.make_executor(handler, safe_to_retry=True).execute(
            principal=self.principal(), tool_name="tool", arguments={"value": "x"},
            budget=ExecutionBudget(max_retries=5)
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.attempts, 1)

    def test_side_effect_not_retried_without_idempotency(self):
        attempts = 0
        def handler(*, context, value):
            nonlocal attempts
            attempts += 1
            raise ToolFailure("ambiguous timeout", retryable=True)
        result = self.make_executor(handler, safe_to_retry=False).execute(
            principal=self.principal(), tool_name="tool", arguments={"value": "x"},
            budget=ExecutionBudget(max_retries=3)
        )
        self.assertFalse(result.ok)
        self.assertEqual(attempts, 1)

    def test_same_call_budget_stops_loop(self):
        executor = self.make_executor(lambda *, context, value: value)
        budget = ExecutionBudget(max_tool_calls=10, max_same_call=2)
        for _ in range(2):
            self.assertTrue(executor.execute(
                principal=self.principal(), tool_name="tool",
                arguments={"value": "x"}, budget=budget
            ).ok)
        third = executor.execute(
            principal=self.principal(), tool_name="tool",
            arguments={"value": "x"}, budget=budget
        )
        self.assertFalse(third.ok)
        self.assertIn("same-call", third.error)

    def test_deadline_checked_before_handler(self):
        called = False
        def handler(*, context, value):
            nonlocal called
            called = True
            return value
        result = self.make_executor(handler).execute(
            principal=self.principal(), tool_name="tool", arguments={"value": "x"},
            budget=ExecutionBudget(),
            context=ExecutionContext(deadline_monotonic=time.monotonic() - 1)
        )
        self.assertFalse(result.ok)
        self.assertFalse(called)

    def test_secret_redaction(self):
        text = redact_error("Authorization: Bearer abc123 password=hunter2 api_key=xyz")
        self.assertNotIn("abc123", text)
        self.assertNotIn("hunter2", text)
        self.assertNotIn("xyz", text)
        self.assertGreaterEqual(text.count("[REDACTED]"), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
