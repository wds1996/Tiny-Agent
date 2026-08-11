# Tiny-Agent

Tiny-Agent is a learning-first, production-minded Python agent runtime built from scratch.

The project starts with a minimal ReAct-style loop and will evolve step by step toward a practical agent system with tool use, stateful orchestration, RAG, MCP, memory, evaluation, observability, API serving, and deployment.

## Learning roadmap

- [x] Day 1-3: LLM API, structured output, function calling
- [ ] Day 4: ReAct-style agent runtime
- [ ] Day 5: Planning and execution
- [ ] Day 6: Agent SDK concepts
- [ ] Day 8-10: Stateful orchestration / LangGraph
- [ ] Day 11-12: RAG and Agentic RAG
- [ ] Day 13-14: MCP
- [ ] Day 15-21: Memory, persistence, HITL, reliability, tracing, evals, security
- [ ] Day 22-30: Production project, FastAPI, Docker, CI, docs

## Design principles

1. Learn the mechanism before the framework.
2. Keep the core runtime small and inspectable.
3. Prefer explicit state and typed interfaces.
4. Separate model reasoning from auditable actions and observations.
5. Add production concerns incrementally instead of hiding them behind a framework.

## References

- ReAct: Synergizing Reasoning and Acting in Language Models (ICLR 2023): https://arxiv.org/abs/2210.03629

## Status

Early development. The first implementation milestone is `v0.1`: a framework-free ReAct-style agent loop.
