# Structured Output

## 1. 为什么只靠自然语言不够？

Language model 很擅长生成文本，但 application 经常需要的是软件能够可靠解析的数据。

对人来说，下面这句话完全可以理解：

```text
The user wants to book a meeting tomorrow at 3 PM with Alice.
```

但 application code 更希望得到：

```json
{
  "intent": "schedule_meeting",
  "date": "tomorrow",
  "time": "15:00",
  "attendees": ["Alice"]
}
```

Structured Output 就是 probabilistic natural-language generation 与 deterministic software logic 之间的一座桥。

## 2. 核心思想

不是让 model 随意输出 prose，而是由 application 定义预期结果的结构。

概念上：

```json
{
  "type": "object",
  "properties": {
    "intent": {"type": "string"},
    "confidence": {"type": "number"}
  },
  "required": ["intent", "confidence"]
}
```

不同 provider API 的具体写法可能不同，但工程原则稳定：

> **当 software 后续必须根据 model output 做决定时，应尽可能让这个 boundary machine-readable。**

## 3. Structured Output vs 只在 Prompt 里要求 JSON

比较弱的方式：

```text
Please answer in JSON.
```

model 仍然可能输出：

```text
Sure! Here is the JSON:
{...}
```

甚至生成 malformed JSON。

schema-constrained Structured Output 更强，是因为 provider 或 runtime 会主动约束 / 验证 output format。

如果 native schema enforcement 不可用，application 仍然应该在使用结果前做本地 validation。

## 4. Validation 是 Runtime 的一部分

假设期望对象：

```python
{
    "city": "Tokyo",
    "unit": "celsius"
}
```

可能出现：

- 缺少 `city`；
- `unit` 不支持；
- data type 错误；
- 出现 unexpected field；
- 值在语义上不合法。

所以 runtime 必须把 model output 当成 **untrusted input**，直到 validation 成功。

Agent system 中这一点更加重要，因为 structured model output 可能进一步触发真实 action。

## 5. Structured Output 不等于 Function Calling

两者相关，但解决的是不同问题。

### Structured Output

application 希望 model response 具有特定 data shape：

```text
User -> Model -> {intent, priority, summary}
```

### Function Calling

application 向 model 描述当前可用 action，让模型选择是否以及如何调用某一个：

```text
User -> Model -> call search(query="...")
```

ToolCall 本身通常也是 structured data，但它的语义目的在于：

```text
action selection
```

而不仅仅是“把回答排成 JSON”。

## 6. Agent 中 Structured Output 还有哪些用途？

它不仅用于 Tool。

### Routing

```json
{
  "route": "web_search"
}
```

### Planning

```json
{
  "steps": [
    {"id": 1, "task": "search sources"},
    {"id": 2, "task": "compare evidence"}
  ]
}
```

### Evaluation

```json
{
  "passed": true,
  "score": 0.92,
  "reason": "..."
}
```

### Human Approval Metadata

```json
{
  "risk": "high",
  "requires_approval": true
}
```

也就是说，凡是 model output 后面要被 software 当成 control data 使用，都应该认真考虑 structured contract。

## 7. Typed Application Model

项目变大以后，raw dictionary 很容易变得难以维护。

与其到处传 arbitrary object，可以定义 typed structure：

```python
@dataclass
class ToolCall:
    name: str
    arguments: dict
```

或者使用 Pydantic 之类的 validation library。

收益包括：

- explicit contract；
- 更好的 IDE support；
- centralized validation；
- 更清晰的 tests；
- 更容易做 provider normalization。

Tiny-Agent 使用 normalized internal type，因此 core runtime 不依赖特定 provider response format。

## 8. 一个实用规则

```text
面向人类沟通
    -> natural language

软件需要解释 / 决策的 boundary
    -> structured output
```

很多 production Agent bug，都来自系统让 LLM 用 unconstrained prose 表达关键控制信息，然后 application 再靠脆弱的 string parsing 猜它到底想说什么。

如果一个布尔决策最后靠：

```python
if "yes" in model_text.lower():
```

来控制生产副作用，那么问题通常不是 prompt 还不够长，而是 contract 设计得太松。

## 9. 关键结论

- Structured Output 让 probabilistic model response 更容易被 deterministic software 消费。
- schema-constrained output 比 prompt 中简单要求 JSON 更强。
- model 生成的 structure 仍然必须 validate。
- Structured Output 与 Function Calling 解决的是不同问题。
- Agent routing、planning、evaluation 与 Tool use 都受益于 explicit structured contract。

## 复习题

1. 为什么 `Please output JSON` 比 schema-constrained output 弱？
2. 为什么 model-generated JSON 仍然应该被视为 untrusted input？
3. Structured Output 与 Tool Calling 的概念差异是什么？
4. 除了 Tool 之外，Agent runtime 还有哪些地方适合使用 Structured Output？