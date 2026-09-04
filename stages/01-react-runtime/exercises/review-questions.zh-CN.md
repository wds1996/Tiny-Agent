# Stage 01 综合练习：不要背 Runtime，把它重新造一遍

> Language: [English](review-questions.md) | 简体中文

这份练习的目标不是检查你记住了多少术语。

如果你真的理解 Stage 01，应该能够做到三件事：

1. 不看源码也能画出 Runtime 的控制路径；
2. 给出一段有 bug 的 Agent loop，能指出职责混乱在哪里；
3. 自己重新实现一个小型 Runtime，并用 FakeModel 把它测试清楚。

---

## Part A — 先用自己的话解释

不要引用 README 原句，尽量结合代码回答。

1. Stage 00 的 Tool loop 已经能反复调用模型，为什么 Stage 01 还要抽出 `AgentRuntime`？
2. `ToolCall` 表示的是“模型已经执行了一个 Tool”，还是“模型提出了一个执行提议”？为什么？
3. `Observation` 为什么必须进入下一轮模型上下文？
4. 为什么 `Model.generate()` 应该只代表一次 model turn？
5. 如果 Provider Adapter 自己完成 `model -> Tool -> model -> Tool` 整个循环，会破坏哪些后续能力？
6. `ModelResponse` 为什么值得作为 Tiny-Agent 自己的内部类型？
7. `ToolRegistry` 除了减少 `if/elif`，还建立了什么边界？
8. `call_id` / `ToolCall.id` 在多 ToolCall 场景解决什么问题？
9. 为什么同一轮多个 ToolCall 不等于 Python handler 已并发执行？
10. `max_steps` 能防止什么？它防不了什么？
11. 为什么 FakeModel 是 Runtime 单元测试的重要工具？
12. 为什么真实模型 evaluation 不能替代 deterministic unit test？
13. 为什么 ReAct-style Runtime 不需要暴露完整 hidden chain-of-thought？
14. “Tool 被模型看见”为什么不等于“Tool 被授权执行”？
15. 为什么最终答案正确仍然不能证明 Agent trajectory 正确？

---

## Part B — 手工追踪一次 Runtime

给定用户请求：

```text
查询东京课程模拟天气，并换算成华氏度。
```

模型第一轮返回：

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

Tool 返回：

```json
{
  "city": "Tokyo",
  "temperature_c": 18.0,
  "condition": "cloudy"
}
```

请你手写出：

1. Runtime 应追加的 assistant ToolCall message；
2. Runtime 应追加的 Tool observation message；
3. 第二轮 `model.generate(messages, tools)` 能看到的关键新信息；
4. 第二轮合理的 `ModelResponse`；
5. 为什么 `call_weather` 不能丢。

然后继续追踪到最终答案。

---

## Part C — Coding Lab 1：从零实现最小 Runtime

不要复制 `minimal_react_runtime.py`。

自己实现：

```text
ToolCall
ModelResponse
Model Protocol
Tool
ToolRegistry
AgentResult
AgentRuntime
```

最少要求：

```text
支持 ToolCall
支持 final answer
支持 max_steps
未知 Tool 绝不能被执行，失败处理必须明确
保留 action / observation trajectory
模型返回空 response 时明确报错
```

对于未知 Tool，请在这个练习里明确选择一种策略并写在代码注释中：要么直接终止本次运行，要么返回一条有界、脱敏的失败 Observation，让下一轮模型有机会恢复。无论选哪种，都不能“猜一个最相似的 Python 函数”，更不能按模型给出的字符串动态执行任意函数。

先只用 FakeModel。

### 验收任务

```text
turn 1 -> get_mock_weather("Tokyo")
turn 2 -> celsius_to_fahrenheit(18.0)
turn 3 -> final answer
```

最终断言：

```text
steps == 3
messages 中存在两个 ToolCall
messages 中存在两个 observation
最终 output 包含 18°C / 64.4°F
```

---

## Part D — Coding Lab 2：让失败成为可恢复 observation

构造一个 FakeModel：

```text
turn 1
  -> celsius_to_fahrenheit(temperature_c="bad")

turn 2
  -> 看到 safe ToolFailure 后改成 temperature_c=18.0

turn 3
  -> final answer
```

要求：

- Runtime 不因为第一次可恢复 Tool failure 整体 crash；
- observation 不应该泄露完整 stack trace；
- 第二轮模型能看见失败 observation；
- 最终成功结束。

然后回答：

> 什么错误适合进入 model observation，什么错误应该直接终止 Runtime？

你现在不需要设计完整 taxonomy，但必须意识到“所有 exception 都返回模型”不是正确答案。

---

## Part E — Coding Lab 3：证明 `max_steps` 真的是 hard boundary

写：

```python
class EndlessToolModel:
    ...
```

让它每一轮都调用：

```text
echo(value="again")
```

运行：

```python
AgentRuntime(
    model=EndlessToolModel(),
    tools=...,
    max_steps=2,
)
```

预期：

```text
RuntimeError: Agent exceeded max_steps=2
```

然后列出至少五种 `max_steps` 防不了的风险。

---

## Part F — Coding Lab 4：同一轮多个 ToolCall

让 FakeModel 在同一个 `ModelResponse` 中返回两个彼此独立、且都合法的调用：

```text
celsius_to_fahrenheit(18.0)
celsius_to_fahrenheit(20.0)
```

验证：

```text
两个 call 都被记录
两个 observation 都保留各自 call_id
下一轮 model 能看到 64.4 和 68.0 两个结果
```

然后修改转换 Tool 的 handler，让每次执行都 `sleep(1)`。

观察 Stage 01 Runtime 仍然顺序执行。

回答：

> 模型一次返回两个 ToolCall 和 Runtime 并发执行两个 Tool，为什么是两件不同的事情？

这里故意使用两个都有效的独立调用，是为了让实验只测试“multiple ToolCalls 与并发”的区别，而不是额外混进一个无关的 Tool failure。

---

## Part G — Coding Lab 5：把真实 OpenAI 接进来

安装：

```bash
python -m pip install -e ".[openai]"
export OPENAI_API_KEY="..."
```

运行：

```bash
python stages/01-react-runtime/code/openai_multi_tool_agent.py
```

记录一次真实 trajectory：

```text
user input
model action(s)
Tool arguments
observation(s)
final answer
step count
```

然后回答：

1. 哪些部分是 Runtime deterministic behavior？
2. 哪些部分是 model decision？
3. 如果模型没有完全按照你预测的 Tool 顺序走，但最终 contract 满足，算不算 Runtime bug？
4. 如果模型完全没有使用要求的 Tool，却碰巧答对，应该怎样评价？

---

## Part H — 阅读真正的测试，把 assertion 当成规范

阅读：

```text
tests/test_runtime.py
tests/test_runtime_edges.py
```

不要只看测试名字。

对每个 test 写一句：

```text
“这个 test 在保护 Runtime 的哪条不变量？”
```

至少应该识别：

```text
Tool execution -> observation -> next turn
max_steps
safe Tool failure observation
invalid empty ModelResponse rejection
```

---

## Part I — Architecture Debugging

下面是一段故意写坏的设计：

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

指出至少六个 architecture 问题。

可能涉及：

```text
provider coupling
Tool routing coupling
protocol parsing
execution authority
lack of stopping
lack of validation
lack of test seam
lack of observation abstraction
```

然后画出你会怎样拆。

---

## Part J — Final Challenge：做一个真正属于你自己的小 Runtime

不要继续用旅行助手。

自己选择一个场景，例如：

```text
代码助手
论文检索助手
文件整理助手
机器人任务助手
数据分析助手
```

至少设计三个 Tool：

```text
一个只读 Tool
一个计算 / 转换 Tool
一个可能失败的 Tool
```

必须展示四类 trajectory：

1. 不需要 Tool，直接 final answer；
2. 单 Tool task；
3. 串行两步以上 Tool task；
4. Tool failure 后恢复或安全停止。

并为 Runtime 写 deterministic tests。

### 最终报告不要只贴代码

请解释：

```text
为什么这些 Tool 粒度这样设计？
哪些逻辑属于 Runtime？
哪些逻辑属于 Adapter？
哪些逻辑属于 Tool handler？
哪些 failure 目前仍未解决？
下一步最值得加入哪一个 production capability？为什么？
```

如果你能完成这个 challenge，并且解释清楚每个 boundary，Stage 01 才算真正内化。

---

# 面试式问题

最后尝试口头回答：

1. 请从用户输入开始，完整描述一次 ToolCall 到下一轮 model input 的生命周期。
2. 为什么 Provider Adapter 不应该拥有 Agent loop？
3. 为什么 `call_id` 是 correlation ID，而不是普通 metadata？
4. 为什么 ToolRegistry 是执行边界，而不仅是一个 dict？
5. 怎样在不调用真实 LLM 的情况下测试 Agent Runtime？
6. 如果公司从 OpenAI 换到 Qwen，理想情况下哪些文件应该变化？哪些不应该变化？
7. 为什么 multiple ToolCalls 和 concurrent Tool execution 不是一回事？
8. 为什么 `max_steps` 是必要但远远不充分的 stopping policy？
9. 一个 Stage 01 Runtime 距离 production 还缺哪些类别的能力？
10. 为什么“能跑”不是 Agent architecture 设计完成的标准？
