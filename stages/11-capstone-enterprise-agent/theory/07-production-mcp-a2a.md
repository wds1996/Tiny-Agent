# 07 — Production Boundary, MCP, and A2A

The final architecture is useful only if callers can actually reach it. Stage 11 therefore exposes the same domain Agent through multiple boundaries without duplicating the research logic.

## Boundary 1 — HTTP service

The FastAPI adapter exposes:

```text
POST /v1/research/base
POST /v1/research/langgraph
POST /v1/research/langgraph/{thread_id}/resume
GET  /livez
```

The adapter translates HTTP payloads into `ResearchRequest` and calls the domain agents. It does not implement planning or retrieval inside route functions.

```text
HTTP
  -> request validation
  -> OpenScholar domain core
  -> ResearchReport
  -> JSON
```

## Identity warning

The teaching body includes `user_id` for correlation and memory examples. That field is **not authenticated identity**.

Bad production design:

```json
{"user_id":"admin"}
```

followed by:

```text
Great, you are now admin.
```

Production should derive principal/tenant identity from authenticated middleware, gateway claims, workload identity, or another trusted layer.

## Boundary 2 — MCP capability

MCP exposes a capability of the system:

```text
search_corpus(query)
```

A host can discover and call the corpus search tool without adopting OpenScholar's internal runtime.

This is a Stage 05 boundary:

```text
Agent / application
      -> MCP
      -> capability
```

The MCP tool returns evidence data. The host still owns authorization and how that data enters its model context.

## Boundary 3 — A2A Agent service

A2A exposes OpenScholar as an independent Agent system:

```text
remote Agent
   -> A2A message/task
   -> OpenScholar Agent
   -> research result
```

The remote caller does not need to know whether OpenScholar internally uses LangGraph, local RAG, MCP, or a reviewer team.

This is the concrete difference:

```text
MCP: use my capability
A2A: collaborate with my Agent
```

## A2A does not grant trust

An Agent Card advertises capabilities. It does not prove that a caller is authorized to use every capability, and it does not prove that the remote Agent is safe.

A production A2A deployment still needs:

- TLS;
- caller authentication;
- tenant binding;
- authorization;
- rate limits;
- request size limits;
- tracing/audit boundaries;
- downstream least privilege.

## Stage 10 service constraints still apply

Wrapping OpenScholar in FastAPI does not erase production realities:

```text
process-local semaphore != cluster-wide limit
request timeout != hard kill
dict memory != distributed state
Docker != correctness
```

A real deployment can place the Agent behind `BoundedAgentService` to preserve queue and execution deadlines.

## Durable graph backend

The teaching LangGraph version defaults to `InMemorySaver` so examples run without infrastructure. Production should switch the checkpointer to a durable backend from Stage 06.

Likewise:

```text
InMemoryResearchMemory
```

should become a durable Store when cross-restart user preferences matter.

Do not mistake an in-memory demo implementation for a production guarantee merely because the surrounding API is network-accessible.

## Container

The Stage 11 Dockerfile packages the application and starts the FastAPI example. It is deliberately a baseline, not a claim of enterprise deployment completeness.

A production environment must still decide:

- secret delivery;
- persistence backends;
- replicas and pool sizing;
- network egress;
- authentication;
- autoscaling;
- job durability;
- observability exporter;
- backup/retention;
- data licensing.

A container is a shipping box. It does not inspect whether the thing inside the box is architecturally sound.

## Data licensing and paper ingestion

The repository stores a manifest of open paper identifiers and download URLs rather than redistributing PDFs. Users should still verify the license/terms of any corpus they ingest, especially when extending the project beyond the provided open-paper examples.

## Suggested production evolution

A realistic next architecture could be:

```text
Gateway / Auth
      |
      v
OpenScholar API replicas
      |
      +---- Postgres checkpointer / Store
      |
      +---- Redis coordination / rate limit
      |
      +---- Qdrant corpus index
      |
      +---- Crossref / external scholarly services
      |
      +---- MCP capability servers
      |
      +---- A2A peer Agents
      |
      `---- OpenTelemetry / LangSmith
```

But every extra box must solve a measured requirement. A 12-stage learning project should end by teaching you when **not** to add another box.

## Production checklist

Before calling a research Agent “production ready,” verify at least:

```text
[ ] identity comes from a trusted auth boundary
[ ] request/run/thread/user IDs are distinct
[ ] local and external evidence have explicit trust classes
[ ] retrieval/evidence thresholds are evaluated
[ ] memory writes require policy/consent
[ ] side effects require approval when appropriate
[ ] approval does not bypass authorization
[ ] retries are safe/idempotent
[ ] durable HITL uses a durable checkpointer
[ ] timeouts and capacity limits exist
[ ] secrets are not logged/traced
[ ] citations are evaluated against evidence inventory
[ ] regression tests cover known failures
[ ] corpus/license/data-retention policy is understood
[ ] container/runtime health checks exist
[ ] multi-Agent coordination remains bounded
```

The capstone is complete when you can explain why each box exists—not when the architecture diagram contains the largest number of arrows.