"""Stage 07 example 6: exact repeated-call detection."""

from tiny_agent import RepeatedToolCallDetector, ToolLoopDetectedError


detector = RepeatedToolCallDetector(max_identical_calls=2)

for turn in range(1, 5):
    try:
        detector.observe("search", {"query": "same query", "top_k": 3})
        print(f"turn {turn}: allowed")
    except ToolLoopDetectedError as exc:
        print(f"turn {turn}: blocked -> {exc}")
        break

# A loop detector is not a replacement for max_tool_calls.
# It is an earlier, more specific circuit breaker for suspicious repetition.
