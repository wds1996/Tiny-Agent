# MCP 2026 Advanced Extensions — Tasks、MRTR、Apps 与 Governance

Stage 05 主线先学习稳定的 MCP core；这一份 advanced note 专门覆盖 2026-07-28 generation 中尤其重要的扩展能力。

## 1. Extensions framework

新 capability 可以在 core protocol 之外，通过 reverse-DNS extension identifier 演进，并显式协商双方是否支持。

这让：

```text
stateless stable core
        +
fast-evolving optional capabilities
```

可以同时成立，而不是让每个实验特性都永久膨胀 core protocol。

---

## 2. Tasks extension

Long-running Tool work 不一定要让一个 `tools/call` 阻塞到任务完成。

概念流程：

```text
client opts into io.modelcontextprotocol/tasks
        ↓
tools/call
        ↓
server returns task handle
        ↓
tasks/get / tasks/update / tasks/cancel
        ↓
terminal result
```

Task state 属于 extension/application；2026 core 本身仍然保持 stateless。

---

## 3. Multi Round-Trip Requests（MRTR）

旧 session-oriented server-to-client request model 与 stateless core 不自然匹配。

MRTR 把 elicitation/sampling 一类 workflow 重构成显式 multi-round request/response，而不要求永久持有 bidirectional protocol session。

核心思想：

```text
request
-> input required
-> explicit response with requested input
-> continue/retry
-> result
```

---

## 4. MCP Apps

MCP Apps 允许 server 把 interactive UI 与 capability 关联起来。

Host 在 sandboxed boundary 中 render UI，并把 action 重新送回 governed MCP call，而不是给页面任意 authority。

安全原则始终是：

```text
rendered UI
!= authorization
```

---

## 5. Header-based routing 与 cacheable catalogs

现代 HTTP request 暴露 method/tool identity，使 gateway 能在无需深度解析任意 argument 的前提下做 routing/authorization。

Capability list 的 deterministic ordering 与 cache hint，也有助于 client 保持稳定、可缓存的 capability catalog。

这与 Stage 07 直接相连：server 可以拥有很多 capability，但进入 model context 的仍应只是当前需要的 subset。

---

## 6. Enterprise authorization 方向

2026 release 进一步对齐标准 OAuth/OIDC practice，并从 Dynamic Client Registration 转向 client metadata documents 等更标准的 deployment direction。

始终分开：

```text
protocol discovery
authentication
authorization
```

它们不是一个问题的三个叫法。

---

## 7. 与 Tiny-Agent long-horizon work 的关系

MCP Tasks 表达的是：

```text
long-running remote capability execution
```

Tiny-Agent Stage 14 处理的是更大的 application harness 问题：

```text
local TaskLedger
durable run ownership
workspace artifacts
context compaction
evaluator / repair
sandbox rehydration
```

二者是相邻层，而不是同一 abstraction。

同一个 deep-research run 可能同时存在：

```text
MCP task handle
service run_id
Agent thread/checkpoint
TaskLedger task
workspace artifact IDs
```

把它们都叫 `task_id`，是给未来 debug 留下彩蛋。

---

## References

- 2026-07-28 release — https://blog.modelcontextprotocol.io/posts/2026-07-28/
- current MCP roadmap — https://blog.modelcontextprotocol.io/posts/mcp-roadmap/

---

## Exercise

设计一个 Agent，它需要调用一个 long-running MCP data-processing Tool。

分别标出并解释：

1. MCP task handle/state；
2. Tiny-Agent service run ID；
3. Agent thread/checkpoint ID；
4. workspace artifact IDs；
5. authenticated principal/tenant；
6. 每一层各自的 timeout/cancellation semantics。

最后回答：

> 如果 remote MCP task 已 cancel，但 application run 仍存在，系统下一步应该由哪一层 policy 决定？