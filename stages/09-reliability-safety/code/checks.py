from __future__ import annotations

import json
import time
import unittest
from types import SimpleNamespace

from deepseek_guardrails import (
    build_executor as build_deepseek_executor,
    dispatch_tool_call,
)
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
from idempotency_demo import RefundService, build_executor as build_refund_executor


class Stage09Checks(unittest.TestCase):
    def make_executor(
        self,
        handler,
        *,
        safe_to_retry=False,
        idempotency_supported=False,
        tool_name="tool",
    ):
        return GuardedExecutor(
            [
                ToolSpec(
                    tool_name,
                    {"value": str},
                    handler,
                    safe_to_retry=safe_to_retry,
                    idempotency_supported=idempotency_supported,
                )
            ],
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

    def test_idempotency_key_needs_execution_support_before_retry(self):
        attempts = 0

        def handler(*, context, value):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise ToolFailure("ambiguous timeout", retryable=True)
            return value

        context = ExecutionContext(idempotency_key="refund:run-1:ORDER-42")
        unsupported = self.make_executor(handler, safe_to_retry=False).execute(
            principal=self.principal(),
            tool_name="tool",
            arguments={"value": "x"},
            budget=ExecutionBudget(max_retries=1),
            context=context,
        )
        self.assertFalse(unsupported.ok)
        self.assertEqual(attempts, 1)

        attempts = 0
        supported = self.make_executor(
            handler,
            safe_to_retry=False,
            idempotency_supported=True,
        ).execute(
            principal=self.principal(),
            tool_name="tool",
            arguments={"value": "x"},
            budget=ExecutionBudget(max_retries=1),
            context=context,
        )
        self.assertTrue(supported.ok)
        self.assertEqual(supported.attempts, 2)

    def test_idempotent_service_prevents_duplicate_refund_on_retry(self):
        service = RefundService()
        executor = build_refund_executor(service)

        result = executor.execute(
            principal=Principal("r1", frozenset({"refund_manager"})),
            tool_name="issue_refund",
            arguments={"order_id": "ORDER-42", "amount": "10.00"},
            budget=ExecutionBudget(max_retries=1, max_same_call=3),
            context=ExecutionContext(idempotency_key="refund:run-17:ORDER-42"),
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.attempts, 2)
        self.assertEqual(service.created_refunds, 1)

    def test_deepseek_adapter_cannot_bypass_permission_policy(self):
        call = SimpleNamespace(
            function=SimpleNamespace(
                name="issue_refund",
                arguments=json.dumps({"order_id": "ORDER-42", "amount": "10.00"}),
            ),
            id="call-demo",
        )
        name, content = dispatch_tool_call(
            executor=build_deepseek_executor(),
            principal=Principal("u1", frozenset({"support"})),
            budget=ExecutionBudget(),
            context=ExecutionContext(),
            call=call,
        )

        self.assertEqual(name, "issue_refund")
        result = json.loads(content)
        self.assertFalse(result["ok"])
        self.assertIn("not allowed", result["error"])

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
