# 01 — From a Tool Loop to a ReAct Runtime: When Does Tool Calling Become an Agent?

> Language: English | [简体中文](01-react-and-agent-loop.zh-CN.md)

Stage 00 ended with a loop like this:

```python
while True:
    response = call_model(...)

    if response_has_tool_call(response):
        result = execute_tool(...)
        append_tool_result(result)
        continue

    return final_text(response)
```

That already looks Agent-like.

But the useful question is not:

> “Does this count as ReAct?”

The useful question is:

> **Once the model stops answering once and starts choosing the next step from real environment feedback, what new responsibilities must the application own?**

That is where Stage 01 begins.

---

## 1. One Tool call is not the same as an Agent loop

A one-shot Tool interaction may look like:

```text
User -> Model -> ToolCall -> Python -> Tool result -> Model -> Answer
```

But the travel assistant may receive:

```text
Use the course's mock Tokyo weather, convert it to Fahrenheit,
and explain the temperature to a traveler.
```

The model cannot construct the second action correctly until the first observation exists.

First:

```text
get_mock_weather(city="Tokyo")
```

Then the environment returns:

```json
{
  "temperature_c": 18.0,
  "condition": "cloudy"
}
```

Only now can the next action be grounded in a real value:

```text
celsius_to_fahrenheit(temperature_c=18.0)
```

So the control structure becomes:

```text
current state
   ↓
model chooses a next action
   ↓
Runtime executes
   ↓
Observation changes state
   ↓
model chooses again
```

That repeated dependence on new observations is where an explicit Agent Runtime starts to matter.

---

## 2. A practical interpretation of ReAct

ReAct is often presented historically as:

```text
Thought -> Action -> Observation -> Thought -> ...
```

Do not turn that notation into a Runtime requirement.

A production-oriented implementation does not need to expose hidden chain-of-thought in order to use the valuable control pattern.

For Runtime engineering, the durable abstraction is:

```text
Decide -> Act -> Observe -> Decide again
```

The auditable facts are:

```text
Action
Arguments
Observation
Final Answer
```

Those are the facts needed to answer debugging questions such as:

```text
Which Tool did the model request?
With what arguments?
Did the Runtime really execute it?
What did the environment return?
What happened on the next turn?
Why did the run stop?
```

Hidden reasoning is not the Runtime contract.

---

## 3. Keep Action and Observation separate

### Action

A model proposal:

```text
get_mock_weather(city="Tokyo")
```

Nothing has happened in the real world yet.

### Observation

What the Runtime obtains after actual execution:

```json
{
  "city": "Tokyo",
  "temperature_c": 18.0,
  "condition": "cloudy",
  "source": "course_mock"
}
```

The relationship is:

```text
Model proposal
     ↓
   Action
     ↓
Runtime executes
     ↓
Observation
```

If a ToolCall is treated as though it has already executed, permissions, approval, sandboxing, and side-effect safety become impossible to reason about cleanly.

Tiny-Agent therefore keeps one rule from the start:

> **The model may propose an action; only the Runtime can turn that proposal into a real side effect.**

---

## 4. Why observations matter

Consider a research task:

```text
Find a recent Agent Memory paper and summarize the method.
```

The first model decision might be:

```text
search_papers(query="agent memory")
```

But real results may contain an old survey, a similarly named blog post, or a promising 2026 paper with incomplete metadata.

The next action should depend on what was actually returned.

That is a major difference between an Agent loop and a predetermined pipeline:

> **Environment feedback can change the control path.**

If every next step is known before execution starts, a deterministic Workflow is often the better abstraction. Stage 02 will examine that boundary directly.

---

## 5. Why the Runtime must own the loop

A dangerous minimal implementation is:

```python
while True:
    response = model.generate(...)
    for call in response.tool_calls:
        execute(call.name, call.arguments)
```

It silently assumes:

```text
model wants to execute
=
application allows execution
```

A real Runtime must own questions such as:

```text
Is the Tool registered?
Are the arguments acceptable?
Is the caller authorized?
Is approval required?
Has a step/cost/time budget been exceeded?
Should a failure become an observation, a retry, or a fatal error?
Did the model violate the response contract?
```

Stage 01 implements only the smallest subset, but ownership must be correct from the beginning.

---

## 6. What can one model turn return?

Tiny-Agent normalizes one model decision into:

```python
@dataclass(slots=True)
class ModelResponse:
    final_answer: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
```

The Runtime therefore understands two primary outcomes.

### Outcome A — ToolCall(s)

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

The Runtime records the action, executes the Tool, records the Observation, and starts another model turn.

### Outcome B — Final answer

```python
ModelResponse(
    final_answer="The course's mock Tokyo weather is 18°C, about 64.4°F."
)
```

The run terminates.

### What if neither exists?

```python
ModelResponse()
```

That is not a vague “maybe the model needs more time.” It is a model/Runtime contract violation and should fail explicitly.

---

## 7. `max_steps` is a control boundary

A model-driven loop can produce:

```text
search -> search -> search -> search -> ...
```

So even a teaching Runtime needs a hard bound:

```python
for step in range(1, self.max_steps + 1):
    ...

raise RuntimeError(
    f"Agent exceeded max_steps={self.max_steps}"
)
```

`max_steps` is not just a tuning parameter. It prevents the default policy from becoming “let a probabilistic model continue forever.”

It does not solve everything: a single Tool can still hang, spend money, perform a dangerous side effect, or emit many calls in one step. Later stages add timeouts, permissions, approvals, cost budgets, and other controls.

---

## 8. Tool failures can become observations — carefully

A recoverable failure can sometimes help the model repair its next action.

For example, a bad argument could become a safe observation such as:

```text
ToolFailure[invalid_arguments]
```

The next model turn may correct the call.

The useful principle is:

> **Some failures are environment feedback that can support recovery.**

Do not misread that as “copy every exception string into model context.” Exceptions can contain sensitive internals. The evolving `src/tiny_agent/runtime.py` has already been hardened by later reliability work to redact unexpected failures. Stage 01 teaches the loop semantics; Stage 07 teaches error classification and policy.

---

## 9. Use a fake model to see the real Runtime

`minimal_react_runtime.py` intentionally uses:

```python
class ScriptedTravelModel:
    ...
```

Its trajectory is deterministic:

```text
turn 1 -> get_mock_weather("Tokyo")
turn 2 -> celsius_to_fahrenheit(18.0)
turn 3 -> final answer
```

We remove model uncertainty so we can inspect the control layer itself.

Run:

```bash
python stages/01-react-runtime/code/minimal_react_runtime.py
```

Expected shape:

```text
01. USER        ...
02. ACTION      get_mock_weather({'city': 'Tokyo'}) [id=call_weather]
03. OBSERVATION get_mock_weather -> {...}
04. ACTION      celsius_to_fahrenheit({'temperature_c': 18.0}) [id=call_convert]
05. OBSERVATION celsius_to_fahrenheit -> 64.4
06. ASSISTANT   The course's mock Tokyo weather is 18°C, about 64.4°F.
```

Read that as an **execution trajectory**, not merely as a chat transcript.

---

## 10. ReAct and Workflow are not a status hierarchy

Do not assume:

```text
Agent > Workflow
```

If the path is known:

```text
parse -> validate -> retrieve -> rerank -> answer
```

write deterministic control flow.

Use model-directed control when the next step genuinely depends on semantic judgment and environment feedback.

A useful question is:

> **Is there real semantic uncertainty here, or are we just avoiding ordinary software design?**

Stage 02 continues from that question.

---

## 11. What to carry into the next chapter

Do not leave this chapter with only “Reason-Act-Observe.” Keep the engineering chain:

```text
Model
  proposes the next decision
        ↓
Runtime
  owns loop / execution / stopping
        ↓
Tool
  interacts with the environment
        ↓
Observation
  becomes new information
        ↓
Model
  decides again from updated context
```

Next we will take the Stage 00 hand-written loop and extract each of those responsibilities into a minimal Runtime architecture.

---

## Check yourself

1. Why does the Tokyo example need another model turn after `get_mock_weather`?
2. Why are ToolCall and Tool execution different events?
3. Why should an Observation enter the next model turn instead of only being logged?
4. Why must the Runtime own stopping conditions?
5. Why is `ModelResponse()` a contract violation?
6. Why is FakeModel useful rather than “fake Agent teaching”?
7. Why does ReAct not require exposing hidden chain-of-thought?
8. When is a deterministic Workflow preferable to an Agent loop?