# Stage 01 — ReAct 与 Core Agent Runtime

这一阶段把 Stage 00 的基础 Tool Calling，提升成一个显式 Agent runtime，并把这个 runtime 接到真实 LLM provider。

目标不是背 framework API，而是理解绝大多数 Agent framework 最终都必须管理的核心控制循环：

```text
decide -> act -> observe -> decide again
```

Stage 01 刻意拆开两个责任：

```text
AgentRuntime                      Model Provider Adapter
------------                      ----------------------
iteration                         API request format
stopping                          provider Tool schema
execution                         provider response parsing
observations                      provider-specific configuration
runtime errors                    output normalization
```

这个分离是 Tiny-Agent 后面所有阶段的基础。

## 前置要求

先完成 [`../00-foundations/`](../00-foundations/)，或者确认你已经理解：

- message-based LLM API；
- Structured Output；
- Function / Tool Calling；
- JSON Schema Tool definitions；
- model-generated ToolCall 与真实 Python execution 的区别；
- 如何把 Tool observation 返回给 model。

## 学习目标

完成本阶段后，你应该能够：

1. 从工程角度解释 ReAct；
2. 区分 one-shot Tool Calling 与 iterative Agent loop；
3. 实现 explicit Agent runtime；
4. 解释为什么 model 不应该拥有 Tool execution authority；
5. 通过 model interface 隔离 provider-specific API；
6. 把 provider output normalize 成 internal Agent types；
7. 解释 provider adapter 的职责；
8. 解释为什么 `call_id` 必须穿过 Tool execution 后继续保留；
9. 维护 Tool registry；
10. 在适当情况下把 Tool error 作为 recoverable observation 返回；
11. 区分 serial Tool dependency 与同一 turn 中多个 independent ToolCall；
12. enforce maximum-step stopping condition；
13. 不依赖 live LLM，对 runtime / adapter 做 deterministic unit test；
14. 用真实 OpenAI model 运行同一套 provider-neutral runtime；
15. 区分 Stage 01 的 architecture principle 与 deliberate teaching simplification。

## 推荐顺序

### Part A — 理解 Agent Loop

1. `theory/01-react-and-agent-loop.md`
2. `theory/02-runtime-architecture.md`
3. `code/minimal_react_runtime.py`

### Part B — 接入真实 Model

4. `theory/03-model-provider-adapter.md`
5. `../../src/tiny_agent/models/openai.py`
6. `../../tests/test_openai_adapter.py`
7. `code/openai_multi_tool_agent.py`

### Part C — 理解边界

8. `theory/04-scope-and-production-limitations.md`
9. `../../tests/test_runtime_edges.py`
10. `../../tests/test_openai_adapter_edges.py`

### Part D — Review / Extend

11. 阅读 `../../src/tiny_agent/` 的 integrated implementation；
12. `exercises/review-questions.md`
13. `exercises/provider-adapter-exercises.md`

中文理论与练习使用同目录 `*.zh-CN.md`，所有 `.py` 与测试仍共用英文教程同一份真实实现。

## Stage Architecture

```text
                         +----------------------+
                         |       User Task      |
                         +----------+-----------+
                                    |
                                    v
                         +----------------------+
                         |     AgentRuntime     |
                         +----------+-----------+
                                    |
                           provider-neutral
                              Model protocol
                                    |
                                    v
                         +----------------------+
                         | Provider Adapter     |
                         | OpenAIResponsesModel |
                         +----------+-----------+
                                    |
                             Responses API
                                    |
                                    v
                         +----------------------+
                         |   Model Decision     |
                         +----------+-----------+
                                    |
                    +---------------+---------------+
                    |                               |
              final answer                    function call(s)
                    |                               |
                    v                               v
                   END                      +---------------+
                                            | ToolRegistry  |
                                            +-------+-------+
                                                    |
                                                    v
                                             Python Handler
                                                    |
                                                    v
                                               Observation
                                                    |
                                                    +-------> next model turn
```

## 为什么单独做成一个 Stage

Stage 00 已经展示 Tool Calling 可以反复发生；Stage 01 开始把 runtime responsibility 显式化：

- iteration；
- stopping；
- normalized response；
- execution ownership；
- provider adapters；
- request / response protocol translation；
- ToolCall correlation ID；
- error observation；
- deterministic testing。

这些责任标志着“Function Calling demo”和“Agent runtime”之间第一次真正的 architecture boundary。

## Implementation Layers

### Educational Snapshot

`code/minimal_react_runtime.py` 刻意保持 compact / self-contained，应该可以从第一行一直读到最后一行。

### Real Provider Example

`code/openai_multi_tool_agent.py` 使用相同 architecture，接入真实 OpenAI Responses API model，并提供两个 arithmetic Tools。

example task：

```text
Calculate (23 * 17) + 41 and explain the result.
```

典型 trajectory：

```text
multiply(23, 17)
      |
      v
     391
      |
      v
add(391, 41)
      |
      v
     432
      |
      v
final answer
```

runtime 没有 hard-code 这条 sequence，由 model 决定每一步何时使用 Tool。

### Latest Library Implementation

reusable implementation 分散在：

- `../../src/tiny_agent/types.py`
- `../../src/tiny_agent/tool.py`
- `../../src/tiny_agent/runtime.py`
- `../../src/tiny_agent/models/openai.py`
- `../../tests/test_runtime.py`
- `../../tests/test_runtime_edges.py`
- `../../tests/test_openai_adapter.py`
- `../../tests/test_openai_adapter_edges.py`

stage snapshot 与 `src/` 职责不同：

```text
stage code
    -> 教最小机制

src/
    -> 随后续 Stage 继续演化的 reusable implementation
```

## 运行真实 Provider Example

安装：

```bash
pip install -e ".[openai]"
```

设置 API key：

```bash
export OPENAI_API_KEY="your-key"
```

运行：

```bash
python stages/01-react-runtime/code/openai_multi_tool_agent.py
```

教学 example 默认使用 `gpt-5.6-luna`，reasoning effort 为 `none`，让这一阶段聚焦 transparent / stateless provider-adapter boundary。

provider-native conversation state 与 persisted reasoning 会在后续 stage 专门引入。

## 重要：这仍然不是 Production Runtime

进入下一阶段前必须阅读：

`theory/04-scope-and-production-limitations.md`

Stage 01 **尚未提供**：

- local JSON-Schema validation；
- safe error redaction；
- real concurrent Tool execution；
- retries；
- timeouts；
- permissions；
- checkpoints；
- tracing；
- evaluation。

这些不是被教程藏起来了，而是刻意推迟到合适阶段展开。

## 完成检查

你应该能够精确解释：

> **Model 提出 next action；runtime 拥有 execution、observation、state transition 与 stopping。**

以及：

> **Provider adapter 在 Tiny-Agent internal protocol 与 provider wire protocol 之间做 translation，但不拥有 Agent loop。**

还应该能不看代码画出：

```text
Tool schema
  -> provider function definition
  -> model function_call
  -> Tiny-Agent ToolCall
  -> Python Tool execution
  -> Tiny-Agent observation
  -> provider function_call_output
  -> next model decision
```

最后，你应该能解释为什么一个 early implementation 可以在**概念上正确**，同时又**明确不具备生产完整性**。