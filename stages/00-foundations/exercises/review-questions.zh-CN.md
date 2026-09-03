# Stage 00 复习题

这些题不是为了检查你会不会背 API，而是检查你是否真正理解 model / runtime boundary。

## 概念题

1. model provider 与 Agent runtime 有什么区别？
2. 为什么 provider-specific response object 在进入 core Agent logic 前应该 normalize？
3. 一个 `tool` message 表示什么？
4. 为什么 Structured Output 适合 software control boundary？
5. schema-constrained Structured Output 与 prompt 中写“return JSON”有什么区别？
6. Structured Output 与 Function Calling 有什么区别？
7. LLM 会直接执行 Python Tool 吗？请把完整 sequence 说明清楚。
8. Tool 的哪些部分对 model 可见，哪些部分只属于 runtime？
9. 为什么 Tool argument 必须在 execution 前 validation？
10. 为什么 Tool result 必须返回给 model？
11. 什么让一次 ToolCall 发展成 iterative tool-use loop？
12. 为什么 minimal Tool loop 仍然不是 production Agent runtime？

## 编程练习

### Exercise 1 — 增加 Division Tool

在 `../code/minimal_tool_loop.py` 中增加：

```text
divide(a, b)
```

要求：

- 拒绝 division by zero；
- 清晰表示 failure；
- 不要为了让流程“看起来成功”而返回 fake successful value。

### Exercise 2 — Unknown Tool

修改 scripted model，让它提出一个 registry 中不存在的 Tool。

观察 error 在哪里发生，并解释：为什么 registry enforcement 属于 runtime，而不是 model？

### Exercise 3 — 增加 Argument Validation

handler 执行前，检查 arguments 是否匹配 expected shape。

分别考虑：

- 缺少 argument；
- 提供 unexpected argument；
- value type 错误。

思考这些失败应该：

```text
crash?
become safe Tool observation?
ask user?
```

不同 error class 的完整设计会在 Stage 07 展开。

### Exercise 4 — 替换 Fake Model

实现真实 provider adapter，同时保持 Tool loop 本身不变。

最重要约束：

> **Provider-specific parsing 属于 adapter，不属于 `run_tool_loop`。**

如果换 provider 必须重写 Agent loop，说明 provider boundary 没有隔离好。

## 面试题

1. “Function Calling 就是 Agent。”你同意吗？为什么？
2. 如果 model 请求 `delete_database()`，是否因为 model 选择了它，runtime 就应该自动执行？
3. 公司切换 model provider 时，一个设计良好的 Agent system 理想情况下应该主要修改哪一层？
4. 为什么 Tool description 会影响 Tool-selection accuracy？
5. Stage 00 的 loop 离 production runtime 还缺哪些能力？

## 最终自检

你应该能够不用 framework 名称解释：

```text
model output
    = proposal

Tool schema
    = model-facing action contract

handler
    = runtime implementation

Tool observation
    = execution result returned to next model call

Structured Output
    != Tool Calling

model capability
    != runtime authority
```

如果这些边界已经清楚，再进入 Stage 01。