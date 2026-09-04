# Stage 01 Review and Implementation Exercises: Rebuild the Runtime Instead of Memorizing It

> Language: English | [简体中文](review-questions.zh-CN.md)

The goal is not to test vocabulary.

If you understand Stage 01, you should be able to explain the Runtime path without source code, diagnose a badly coupled Agent loop, and rebuild a small Runtime with deterministic tests.

---

## Part A — Explain in your own words

1. Stage 00 already had a repeated Tool loop. Why extract `AgentRuntime` at all?
2. Does `ToolCall` mean a Tool has already executed, or that the model proposed an action? Why?
3. Why must an Observation enter the next model turn?
4. Why should `Model.generate()` represent exactly one model turn?
5. What future capabilities become difficult if the Provider Adapter owns the entire model/Tool loop?
6. Why is `ModelResponse` worth defining as a Tiny-Agent internal type?
7. What boundary does `ToolRegistry` create beyond removing `if/elif` statements?
8. What problem does `call_id` / `ToolCall.id` solve when multiple calls exist?
9. Why do multiple ToolCalls in one turn not imply concurrent Python execution?
10. What does `max_steps` prevent, and what does it not prevent?
11. Why is FakeModel valuable for Runtime unit tests?
12. Why can live-model evaluation not replace deterministic unit testing?
13. Why does a ReAct-style Runtime not require exposing hidden chain-of-thought?
14. Why does Tool visibility not imply execution authorization?
15. Why can a correct final answer still hide an incorrect Agent trajectory?

---

## Part B — Trace one Runtime turn by hand

Given:

```text
Use the course mock Tokyo weather and convert it to Fahrenheit.
```

The model returns:

```python
ModelResponse(
    tool_calls=[
        ToolCall(
            id="call_weather",
            name="get_mock_weather",
            arguments={"city": "Tokyo"},
        )
    ]
)
```

The Tool returns:

```json
{
  "city": "Tokyo",
  "temperature_c": 18.0,
  "condition": "cloudy"
}
```

Write by hand:

1. the assistant ToolCall transcript item;
2. the Tool observation item;
3. the critical new information available to the next `model.generate(...)` call;
4. a reasonable second `ModelResponse`;
5. why `call_weather` cannot be discarded.

Continue the trace through the final answer.

---

## Part C — Coding Lab 1: implement the minimal Runtime from scratch

Without copying `minimal_react_runtime.py`, implement:

```text
ToolCall
ModelResponse
Model Protocol
Tool
ToolRegistry
AgentResult
AgentRuntime
```

Minimum requirements:

```text
ToolCalls
final answers
max_steps
unknown Tools must never execute; failure handling must be explicit
action/observation trajectory
explicit invalid-empty-response failure
```

For an unknown Tool, choose and document one clear policy for this exercise: either terminate the run explicitly or return a bounded, safe failure Observation that lets the next model turn recover. Do not guess a similarly named Python function and do not dynamically execute arbitrary names.

Start with a FakeModel.

Acceptance trajectory:

```text
turn 1 -> get_mock_weather("Tokyo")
turn 2 -> celsius_to_fahrenheit(18.0)
turn 3 -> final answer
```

Assert the step count, two actions, two observations, and a final answer containing 18°C / 64.4°F.

---

## Part D — Coding Lab 2: recover from a safe Tool failure

Create a FakeModel trajectory:

```text
turn 1 -> celsius_to_fahrenheit(temperature_c="bad")
turn 2 -> sees a safe ToolFailure and retries with 18.0
turn 3 -> final answer
```

The Runtime should not crash on the recoverable failure, should not expose a raw stack trace, and should let the next model turn observe the failure.

Then answer: which failures should become model observations, and which should terminate execution?

---

## Part E — Coding Lab 3: prove `max_steps` is a hard boundary

Implement an `EndlessToolModel` that requests the same `echo` Tool forever.

Expected result with `max_steps=2`:

```text
RuntimeError: Agent exceeded max_steps=2
```

List at least five risks that `max_steps` does not solve.

---

## Part F — Coding Lab 4: multiple ToolCalls in one turn

Return both independent calls in one `ModelResponse`:

```text
celsius_to_fahrenheit(18.0)
celsius_to_fahrenheit(20.0)
```

Verify that both calls and both correlated observations (`64.4` and `68.0`) reach the next model turn.

Then add `sleep(1)` to the conversion handler and observe that the Stage 01 Runtime is still sequential.

Explain why model-level multiple ToolCalls and Runtime-level concurrent execution are different concepts. This version deliberately uses two valid independent calls so the experiment measures concurrency semantics rather than mixing in an unrelated Tool failure.

---

## Part G — Coding Lab 5: connect a real OpenAI model

Run:

```bash
python -m pip install -e ".[openai]"
export OPENAI_API_KEY="..."
python stages/01-react-runtime/code/openai_multi_tool_agent.py
```

Record:

```text
user input
model action(s)
Tool arguments
observation(s)
final answer
step count
```

Identify which behavior is deterministic Runtime policy and which behavior is a stochastic model decision.

If the model uses a different valid Tool trajectory than you predicted, is that a Runtime bug? If it answers correctly without using a required Tool, should the run pass evaluation?

---

## Part H — Read tests as executable specifications

Read:

```text
tests/test_runtime.py
tests/test_runtime_edges.py
```

For every test, write one sentence:

```text
“This test protects the Runtime invariant that ...”
```

You should identify invariants around Tool execution/Observation flow, maximum steps, safe failure observations, and invalid empty responses.

---

## Part I — Architecture debugging

Diagnose this intentionally bad design:

```python
class AgentRuntime:
    def run(self, prompt):
        client = OpenAI()

        while True:
            response = client.responses.create(...)

            for item in response.output:
                if item.type == "function_call":
                    if item.name == "weather":
                        result = weather(...)
                    elif item.name == "refund":
                        result = refund(...)
```

Find at least six architecture problems involving provider coupling, Tool routing, protocol parsing, execution authority, stopping, validation, testing seams, or observation structure.

Then redraw the dependency boundaries.

---

## Part J — Final challenge: build a Runtime for your own domain

Choose a different domain such as a coding assistant, paper-research assistant, file organizer, robot task assistant, or data-analysis assistant.

Design at least three Tools:

```text
one read-only Tool
one calculation/transformation Tool
one Tool that can fail
```

Demonstrate four trajectories:

1. direct final answer with no Tool;
2. one-Tool task;
3. serial two-or-more-Tool task;
4. Tool failure followed by recovery or safe termination.

Write deterministic Runtime tests.

Your report should explain why the Tool granularity was chosen, which logic belongs to Runtime vs Adapter vs handler, which failure classes remain unsolved, and which production capability you would add next.

---

# Interview-style questions

1. Trace a ToolCall from model output through Tool execution and back into the next model input.
2. Why should a Provider Adapter not own the Agent loop?
3. Why is `call_id` a correlation identifier rather than decorative metadata?
4. Why is ToolRegistry an execution boundary rather than merely a dictionary?
5. How do you test an Agent Runtime without calling a live LLM?
6. If a company switches from OpenAI to Qwen, which files should ideally change and which should not?
7. Why are multiple ToolCalls and concurrent Tool execution different?
8. Why is `max_steps` necessary but insufficient?
9. Which capability categories are still missing from Stage 01 before production?
10. Why is “the demo runs” not an architecture-completion criterion?
