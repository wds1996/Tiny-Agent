# 02 — Core Runtime Architecture

## 1. 为什么这么早就需要讲 Architecture？

一个 toy Agent 完全可以写在单文件里。

但教学代码一旦希望真正可复用，最重要的事情之一就是把 component responsibility 明确拆开。

Tiny-Agent 在这一阶段分离四个核心 concern：

```text
Model interface
Tool interface + registry
Normalized response types
Agent runtime
```

这套设计刻意保持小。

我们不是在第一阶段复刻一个大型 Agent framework，而是在建立后续功能可以稳定扩展的最小 boundary。

## 2. High-Level Architecture

```text
                    +-------------------+
                    |       User        |
                    +---------+---------+
                              |
                              v
                    +-------------------+
                    |   AgentRuntime    |
                    +----+---------+----+
                         |         |
                         |         |
                         v         v
                  +----------+   +--------------+
                  |  Model   |   | ToolRegistry |
                  +----+-----+   +------+-------+
                       |                |
                       v                v
                ModelResponse        Tool handler
                /           \           |
        Tool calls        final          v
             |           answer      observation
             +---------------+-----------+
                             |
                             v
                       next runtime step
```

## 3. 为什么 `Model` 是 Interface

Agent runtime 应该依赖一个小而稳定的 internal contract，而不是直接依赖 provider SDK。

概念上：

```python
class Model(Protocol):
    def generate(
        self,
        messages,
        tools,
    ) -> ModelResponse:
        ...
```

provider adapter 位于 interface 后面：

```text
                    +----------------+
AgentRuntime -----> | Model protocol |
                    +-------+--------+
                            ^
             +--------------+--------------+
             |              |              |
        OpenAIAdapter   QwenAdapter   FakeModel
```

好处：

- 切换 provider 不需要重写 runtime；
- test 可以使用 deterministic fake model；
- provider-specific parsing 被隔离；
- runtime 有稳定 internal vocabulary。

## 4. 为什么要 Normalize Model Response

不同 provider 对 ToolCall 的 representation 可能完全不同。

core runtime 不应该知道这些 wire-format detail。

Tiny-Agent 把 provider response 转成自己的 internal type，例如：

```python
@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict

@dataclass
class ModelResponse:
    final_answer: str | None
    tool_calls: list[ToolCall]
```

这形成 normalization boundary：

```text
Provider response
      |
      v
Provider adapter
      |
      v
ModelResponse
      |
      v
AgentRuntime
```

这样 runtime 只需要理解一个 protocol，而不是每个 provider 都写一套分支。

## 5. 为什么 Tool 不只是 Callable

Tool 同时包含 model-facing contract 与 runtime-facing implementation：

```text
Model-facing                         Runtime-facing
------------                         --------------
name                                 callable
description                          validation
parameter schema                     execution
                                     error handling
```

registry 把 model-visible name 映射到真实 implementation：

```python
{
    "calculator": calculator_tool,
    "search": search_tool,
}
```

runtime 绝不能直接信任 model-generated string 去调用任意 Python symbol。

## 6. 为什么需要 `ToolRegistry`

没有 registry 时，很容易长成：

```python
if tool_name == "calculator":
    ...
elif tool_name == "weather":
    ...
elif tool_name == "search":
    ...
```

这样 Tool routing、validation、schema generation 和 execution 都被耦合进 Agent loop。

`ToolRegistry` 把这些职责集中起来：

- registration；
- duplicate-name checks；
- schema export；
- lookup；
- execution。

后续它还会自然成为这些功能的 integration point：

- permissions；
- tracing；
- timeouts；
- MCP-discovered Tools；
- Tool metadata；
- approval policy。

## 7. Runtime Responsibility

runtime 不只是一个 `while` loop。

即使在最小版本，它已经拥有 policy：

```text
initialize task messages
call model
interpret normalized response
execute Tools
append observations
count steps
stop on final answer
stop on step budget
surface contract violations
```

未来会继续增加：

```text
state persistence
retry policies
human approval
permissions
tracing
evaluation hooks
streaming
cancellation
cost budgets
```

## 8. 为什么 `AgentResult` 还保留 Messages

返回 execution messages 很有帮助，因为它们构成最原始的 trajectory：

```text
user input
assistant Tool proposal
Tool observation
assistant next proposal
...
final answer
```

这还不算完整 observability，但至少让 tests / developer 能检查到底发生了什么。

Stage 08 会进一步引入 explicit trace / span object，而不是永远把 conversation messages 当 tracing system。

## 9. 为什么 Tool Exception 有时会变成 Observation

当前 teaching runtime 会捕获 Tool exception，并把它转成 string observation。

它是在展示一个重要概念：

> external failure 有时是 model 可以利用的 recoverable environment feedback。

但 production runtime 不应该无差别 catch 每一个 exception。

后续更合理的 hierarchy 可能是：

```text
ToolError
├── InvalidArguments
├── RetryableToolError
├── TimeoutError
├── PermissionDenied
└── FatalToolError
```

不同 failure class 应该对应不同 policy。

## 10. Deterministic Unit Test

fake model 可以 scripted：

```text
turn 1 -> calculator ToolCall
turn 2 -> final answer
```

这样 runtime test 不依赖：

- network access；
- API key；
- sampling randomness；
- token cost；
- provider outage。

Agent project 需要两类测试：

### Unit Test

验证 runtime deterministic behavior。

### Integration / Evaluation Test

使用真实 model 测量真实 Agent quality。

两者不能互相替代。

## 11. 下一练习的 Design Rule

一个真实 provider adapter 必须满足现有 `Model` interface，**且不能要求修改 `AgentRuntime`**。

如果增加 provider 需要重写 runtime，说明 abstraction boundary 设计错了。

## 12. 关键结论

- provider-specific SDK code 留在 core runtime 之外；
- provider response normalize 成 internal types；
- ToolRegistry 是 execution boundary；
- runtime 拥有 iteration 与 policy；
- 即使真实系统使用 stochastic LLM，也要保留 deterministic unit test；
- interface 要允许后续 stage 扩展，而不是为了增加功能把最小机制全部抹掉。