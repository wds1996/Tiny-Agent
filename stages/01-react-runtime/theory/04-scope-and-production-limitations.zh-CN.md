# 04 — 这版 Runtime 哪里还会坏？从“概念正确”走向 Production Thinking

> Language: [English](04-scope-and-production-limitations.md) | 简体中文

到这里，我们已经有了一套结构上很干净的最小 Runtime：

```text
Model 提出 ToolCall
    ↓
Adapter 归一化
    ↓
Runtime 控制 loop
    ↓
ToolRegistry 执行
    ↓
Observation 回到下一轮
```

这套架构是对的。

但“架构边界正确”不等于“生产可用”。

这是很多 Agent 教程最容易误导初学者的地方：十几行 demo 跑通后，教程往往直接跳到“你已经构建了一个 Agent”。

更专业的说法应该是：

> **我们已经构建了一个能把核心控制关系讲清楚的 Agent Runtime，但它仍然缺少大量生产约束。**

这一章不罗列“以后还要学很多东西”。

我们直接拿失败场景来拆。

---

## 1. 失败场景一：模型永远不结束

假设模型每一轮都返回：

```text
get_mock_weather(city="Tokyo")
```

Runtime 如果写成：

```python
while True:
    ...
```

就会无限循环。

Stage 01 已经加了：

```python
max_steps
```

并且 `tests/test_runtime_edges.py` 里用一个 `EndlessToolModel` 明确验证：

```python
with pytest.raises(RuntimeError, match="exceeded max_steps=2"):
    runtime.run(...)
```

这说明 `max_steps` 是**已经解决的 Stage 01 boundary**。

但它只回答：

```text
最多允许多少轮？
```

它没有回答：

```text
一个 Tool 最多执行多久？
最多调用多少个 Tool？
最多花多少 Token / 钱？
用户取消后怎样停止？
```

所以后面还需要 timeout、Tool-call budget、cost budget、cancellation 等机制。

---

## 2. 失败场景二：模型参数是错的

模型可能提出：

```text
celsius_to_fahrenheit(
    temperature_c="eighteen"
)
```

即使 provider 使用 strict schema，应用也不应该把：

```text
provider 说它合法
```

当成：

```text
Runtime 永远不需要验证
```

为什么？

因为以后可能出现：

```text
另一个 provider
手写 ToolCall fixture
旧 checkpoint
MCP Tool
schema drift
测试代码直接构造 ToolCall
```

所以生产 Runtime 还需要**本地 application-side validation**。

Stage 01 的 teaching snapshot 没把 JSON Schema validator 塞进最小 loop，是为了先看清控制关系。

这属于“故意暂缓”，不是“这个问题不存在”。

---

## 3. 失败场景三：Tool 抛出的异常里有内部秘密

早期教程经常这样写：

```python
except Exception as exc:
    observation = str(exc)
```

这很方便，因为模型可以看到失败原因并尝试恢复。

但异常内容可能是：

```text
/opt/company/private/customer_123/data.csv
postgresql://internal-db-07/...
SQL syntax near customer_secret
AWS bucket name
内部 service URL
```

这些不应该原样进入 model context。

所以真实系统需要两份错误信息：

```text
给模型看的 safe observation
        !=
给开发者看的 detailed diagnostic
```

当前 `src/tiny_agent/runtime.py` 已经被后续 Stage 07 加固：意外 Tool exception 会转成脱敏后的 `ToolFailure[...]` observation，而详细信息留在更合适的诊断层。

这就是为什么教学快照和最终 library 不应该逐字一样。

---

## 4. 失败场景四：模型调用了一个根本不应该给它的 Tool

假设应用注册：

```text
read_weather
send_email
refund_payment
delete_database
```

Stage 01 的最小 Runtime 只要 Tool 在 Registry 里，模型提出后就会执行。

这显然不够。

真实系统需要区分：

```text
可见
!=
可执行
```

甚至：

```text
模型知道这个 Tool 存在
!=
当前用户有权执行
!=
当前这次调用满足 policy
!=
不需要人工批准
```

例如：

```text
read_weather
    -> 自动执行

send_email
    -> 可能需要 policy / approval

delete_database
    -> 默认禁止
```

这些能力会在 Stage 06/07 的 HITL、permission、authorization、Tool governance 中系统加入。

最关键的 architecture principle 已经在 Stage 01 放对了：

> **Tool execution 属于 Runtime，而不是模型。**

只有 ownership 放对，后续 permission 才有地方生效。

---

## 5. 失败场景五：Tool 卡住了

假设 Tool：

```python
def get_weather(city):
    return remote_api(city)
```

远程服务 60 秒都没返回。

`max_steps=5` 完全帮不上忙，因为 Agent 连第一步都没结束。

这时需要的是：

```text
per-Tool timeout
request timeout
cancellation
async execution
```

注意：

```text
step budget
!=
time budget
```

这是两个完全不同的控制维度。

后面 Reliability / Production Stage 会分别处理。

---

## 6. 失败场景六：模型同一轮提出多个 ToolCall

模型可能一次返回：

```text
get_weather(Tokyo)
get_weather(Paris)
get_weather(New York)
```

Stage 01 已经能表示：

```python
ModelResponse(tool_calls=[a, b, c])
```

但 Runtime 当前执行：

```python
for call in response.tool_calls:
    execute(call)
```

也就是顺序执行。

如果三个调用互相独立，生产系统可能希望并发。

但一旦并发，就会立刻出现：

```text
最多并发几个？
其中一个失败怎么办？
其它 call 要取消吗？
结果怎样按 call_id 聚合？
谁先返回是否影响 transcript 顺序？
```

所以：

```text
multiple ToolCalls
```

只是**决策表示能力**；

```text
concurrent execution
```

是另一套 Runtime execution semantics。

不要把它们混成一个 feature。

---

## 7. 失败场景七：Provider state 和 Runtime state 开始混在一起

Stage 00 已经见过：

```python
previous_response_id=...
```

它可以让 provider 继续之前的 Responses 上下文。

Stage 01 当前则主要重放 Tiny-Agent transcript。

为什么不现在就把两者混在一起？

因为你很快会遇到这些问题：

```text
previous_response_id 是谁持久化？
服务重启后还有效吗？
一个 thread 能不能同时有两个 run？
checkpoint 和 provider state 谁是 source of truth？
Tool observation 存在哪里？
resume 时哪些 reasoning item 必须恢复？
```

如果你连：

```text
conversation history
provider conversation state
Runtime state
checkpoint
long-term memory
```

都还没区分，就提前接 session API，只会把概念搅在一起。

所以 Stage 03 / 06 再专门引入 state/persistence。

---

## 8. 失败场景八：只看 `messages`，调试开始不够用了

Stage 01 的：

```python
AgentResult.messages
```

很好用。

它能告诉你：

```text
User
Action
Observation
Action
Observation
Final
```

但生产系统还要问：

```text
每次模型调用耗时多少？
Tool 调用耗时多少？
Token 使用是多少？
哪个 step 最慢？
哪类 Tool failure 最多？
一次 run 的 request_id 是什么？
哪个用户触发？
最终成功率如何？
```

这些需要真正的：

```text
logging
tracing
metrics
evaluation
```

不能永远把聊天 transcript 当 observability system。

Stage 08 会系统展开。

---

## 9. 失败场景九：最终答案是对的，但 Agent 过程可能是错的

假设题目：

```text
请使用 weather Tool 查询东京模拟天气。
```

两个 Agent 都回答：

```text
18°C
```

Agent A：

```text
ToolCall -> observation 18 -> final
```

Agent B：

```text
直接猜 18 -> final
```

如果只检查 final answer，两者都“通过”。

但 B 已经违反任务约束。

所以 Agent evaluation 至少有两层：

```text
answer quality
trajectory quality
```

Stage 01 先通过 `AgentResult.messages` 让 trajectory 可见；Stage 08 再正式做 evaluator。

---

## 10. 为什么不在 Stage 01 一次把这些都写完？

有两种教程都很糟糕。

### 第一种：过度简化

```text
10 行 Tool Calling demo
    ↓
“恭喜，你已经完成 production Agent”
```

它会让读者高估自己真正理解的东西。

### 第二种：第一天就把所有 production concerns 混进来

```text
async
retry
RBAC
checkpoint
tracing
Redis
Postgres
queue
sandbox
multi-agent
```

一起塞进第一个 Runtime。

代码可能很“企业级”，但读者根本看不见 Agent loop 本身。

高质量教学应该采用：

> **Progressive Disclosure：先把一个机制讲透，再明确指出它还缺什么，以及以后在哪里补。**

所以 Tiny-Agent 的路线是：

```text
Stage 00  LLM / Tool Calling 基础
   ↓
Stage 01  显式 Agent Runtime
   ↓
Stage 02  Workflow / Routing / Planning
   ↓
Stage 03  State / Orchestration
   ↓
Stage 06  Persistence / HITL
   ↓
Stage 07  Reliability / Safety
   ↓
Stage 08  Evaluation / Observability
   ↓
Stage 10  Production Deployment
```

不是“前面写错了，后面重写”，而是同一个 boundary 逐步变强。

---

## 11. 哪些是长期原则，哪些只是 Stage 01 简化？

### 应该一直保留的 architecture principles

```text
模型提出，Runtime 执行
Provider Adapter 不拥有 Agent loop
provider output 先 normalize
ToolCall 和 observation 用 correlation ID 关联
Runtime 必须有明确 stopping control
Tool capability 通过 Registry / execution boundary 进入真实世界
可测试的控制逻辑应该支持 deterministic tests
```

### Stage 01 的教学简化

```text
只有 max_steps，没有完整 budget system
Tool args 还没有完整 local JSON Schema validation
同步 Tool 为主
没有 permission / approval
没有 retry / timeout policy
没有 checkpoint / resume
没有正式 trace / metrics / evaluator
provider state 处理非常保守
```

学完以后，最危险的情况不是“你不知道这些功能怎么写”。

而是：

> **你不知道哪些东西现在根本还没有。**

所以一定要能清楚说出这张边界表。

---

## 12. Stage 01 的真正结课标准

现在回头看，我们不是只学了一个 `while` loop。

我们已经建立：

```text
Model boundary
Provider Adapter
normalized ToolCall / ModelResponse
ToolRegistry
AgentRuntime
Observation loop
call_id correlation
step bound
deterministic Runtime testing
```

同时又知道：

```text
这些 != production completeness
```

这才是一个高质量基础教程应该达到的状态：

> **不仅告诉你“怎么写”，还告诉你“为什么这样写”“这个设计解决了什么”“它还没有解决什么”。**

下一阶段会继续追问一个新的问题：

> **既然 Runtime 已经可以让模型自由选择下一步，那是不是所有任务都应该写成 Agent loop？**

答案当然不是。

这就是 Stage 02 的起点。