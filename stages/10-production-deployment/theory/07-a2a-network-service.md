# 07 — A2A as a Deployed Network Service

Stage 09 introduces Agent-to-Agent collaboration and A2A protocol concepts. Stage 10 asks what changes when that Agent becomes a real network service with public discovery, authentication, task state, streaming, replicas, and shutdown behavior.

Protocol compatibility is not production readiness.

---

## 1. Conceptual server stack

A current A2A Python SDK server can be understood as layers similar to:

```text
Agent business logic
    ↓
AgentExecutor
    ↓
EventQueue / task events
    ↓
request handler
    ↓
TaskStore
    ↓
A2A route factory
    ↓
Starlette/FastAPI ASGI app
    ↓
Uvicorn / deployment
```

Exact helper/class names are versioned SDK surface. Tiny-Agent keeps integration code covered by CI so tutorials do not fossilize one SDK snapshot as eternal truth.

Learn the responsibilities first.

---

## 2. Agent Card is a public contract

The Agent Card advertises capabilities and reachable endpoints.

Bad production card:

```text
http://127.0.0.1:9999
```

when clients reach:

```text
https://agents.example.com/research
```

Internal container addresses are not necessarily client-reachable public URLs.

Agent Card discovery answers:

```text
what Agent/service exists and how can it be contacted?
```

It does **not** automatically answer:

```text
may this caller use every capability?
```

---

## 3. Discovery != authentication != authorization

Keep the same separation as MCP:

```text
discovery
    -> endpoint/capability information

authentication
    -> who/what is calling?

authorization
    -> may this principal perform this task/resource action?
```

A public Agent Card should not be interpreted as a guest pass to every backend Tool.

---

## 4. Task IDs require ownership

A remote Agent may expose:

```text
create/send task
get task
cancel task
resubscribe/stream
```

Knowing a task ID is not authorization.

Persist ownership:

```text
task_id
subject_id
tenant_id
created_at
status
```

and enforce it on read/cancel/resume.

This is the same service-identity principle used by Stage 10's threads/jobs.

---

## 5. In-memory TaskStore is a teaching backend

One-process smoke tests can use an in-memory store.

With replicas:

```text
request creates task on replica A
next request lands on replica B
```

If B has a different in-memory store, task continuity breaks.

Production task/event state must be shared/durable enough for the protocol behavior you promise.

---

## 6. Streaming/resubscription changes storage requirements

If clients may disconnect and later resubscribe, progress cannot live only in a live socket buffer.

Useful architecture:

```text
Agent execution
-> durable task state/events
-> stream projects updates to client
```

The stream is a view. The task record is the durable continuity boundary.

Whether every event must be replayable is a product/protocol decision.

---

## 7. Gateway/middleware still matters

A deployed A2A service may sit behind:

```text
TLS termination
auth middleware
request size limits
rate limits
WAF/network policy
logging/tracing
```

The A2A route implementation should coexist with normal service controls rather than bypass them because "Agents talk to Agents."

Agents remain software clients. They do not receive diplomatic immunity at the load balancer.

---

## 8. Shutdown/drain

A request handler/runtime may own internal tasks. During host shutdown:

```text
stop admission
-> drain/persist task state
-> close handler/runtime resources
-> release leases
-> exit
```

Tiny-Agent wires the SDK's cleanup path into ASGI lifespan where applicable.

Long work should survive process replacement through durable task/checkpoint state.

---

## 9. MCP + A2A + HTTP are different boundaries

A realistic architecture:

```text
User/client application
       | HTTP
       v
Research product service
       | A2A
       v
Research Agent
       | MCP
       +--> search capability
       +--> document capability
       +--> database capability
```

Possible distinctions:

```text
HTTP -> product/service API
A2A  -> Agent collaboration/task protocol
MCP  -> capability/context protocol
```

Do not force one protocol to solve every boundary.

---

## 10. Worked remote delegation

Supervisor Agent wants a specialist to analyze citations.

```text
Supervisor
-> discover CitationReview Agent Card
-> authenticate as service principal
-> send bounded task + evidence references
-> receive remote task_id
-> persist mapping in local run state
-> stream/poll specialist progress
-> specialist returns artifact/result
-> supervisor validates result before use
```

The remote Agent's output is still external/untrusted data until the Host decides how to use it.

A2A collaboration does not make remote Agents infallible colleagues; it makes them networked colleagues, which is arguably even more reason to keep contracts clear.

---

## 11. Version-aware SDK usage

Helper names and route APIs can change.

Maintain this discipline:

```text
protocol semantics
    -> stable mental model

SDK helper names
    -> versioned adapter + integration tests
```

If an old tutorial conflicts with the project's tested SDK range, prefer current official docs/CI behavior rather than combining snippets from incompatible versions.

---

## Completion principle

> **A deployed A2A Agent is a normal governed network service with protocol-specific task semantics—not a trust shortcut. Persist task ownership/state according to the promises clients depend on.**
