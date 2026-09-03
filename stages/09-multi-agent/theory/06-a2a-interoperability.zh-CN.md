# 06 — A2A 1.0、Agent Card 与 Interoperability

> Language: [English](06-a2a-interoperability.md) | 简体中文

Stage 05 用 MCP 解决 standardized external capability；Stage 09 解决另一个问题：

> 一个独立 Agent system 怎样发现并与另一个独立 Agent system 协作，同时不需要知道对方 private implementation？

这就是 Agent2Agent（A2A）Protocol。

本阶段目标：**A2A 1.0 specification + Python SDK 1.1.x**。

---

## 1. MCP 与 A2A 是不同 Boundary

```text
MCP: Agent/Application -> Tools / Resources / Prompts
A2A: Agent System A    -> Agent System B
```

A2A remote Agent 可以保持 opaque；caller 不需要知道 model、prompt、memory、Tool registry、orchestration graph。

---

## 2. A2A Actors

```text
User
 -> A2A Client / Client Agent
 -> A2A Server / Remote Agent
```

Remote Agent 内部甚至可以是完整 multi-Agent system，caller 不需要知道。

---

## 3. Agent Card

Agent Card 是 remote Agent 的 machine-readable discovery document，描述 identity/version、supported interfaces、capabilities/skills、input/output media type、security requirement。

可以把它理解为“机器可读名片 + service contract”，而不是 internal Tool dump。

---

## 4. A2A 1.0 Interface Shape

```text
AgentCard
└── supportedInterfaces[]
    ├── url
    ├── protocolBinding
    └── protocolVersion
```

Tiny-Agent 构造：

```python
AgentInterface(
    url="https://example.com/a2a",
    protocol_binding="JSONRPC",
    protocol_version="1.0",
)
```

Older 0.3 tutorial 使用不同 card shape，复制代码前必须核对版本。

---

## 5. Skill

Agent Card 的 skill 描述 remote Agent 擅长的 focused capability，例如 research/evidence synthesis。

它不必一一对应 internal Tool；remote Agent 自己决定怎样实现。

---

## 6. Message

`Message` 是 communication turn，包含 messageId、role、parts、可选 task/context refs、metadata/extensions。

Message 负责沟通，不一定代表最终 durable deliverable。

---

## 7. Part

Part 是 Message/Artifact 的 content unit，可承载 text、raw bytes、URL/file reference、structured data。

因此 A2A 不是只交换聊天字符串。

---

## 8. Artifact

Artifact 是 concrete task output，例如 report、image、JSON、generated file、dataset fragment。

```text
Message  = communication
Artifact = deliverable
```

有 artifact model 时，不要把所有 durable result 都埋在 conversational prose 里。

---

## 9. Stateless Response vs Task

简单交互可直接 Message；长工作可建立 stateful `Task`，拥有 ID/lifecycle，适合超过一个 HTTP request 的 Agent work。

---

## 10. Task Lifecycle

可能状态：

```text
working
completed
failed
canceled
rejected
input-required
auth-required
```

Remote Agent 可以暂停等待 input/auth，而不是只能同步 success/failure。这与 Stage 06 HITL/resumability 自然衔接。

---

## 11. Streaming / Async Collaboration

A2A 支持 request/response、stream update、long-running status、push notification，所以应理解为 Agent task protocol，而不是“HTTP function calling”。

---

## 12. A2A 1.0 与旧教程存在 Breaking Evolution

1.0 修改 operation naming、supported interface、Agent Card protocol location、stream event representation、task operations 等。

和 Stage 05 MCP 一样，version archaeology 是现代 Agent engineering 的一部分。

---

## 13. Security Boundary 仍存在

Agent Card 可声明 auth/security requirement，但 application 仍负责 credential storage、caller authorization、tenant isolation、output validation、trust policy。

Protocol compliance != correctness/trustworthiness。

---

## 14. A2A vs MCP

| Question | MCP | A2A |
|---|---|---|
| Main boundary | App/Agent -> capability/context | Agent system -> Agent system |
| Discovery | server primitives | Agent Card + skills/interfaces |
| Internal impl exposed? | Tool/resource/prompt surface | remote Agent 可 opaque |
| Long-running lifecycle | 非主要抽象 | 核心 Task concept |
| Durable deliverables | 依 Tool/resource | Artifact explicit |
| Typical use | DB/docs/Tool/service | remote specialist Agent collaboration |

两者可共存：

```text
Your Agent --A2A--> Remote Research Agent --MCP--> private search/database
```

---

## 15. 为什么本阶段只 Offline 构造 Protocol Object？

完整 A2A network server 会引入 HTTP/gRPC、authentication、task storage、long-running worker、deployment、observability、tenant isolation。

这些更适合 Stage 10 一次讲清楚，而不是塞进一个“看起来很简单”的 interoperability demo。

---

## 16. 核心心智模型

> **MCP 标准化 capability access；A2A 标准化独立 Agent system 之间的 collaboration。**

不要因为两个协议都出现 Agent 和 JSON，就把名字当成同义词。
