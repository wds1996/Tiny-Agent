# Stage 11 — Capstone: Enterprise Research & Knowledge Agent

## Why this stage exists

The capstone combines the earlier stages into one system large enough to demonstrate real Agent engineering tradeoffs while remaining readable as an educational reference.

The project target is an **Enterprise Research & Knowledge Agent** that can work with private knowledge, external research tools, structured workflows, MCP integrations, memory, approval, evaluation, and production deployment.

## Target architecture

```text
User / API
    |
    v
Task Router
    |
    +------------------+
    |                  |
    v                  v
Planner           Direct workflow
    |
    v
Executor / State Graph
    |
    +---------+----------+-----------+
    |         |          |           |
    v         v          v           v
  RAG      Web tools   Database     MCP
    \         |          |           /
     +--------+----------+----------+
              |
              v
          Evidence
              |
              v
         Verification
              |
       risky action?
        /          \
      yes          no
       |            |
 Human Approval     |
        \           /
         +---------+
              |
              v
         Final Answer
```

## Target capabilities

- task classification and routing;
- bounded planning and replanning;
- Agentic RAG over local/private knowledge;
- external research tools;
- database tools;
- custom MCP integrations;
- explicit state and checkpointing;
- session and long-term memory;
- human approval for risky operations;
- retry, timeout, fallback, and execution budgets;
- permission-aware tool execution;
- full traces;
- regression evaluation dataset;
- FastAPI service;
- Docker-based deployment;
- tests and CI;
- architecture and design documentation.

## Planned repository areas

```text
code/
├── agents/
├── graphs/
├── tools/
├── rag/
├── mcp/
├── memory/
├── evals/
├── api/
└── deployment/

theory/
├── 01-system-design.md
├── 02-design-decisions.md
└── 03-production-checklist.md
```

## Evaluation targets

The capstone should not be judged only by a demo. It should measure at least:

- end-to-end task success;
- tool selection correctness;
- tool argument correctness;
- retrieval quality;
- trajectory quality;
- failure/recovery behavior;
- average latency;
- token usage;
- tool-call count.

## Milestone

Produce a portfolio-quality open-source Agent application that can be learned from stage by stage, run locally, evaluated reproducibly, and discussed seriously in an Agent engineering interview.

## Final question

> Can another learner inspect this system and understand not only *what* it does, but *why* each Agent engineering decision exists?
