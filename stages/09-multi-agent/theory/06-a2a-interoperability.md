# 06 — A2A 1.0, Agent Cards & Interoperability

Stage 05 introduced MCP for standardized external capabilities.

Stage 09 introduces a different interoperability problem:

> How can one independent Agent system discover and collaborate with another independent Agent system without knowing its private implementation?

That is the problem addressed by the Agent2Agent (A2A) Protocol.

This stage targets the **A2A 1.0 specification** and the current **1.1.x Python SDK** line.

Official resources:

- https://a2a-protocol.org/latest/
- https://a2a-protocol.org/latest/specification/
- https://a2a-protocol.org/latest/topics/key-concepts/
- https://a2a-protocol.org/latest/whats-new-v1/
- https://a2a-protocol.org/latest/sdk/python/api/

---

## 1. MCP and A2A solve different boundaries

A simplified mental model:

```text
MCP
Agent/Application
      |
      v
Tools / Resources / Prompts
```

versus:

```text
A2A
Agent System A
      |
      v
Agent System B
```

A2A's remote Agent can remain opaque.

The client does not need access to its:

- model;
- internal prompt;
- memory;
- Tool registry;
- orchestration graph.

It interacts with the remote Agent through a protocol contract.

---

## 2. A2A actors

The core interaction has:

```text
User
 |
 v
A2A Client / Client Agent
 |
 v
A2A Server / Remote Agent
```

The client acts for the user and communicates with a remote Agent endpoint.

The remote Agent may itself be an entire multi-Agent system internally.

A2A does not require the caller to know.

---

## 3. Agent Card

An Agent Card is the remote Agent's discovery document.

It describes things such as:

```text
identity
version
supported interfaces
capabilities
skills
input/output media types
security requirements
```

Think of it as a machine-readable business card plus service contract.

It is not a dump of internal Tools.

---

## 4. A2A 1.0 interface shape

A2A 1.0 moved protocol details onto supported interfaces.

Conceptually:

```text
AgentCard
└── supportedInterfaces[]
    ├── url
    ├── protocolBinding
    └── protocolVersion
```

The Tiny-Agent integration therefore builds cards with:

```python
AgentInterface(
    url="https://example.com/a2a",
    protocol_binding="JSONRPC",
    protocol_version="1.0",
)
```

This is intentionally versioned because older 0.3 tutorials use a different Agent Card shape.

---

## 5. Skills

An Agent Card advertises focused skills.

Example:

```text
id: research
name: Research
description: Find and synthesize evidence
tags: research, evidence
examples: Compare two approaches
```

A skill helps a caller decide whether the Agent is suitable.

It is not necessarily a one-to-one mapping to one internal Tool.

The remote Agent decides how to implement the capability.

---

## 6. Message

A `Message` is one communication turn.

It has:

```text
messageId
role
parts
optional task/context references
metadata/extensions
```

Roles identify client/user vs Agent-originated messages.

Messages carry communication, not necessarily final durable outputs.

---

## 7. Part

A Part is the content unit inside Messages and Artifacts.

A2A 1.0 supports content such as:

```text
text
raw bytes
URL/file reference
structured data
```

This makes the protocol modality-flexible instead of assuming every Agent only exchanges chat strings.

---

## 8. Artifact

An Artifact is a concrete task output.

Examples:

- report;
- image;
- structured JSON result;
- generated file;
- dataset fragment.

This distinction is useful:

```text
Message  = communication
Artifact = deliverable
```

Do not bury every durable result inside conversational prose if the protocol has an artifact model.

---

## 9. Stateless response vs Task

A remote Agent can respond immediately with a Message for a simple interaction.

For longer work it can create a stateful `Task`.

A Task has an ID and lifecycle.

This matters when Agent work takes longer than one HTTP request.

---

## 10. Task lifecycle

A2A supports task states including terminal and interrupted states.

Examples include:

```text
working
completed
failed
canceled
rejected
input-required
auth-required
```

The important architectural lesson is:

> Remote Agent work may pause for more input or authentication rather than simply returning success/failure immediately.

That connects naturally to Stage 06 HITL/resumability.

---

## 11. Streaming and asynchronous collaboration

A2A supports patterns for:

- ordinary request/response;
- streaming updates;
- long-running task status;
- push notifications.

This is why A2A is better understood as an Agent task protocol, not merely "HTTP function calling."

---

## 12. A2A 1.0 is a breaking evolution from older tutorials

Older material may reference 0.2/0.3 operation names or card fields.

A2A 1.0 changed several important shapes, including:

- operation naming;
- supported interface representation;
- Agent Card protocol location;
- streaming event representation;
- task operations.

Always check the spec/version before copying code.

Stage 05 taught the same lesson with MCP version changes.

---

## 13. A2A does not erase security boundaries

An Agent Card can describe authentication/security requirements.

But the application still owns:

```text
credential storage
caller authorization
tenant isolation
output validation
trust policy
```

Remote Agent content is external data.

Protocol compliance is not equivalent to correctness or trustworthiness.

---

## 14. A2A vs MCP table

| Question | MCP | A2A |
|---|---|---|
| Main boundary | App/Agent to capabilities/context | Agent system to Agent system |
| Discovery object | Server capabilities/primitives | Agent Card + skills/interfaces |
| Internal implementation exposed? | Tool/resource/prompt surface is exposed | Remote Agent can remain opaque |
| Long-running task lifecycle | Not the main abstraction | Core concept |
| Durable deliverables | Resource/tool result dependent | Artifact is explicit |
| Typical use | Connect DB/docs/tools/services | Collaborate with remote specialist Agent |

They can coexist.

For example:

```text
Your Agent
  |
  | A2A
  v
Remote Research Agent
  |
  | MCP
  v
Remote Agent's private search/database servers
```

The caller does not need to see that internal MCP topology.

---

## 15. Why Stage 09 only builds protocol objects offline

This stage constructs current Agent Card and Message objects and validates the SDK integration without requiring a network service.

A full production A2A server introduces:

- HTTP/gRPC serving;
- authentication;
- task storage;
- long-running workers;
- deployment;
- observability;
- tenant isolation.

Those are better combined with Stage 10 production deployment instead of hiding infrastructure complexity inside a beginner interoperability demo.

---

## 16. Core mental model

> **MCP standardizes access to capabilities. A2A standardizes collaboration with independent Agent systems.**

Do not use protocol names as synonyms just because both contain Agents and JSON.
