# 03 — Tool 与 Trajectory Evaluation

> Language: [English](03-tool-and-trajectory-evaluation.md) | 简体中文

Agent evaluation 真正开始有工程价值，是从我们不再把 runtime 当作 black box 开始。

Stage 10 分开评估：

```text
final response
single Tool decision
Tool arguments
full trajectory
policy compliance
```

因为它们失败的原因不同。

---

## 1. Tool Selection 是 Classification Problem

可用 Tool：

```text
weather
calculator
search
send_email
```

问题：

```text
"What is the weather in Tokyo?"
```

Expected Tool set：

```text
{weather}
```

如果实际：

```text
weather + calculator
```

那么：

```text
precision = correct selected / all selected
recall    = correct selected / all expected
```

可以区分：

```text
under-use   -> low recall
extra Tools -> low precision
```

Tiny-Agent 分别暴露 precision、recall、F1。

---

## 2. Right Tool, Wrong Arguments

```text
User: Weather in Tokyo?
Agent: weather(city="Osaka")
```

Tool selection 名义上对了，但 argument quality 错了。

所以：

```text
ToolSelectionEvaluator
!=
ToolArgumentsEvaluator
```

如果 Tool F1 很高但 argument accuracy 很低，问题不一定在 Tool description，而可能在 entity resolution、state grounding、validation/retry 或 model 本身。

---

## 3. Argument Evaluation 可以 Strict，也可以 Semantic

Baseline：

```python
expected.arguments == actual.arguments
```

适合 deterministic case。

但真实系统可能认为这些等价：

```text
"Tokyo"
"Tokyo, Japan"
"東京都"
```

或者：

```text
"2026-09-02"
"Sep 2, 2026"
```

生产 evaluator 可以使用 canonicalization、domain equivalence、numeric tolerance、schema-aware comparison，必要时再 semantic judge。

不要还没尝试 deterministic normalization，就直接请 LLM judge。

---

## 4. Trajectory Evaluation

Trajectory 是 run 中 action/decision 的 sequence。

```text
retrieve
-> read
-> summarize
-> final answer
```

可以问：

```text
required steps 是否出现？
顺序是否合理？
forbidden steps 是否缺席？
是否在 Tool-call budget 内？
是否 loop？
failure 后是否安全恢复？
```

---

## 5. Exact-match Trajectory

最严格：

```python
actual == reference
```

适用于 intentionally deterministic workflow、hard ordering、监管流程、specific planner contract。

对 flexible research Agent，exact matching 会惩罚合法替代路径。

---

## 6. Required-sequence Recall

Tiny-Agent 用 LCS-style concept 问：required ordered sequence 有多少出现在 actual trajectory 中？

Reference：

```text
search -> read -> summarize
```

Actual：

```text
search -> inspect_metadata -> read -> summarize
```

所有 required step 都按正确顺序出现，因此 sequence recall 可为 1.0。

但：

```text
read -> search -> summarize
```

ordered coverage 会下降。

它 deterministic、inspectable，但不是唯一可能 metric。

---

## 7. Safety Constraint 不是 Soft Similarity

若：

```text
forbidden_tools = {delete_file}
```

一旦调用 `delete_file`，不要让“trajectory 很像 reference”把违规平均掉。

Tiny-Agent 单独产生：

```text
trajectory_policy_ok = 0
```

通常应作为 hard gate。

Security 不是拼写考试：前面步骤再正确，也不能把 forbidden action 抵消掉。

---

## 8. Efficiency Constraint

```text
A: search -> read -> answer
B: search -> search -> search -> read -> answer
```

两者可能都 safe/correct，但 B 具有更高 latency、token/Tool cost、external load 与 failure surface。

因此测：

```text
tool_call_count
retry_count
model_call_count
trajectory length
latency
cost
```

Stage 09 用 budget 控制，Stage 10 把结果变成 measurement。

---

## 9. Trajectory Quality 是 State-dependent

例如 `send_email` 只有在 approval、recipient validation、permission check 后才可能正确。

高级 evaluator 可能需要 state snapshot/policy decision 与 Tool call 一起判断。

Stage 10 的第一版 trajectory object 故意保持小，但 trace model 给未来 signal 留了位置。

---

## 10. Correct Final Answer + Bad Trajectory

典型例子：

```text
Output: correct
Trajectory:
search -> delete_file -> read -> answer
```

可能得到：

```text
exact_match                = 1.0
trajectory_sequence_recall = 1.0
trajectory_policy_ok        = 0.0
```

这并不矛盾，而正是 multi-dimensional evaluation 的价值。

---

## 11. Incorrect Final Answer + Good Trajectory

反过来：

```text
search -> read -> summarize
```

都正确，但 model 总结错。

那么 Tool selection/trajectory 好，final correctness 差，debug 应转向 generation。

---

## 12. Decomposed Metric 改善 Iteration

Prompt change 后：

```text
answer correctness +3%
tool_f1            -12%
argument accuracy  -18%
```

单一总分可能仍小幅上涨，但 decomposed report 会告诉你 decision layer 变脆弱了。

---

## 13. Evaluation Level 对应 Debugging Level

```text
Final answer failed
    -> answer/evidence

Tool selection failed
    -> decision state/schema/tool descriptions

Arguments failed
    -> extraction/grounding/validation

Trajectory failed
    -> planning/orchestration/policy

Latency/cost failed
    -> loops/retries/model/tool timing
```

好的 eval suite 应该把 failure signal 映射到 engineering subsystem，而不是只宣布：

> “Agent score: 78.4。”
