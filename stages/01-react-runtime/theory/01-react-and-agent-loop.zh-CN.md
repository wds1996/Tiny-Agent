# 01 — 从 Tool loop 到 ReAct Runtime：什么时候“调用模型”开始变成 Agent？

> Language: [English](01-react-and-agent-loop.md) | 简体中文

Stage 00 最后一章里，我们已经写过这样的循环：

```python
while True:
    response = call_model(...)

    if response_has_tool_call(response):
        result = execute_tool(...)
        append_tool_result(result)
        continue

    return final_text(response)
```

如果只看这几行，它已经很像一个 Agent 了。

但真正值得学习的问题不是：

> “这个循环是不是 ReAct？”

而是：

> **当模型不再只回答一次，而是根据真实环境返回的结果不断决定下一步时，应用程序必须承担哪些新的责任？**

这一章就从这个问题开始。

---

## 1. 一次 Tool Calling 和 Agent loop 差在哪里？

一次 Tool Calling 可以是：

```text
用户
  ↓
模型
  ↓
ToolCall
  ↓
Python 执行
  ↓
结果返回模型
  ↓
最终回答
```

如果任务到这里一定结束，控制流程仍然比较固定。

但旅行助手可能遇到：

```text
用户：查询东京的课程模拟天气，并换算成华氏度。
```

模型第一轮只知道需要查天气：

```text
get_mock_weather(city="Tokyo")
```

执行后才获得：

```json
{
  "temperature_c": 18.0,
  "condition": "cloudy"
}
```

现在下一步才变得明确：

```text
celsius_to_fahrenheit(temperature_c=18.0)
```

也就是说，第二个 action 的参数依赖第一个 observation。

这时程序不再是：

```text
模型调用一次 -> Tool -> 模型回答
```

而是：

```text
当前状态
   ↓
模型决定下一步
   ↓
执行 action
   ↓
获得 observation
   ↓
状态发生变化
   ↓
模型再次决定
```

这个“根据新 observation 再决定”的循环，才是 Agent runtime 真正开始出现的地方。

---

## 2. ReAct 到底应该怎样理解？

经典 ReAct 常被写成：

```text
Thought -> Action -> Observation -> Thought -> ...
```

这个表示法很有历史意义，但如果你直接把它当工程实现，很容易得到一个错误印象：

> “实现 ReAct 就是把模型完整思维过程打印出来。”

不是。

从 Runtime 角度，更耐用的抽象是：

```text
Decide -> Act -> Observe -> Decide again
```

也就是：

```text
模型：根据当前上下文提出下一步
Runtime：决定是否以及怎样执行
Environment：产生真实结果
Runtime：把结果变成 observation
模型：根据新的 observation 继续判断
```

这里真正需要被记录和审计的是：

```text
Action
Arguments
Observation
Final Answer
```

而不是强迫模型公开 hidden chain-of-thought。

### 为什么这很重要？

因为以后你调试 Agent 时真正需要回答的是：

```text
模型调用了什么 Tool？
参数是什么？
Runtime 实际执行了吗？
Tool 返回了什么？
下一轮为什么又调用了另一个 Tool？
在哪一步结束？
```

这些都是可观察的执行事实。

至于模型内部到底经过了多少隐藏 reasoning，不应该成为 Runtime 正确性的接口。

---

## 3. Action 和 Observation 不要混在一起

这是 Stage 01 最基础、但也最容易被写乱的一组概念。

### Action：模型提出“我想做什么”

例如：

```text
get_mock_weather(city="Tokyo")
```

它只是一个**提议**。

此时真实世界还没有发生任何事情。

### Observation：Runtime 执行后真实得到什么

例如：

```json
{
  "city": "Tokyo",
  "temperature_c": 18.0,
  "condition": "cloudy",
  "source": "course_mock"
}
```

这是环境反馈。

二者的关系是：

```text
Model proposal
     │
     ▼
   Action
     │
Runtime executes
     │
     ▼
Observation
```

如果你把 ToolCall 当成“已经执行”，后面权限、审批、Sandbox、安全边界都会全部混乱。

所以 Tiny-Agent 一直坚持：

> **模型可以提出 action，但只有 Runtime 能把 action 变成真实 side effect。**

---

## 4. 为什么 observation 会改变下一步？

假设我们不是查模拟天气，而是在真实系统里搜索论文。

用户说：

```text
找一篇最新的 Agent Memory 论文，并总结方法。
```

模型第一步可能：

```text
search_papers(query="agent memory")
```

但真实搜索结果可能出现：

```text
结果 A：2024 年综述
结果 B：标题很像，但不是论文
结果 C：2026 年论文，metadata 不完整
```

下一步不能提前写死。

模型可能决定：

```text
read_paper_metadata(result_C)
```

也可能：

```text
search_papers(query="exact title")
```

还可能发现没有足够证据，向用户说明无法确认。

这就是 Agent loop 和普通流水线最大的区别之一：

> **环境反馈会改变后续控制路径。**

如果所有下一步在运行前就已经确定，那通常更接近 Workflow，而不是需要模型动态控制的 Agent loop。

Stage 02 会系统讨论这个边界。

---

## 5. Runtime 为什么必须拥有 loop？

这里可以先写一个危险的版本：

```python
while True:
    response = model.generate(...)

    for call in response.tool_calls:
        execute(call.name, call.arguments)
```

看起来很短。

但它偷偷做了一个非常危险的假设：

```text
模型想执行
=
应用允许执行
```

真实 Runtime 至少要拥有这些控制权：

```text
Tool 是否注册？
参数是否能被接受？
当前调用者有没有权限？
是否需要人工批准？
现在是否已经超过 step / cost / timeout budget？
Tool 失败后是返回 observation、重试还是直接终止？
模型是否已经违反返回协议？
```

Stage 01 只实现其中最小的一部分，但 ownership 必须从第一天就放对位置。

否则以后再加安全机制，你会发现它们只能硬塞进 provider adapter 或 Tool handler，非常痛苦。

---

## 6. 每一轮模型调用到底允许返回什么？

Tiny-Agent Stage 01 把一次模型决策归一化成：

```python
@dataclass(slots=True)
class ModelResponse:
    final_answer: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
```

也就是说，Runtime 主要理解两种结果。

### 结果 A：模型提出 ToolCall

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

Runtime 不结束，而是：

```text
记录 action
→ 执行 Tool
→ 记录 observation
→ 进入下一轮模型调用
```

### 结果 B：模型给最终回答

```python
ModelResponse(
    final_answer="东京课程模拟天气为 18°C，约 64.4°F。"
)
```

Runtime 返回 `AgentResult` 并停止。

### 那如果两者都没有呢？

例如：

```python
ModelResponse()
```

这不是“模型有点迷茫，等一下就好”。

这是**模型 / Runtime contract 被破坏**。

正确做法应该明确报错：

```python
raise RuntimeError(
    "Model returned neither tool calls nor a final answer"
)
```

工程上，一个明确失败的 contract violation 通常比“猜模型想干嘛”安全得多。

---

## 7. 为什么必须有 `max_steps`？

任何由模型驱动的循环都可能出现：

```text
search
→ search
→ search
→ search
→ ...
```

或者：

```text
Tool 失败
→ 模型重试
→ Tool 失败
→ 模型换个参数再重试
→ 一直不结束
```

所以最小 Runtime 也必须有硬停止条件：

```python
for step in range(1, self.max_steps + 1):
    ...

raise RuntimeError(
    f"Agent exceeded max_steps={self.max_steps}"
)
```

注意：`max_steps` 不是“优化参数”。

它是一个**系统控制边界**。

没有它，你实际上是在告诉一个概率模型：

> “你可以无限次决定下一步，直到自己觉得满意。”

这不是一个认真系统应该接受的默认策略。

当然，`max_steps` 只能解决“最多循环几次”。

它解决不了：

```text
单个 Tool 卡 30 分钟
一次 Tool 花掉很多钱
模型在 5 步内删错数据
一个 step 里发出 100 个 ToolCall
```

这些会在后续 Stage 分别用 timeout、permission、approval、cost budget 等机制处理。

---

## 8. Tool 失败时，应该直接把 Runtime 弄崩吗？

不一定。

假设 Tool 收到：

```text
celsius_to_fahrenheit(temperature_c="eighteen")
```

如果这是一个可恢复的参数问题，我们希望模型有机会看到一个**安全的失败 observation**，然后修正：

```text
ToolFailure[invalid_arguments]
```

接着模型可能重新发出：

```text
celsius_to_fahrenheit(temperature_c=18.0)
```

这体现了一个很有价值的 Agent 能力：

> **失败本身也可以成为下一轮决策使用的环境反馈。**

但不要把这句话误解成：

> “所有 exception 都应该原样塞给模型。”

真实异常可能包含文件路径、SQL、内部服务名甚至敏感数据。

当前 `src/tiny_agent/runtime.py` 已经被后续 Stage 07 加固，会把意外异常变成脱敏后的 observation。Stage 01 的 lesson 是理解“可恢复失败可以进入 loop”，完整 error taxonomy 在 Stage 07 再学。

---

## 9. 先用假的模型，把真的 Runtime 看清楚

现在我们终于可以解释为什么 `minimal_react_runtime.py` 默认不用真实 OpenAI。

它里面有一个：

```python
class ScriptedTravelModel:
    ...
```

它会固定返回：

```text
turn 1 -> get_mock_weather("Tokyo")
turn 2 -> celsius_to_fahrenheit(18.0)
turn 3 -> final answer
```

这不是为了模拟“模型智能”。

恰恰相反，我们故意把模型智能拿掉，才能看清 Runtime。

### 我们现在真正想测试的是：

```text
Runtime 是否调用 Tool？
Observation 是否追加到消息历史？
第二轮是否能看到第一轮结果？
最终回答是否让 loop 正确停止？
step 是否正确计数？
```

这些都不需要真实 LLM。

运行：

```bash
python stages/01-react-runtime/code/minimal_react_runtime.py
```

新版示例会打印类似：

```text
01. USER        查询东京课程模拟天气，并换算为华氏度。
02. ACTION      get_mock_weather({'city': 'Tokyo'}) [id=call_weather]
03. OBSERVATION get_mock_weather -> {"city":"Tokyo","temperature_c":18.0,...}
04. ACTION      celsius_to_fahrenheit({'temperature_c': 18.0}) [id=call_convert]
05. OBSERVATION celsius_to_fahrenheit -> 64.4
06. ASSISTANT   东京课程模拟天气为 18°C，约 64.4°F。
```

你现在应该把它看成一条**执行轨迹**，而不只是“聊天记录”。

---

## 10. ReAct 和 Workflow 不要急着二选一

一个常见误区是：

```text
Agent 比 Workflow 高级
```

所以所有步骤都尽量让模型决定。

这通常不是好工程。

如果路径已知：

```text
parse -> validate -> retrieve -> rerank -> answer
```

那就直接写确定性 Workflow。

如果下一步必须依赖环境反馈和语义判断：

```text
当前 state
   ↓
模型判断下一 action
   ↓
环境返回 observation
   ↓
模型再判断
```

Agent loop 才真正有价值。

经验上应该问：

> **这里是真的存在语义不确定性，还是我们只是懒得写 if/else？**

Stage 02 会从这个问题继续展开。

---

## 11. 本章结束时，不要只背“Reason-Act-Observe”

真正应该留下来的，是这条工程链：

```text
Model
  只负责提出 next decision
        ↓
Runtime
  拥有 loop / execution / stopping
        ↓
Tool
  真正与环境交互
        ↓
Observation
  成为下一轮可用信息
        ↓
Model
  根据新事实再次判断
```

如果这条关系已经非常清楚，下一章我们就可以开始把 Stage 00 的手写 loop 一层层拆成真正的 Runtime architecture。

---

## 本章检查

试着不用术语回答：

1. 为什么第一次 `get_mock_weather` 之后还需要再次调用模型？
2. ToolCall 和 Tool execution 为什么不是一回事？
3. Observation 为什么应该进入下一轮，而不是只打印到日志？
4. Runtime 为什么必须拥有 stopping condition？
5. `ModelResponse()` 为什么应该被视为 contract violation？
6. FakeModel 为什么不是“假的 Agent 教学”，反而是理解 Runtime 的好工具？
7. ReAct 为什么不要求输出 hidden chain-of-thought？
8. 什么样的任务更适合确定性 Workflow，而不是 Agent loop？