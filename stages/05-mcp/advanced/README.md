# MCP 2026 Advanced Extensions — Tasks, MRTR, Apps, and Governance

Stage 05 teaches the stable MCP core first. This advanced note covers the capabilities that became especially important in the 2026-07-28 generation.

## 1. Extensions framework

New capabilities can evolve outside the core protocol under reverse-DNS extension identifiers and negotiate support explicitly. This keeps the stateless core small while allowing faster evolution.

## 2. Tasks extension

Long-running tool work may return a task handle instead of blocking one Tool call until completion.

Conceptually:

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

Task state belongs to the extension/application; the 2026 core itself remains stateless.

## 3. Multi Round-Trip Requests (MRTR)

The old session-oriented server-to-client request model does not fit a stateless core. MRTR restructures workflows such as elicitation/sampling into explicit multi-round request/response interactions without requiring a permanently open bidirectional protocol session.

## 4. MCP Apps

MCP Apps let servers associate interactive UI with capabilities. Hosts render the UI in a sandboxed boundary and route actions back through governed MCP calls rather than granting arbitrary page authority.

The security principle remains:

```text
rendered UI
!= authorization
```

## 5. Header-based routing and cacheable catalogs

Modern HTTP requests expose method/tool identity in headers so gateways can route/authorize without deep payload inspection. Deterministic list ordering and cache hints help clients keep capability catalogs stable and cacheable.

## 6. Enterprise authorization direction

The 2026 release hardened OAuth/OIDC alignment and moved away from Dynamic Client Registration toward client metadata documents. Treat protocol discovery, authentication, and authorization as separate concerns.

## 7. Relationship to Tiny-Agent long-horizon work

MCP Tasks can represent long-running remote capability execution. Tiny-Agent Stage 14 teaches the broader application harness problem: local task ledgers, durable run ownership, workspace artifacts, context compaction, evaluator/repair, and sandbox rehydration.

They solve adjacent layers, not the same abstraction.

## References

- 2026-07-28 release — https://blog.modelcontextprotocol.io/posts/2026-07-28/
- current MCP roadmap — https://blog.modelcontextprotocol.io/posts/mcp-roadmap/

## Exercise

Design an Agent that calls a long-running MCP data-processing Tool. Identify separately:

1. MCP task handle/state;
2. Tiny-Agent service run ID;
3. Agent thread/checkpoint ID;
4. workspace artifact IDs;
5. authenticated principal/tenant;
6. timeout/cancellation semantics at each layer.
