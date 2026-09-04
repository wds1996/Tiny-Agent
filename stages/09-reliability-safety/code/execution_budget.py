"""Stage 09 example 4: one ledger for several kinds of execution budget."""

from tiny_agent import BudgetExceededError, BudgetLedger, ExecutionBudget


ledger = BudgetLedger(
    ExecutionBudget(
        max_tool_calls=2,
        max_retry_attempts=1,
        max_elapsed_seconds=None,
        max_tokens=1_000,
        max_cost_usd=0.50,
    )
)

ledger.consume_tool_call()
ledger.record_tokens(300)
ledger.record_cost(0.10)

print("After first operation:")
print("tool_calls =", ledger.tool_calls)
print("tokens     =", ledger.tokens)
print("cost_usd   =", ledger.cost_usd)

ledger.consume_tool_call()

try:
    ledger.consume_tool_call()
except BudgetExceededError as exc:
    print("\nThird tool call blocked:", exc)

# A budget is not an LLM request such as "please do not call too many tools".
# It is deterministic runtime state that can refuse the next operation.
