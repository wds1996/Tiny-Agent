# 08 — Modern Production Profile: From OpenScholar Demo to Deep-Research System

The Stage 11 offline Agent is intentionally deterministic and inspectable. A real deployment should **compose stronger infrastructure behind stable domain boundaries** rather than rewrite the Agent every time a backend changes.

This chapter is the final architecture map for the entire Tiny-Agent curriculum.

Important honesty first:

> `BaseOpenScholarAgent` and `LangGraphOpenScholarAgent` demonstrate the core research path. ContextBuilder, Skills, sandbox compute, durable jobs, and LongHorizonHarness are composable advanced layers; the default short-run path does not pretend to execute every subsystem on every question.

A mature system uses the least dynamic/capable architecture required by the task.

---

## 1. Two profiles, not one giant Agent

### Interactive research profile

Use when the question can finish in one bounded request/session:

```text
request
-> memory/style context
-> plan
-> local + metadata retrieval
-> evidence gate
-> synthesize
-> critic/writer review
-> evaluation
-> optional approved export
```

### Deep-research profile

Use when work may span many documents, tools, analysis steps, sandboxes, or sessions:

```text
authenticated request
-> durable run
-> TaskLedger / long-horizon harness
-> JIT context + Skills
-> retrieval / analysis subtasks
-> sandboxed compute where needed
-> artifacts + evidence
-> evaluator / repair
-> HITL
-> final report
```

Do not force a five-second question through a three-day project-management system because the architecture diagram is impressive.

---

## 2. Production retrieval: swap infrastructure, keep the evidence contract

Teaching baseline:

```text
HashEmbeddingModel
+ InMemoryVectorRetriever
```

Production-shaped path:

```text
neural EmbeddingModel
+ QdrantRetriever
+ metadata/tenant filters
+ candidate diversity
+ optional sparse/hybrid retrieval
+ optional reranker
```

Tiny-Agent maps any Retriever into OpenScholar's evidence contract:

```python
corpus = RetrieverResearchCorpus(retriever)
corpus = DiversifiedResearchCorpus(
    corpus,
    max_per_document=1,
)
```

The Agent still consumes `Evidence` objects. Storage/search implementation does not leak through the whole control flow.

---

## 3. Diversity is not scientific independence

`DiversifiedResearchCorpus` prevents top-k from being four chunks of one document.

That is useful, but scientific evidence quality may also depend on:

```text
source quality
study design
publication date
independent replication
contradictions
claim coverage
retraction/correction status
```

A document-diversity heuristic should not be marketed as an automated systematic-review methodology.

The recurring Tiny-Agent principle applies:

> Be precise about what a mechanism guarantees.

---

## 4. Deterministic grounding vs semantic grounding

Keep deterministic checks for questions code can answer exactly:

```text
citation label exists?
used evidence belongs to the run?
minimum full-text evidence present?
status value valid?
export path contained?
HITL resume state valid?
```

Then add semantic evaluation for questions such as:

```text
Does [E2] actually support this sentence?
Is the wording stronger than the cited evidence?
```

```python
semantic = evaluate_citation_support(
    report,
    StructuredCitationSupportJudge(decision_model),
)
```

A model judge remains an evaluator, not execution authority.

Also distinguish:

```text
no cited claims to evaluate
!=
100% demonstrated support
```

Production reporting should represent `not_applicable/no_claims` explicitly rather than allowing an empty semantic set to create false confidence in dashboards.

---

## 5. Trusted identity before personalization or persistence

Bad production API:

```json
{
  "question": "...",
  "user_id": "admin",
  "tenant_id": "tenant-a"
}
```

Production-shaped boundary:

```text
credential
-> deployment authenticator
-> AuthenticatedIdentity(subject, tenant, roles)
-> bind_trusted_identity
-> BoundedAgentService
-> OpenScholar
```

OpenScholar's production handler scopes personalization identity as:

```python
user_id = f"{tenant_id}:{subject_id}"
```

so identical subject IDs in two tenants do not collide.

Knowing a `thread_id`/`run_id` never authorizes resume by itself.

---

## 6. Bounded interactive service

Short requests should still have explicit admission and deadlines:

```python
service = BoundedAgentService(
    OpenScholarServiceHandler(agent),
    max_concurrency=8,
    queue_timeout_seconds=0.25,
    request_timeout_seconds=60.0,
)
```

This adds:

```text
admission semaphore
queue timeout
run deadline
metrics
safe sync/async handling
```

The HTTP route remains an adapter.

For long work, do not simply set `request_timeout_seconds=86400` and call it durability.

---

## 7. Durable run layer for deep research

Long work should be acknowledged durably:

```text
POST /runs
-> authenticate/authorize
-> SQLiteRunQueue/production queue enqueue
-> 202 + run_id
```

Worker:

```python
job = queue.claim(worker_id="worker-7", lease_seconds=30)
```

Then the worker can load/create the long-horizon project state.

Production would normally use a distributed database/queue/workflow backend, but the semantics stay:

```text
durable enqueue
atomic ownership
lease/recovery
terminal result
```

---

## 8. TaskLedger organizes sub-work inside the run

A deep research run may contain:

```text
find candidate papers
retrieve full text
extract method A
extract method B
compare assumptions
check contradictory evidence
write report
review citations
```

`TaskLedger` keeps this progress outside model context.

```python
ledger.initialize(
    objective="Compare two Agentic RAG methods",
    tasks=[
        "collect sources",
        "extract evidence",
        "compare methods",
        "draft report",
    ],
)
```

New sessions/workers can resume from the same workspace without replaying hidden history.

---

## 9. ContextBuilder creates the working set

A deep run may own hundreds of artifacts and evidence items. The current worker should receive only what it needs.

Conceptual composition using real Tiny-Agent primitives:

```python
items = [
    ContextItem(
        key="task",
        kind="task",
        content=current_task.description,
        required=True,
        trusted=True,
    ),
    ContextItem(
        key="handoff",
        kind="note",
        content=harness.handoff_summary(state),
        priority=90,
        provenance="derived:handoff",
    ),
    ContextItem(
        key="skill",
        kind="skill",
        content=activated_skill.instructions,
        priority=85,
        provenance="skill:research-review",
    ),
]

snapshot = ContextBuilder(context_budget).build(items)
```

The full project remains externalized.

---

## 10. Skills add phase-specific procedure

Deep research can activate Skills such as:

```text
research-review
paper-extraction
report-formatting
```

Flow:

```text
Skill metadata catalog
-> choose relevant Skill
-> activate SKILL.md
-> load reference only when needed
```

A Skill can recommend a process. It does not grant filesystem/network/Tool permissions.

This keeps organizational procedure separate from run-specific memory and evidence.

---

## 11. Sandboxed analysis only when task requires compute

Some research questions need only retrieval/synthesis. Do not spawn a sandbox for decoration.

Use workspace/compute when a subtask requires:

```text
run analysis code
inspect repository
parse/transform large data
produce figures
execute tests
```

```python
runner = DockerSandboxRunner(workspace)
result = runner.run(["python", "analysis.py"])
```

Tiny-Agent's default baseline disables network and reduces container privilege/resources.

The harness keeps durable state and orchestration credentials outside disposable compute.

---

## 12. Artifact-first long-horizon continuity

Deep research should produce explicit artifacts:

```text
evidence/paper-a.md
evidence/paper-b.md
analysis/comparison.csv
figures/result.png
reports/draft.md
```

The next worker receives paths/previews rather than every byte.

This makes context smaller and work auditable.

---

## 13. Evaluator/repair loop

```text
worker result
-> deterministic checks
-> semantic judge where needed
-> pass: task complete
-> fail: repair/replan/human
```

Example:

```text
draft report
-> citation inventory check fails
-> create repair task
-> activate research-review Skill
-> load offending claims + evidence
-> revise
-> evaluate again (bounded)
```

Do not create infinite "critic until perfect" loops. Stage 07 budgets still apply.

---

## 14. Durable HITL

LangGraph demonstrates checkpointed `interrupt` / `Command(resume=...)` semantics.

Production adds:

```text
durable checkpointer
thread owner binding
reviewer identity/audit
approval expiry/version
idempotent post-approval action
```

Knowing a checkpoint/thread ID does not authorize a user to resume it.

Approval also does not bypass deterministic path/Tool authorization.

---

## 15. Complete deep-research architecture

```text
                         Client
                           |
                           | credential
                           v
                 +--------------------+
                 | Auth / API boundary|
                 +---------+----------+
                           |
                           v
                 +--------------------+
                 | Durable Run Queue  |
                 +---------+----------+
                           |
                    worker lease
                           v
                 +--------------------+
                 | LongHorizonHarness |
                 | + TaskLedger       |
                 +----+----------+----+
                      |          |
              context |          | artifacts
                      v          v
              +-------------+  Workspace
              |ContextBuilder|      |
              +------+------+      v
                     |        sandbox compute
             Skill activation      |
                     |              |
                     +------+-------+
                            v
                    Research workers
                       /        \
                 retrieval    analysis
                       \        /
                        evidence
                           |
                           v
                  synthesis / team
                           |
                    evaluators/HITL
                           |
                           v
                     final report
```

Every box has a semantic responsibility.

---

## 16. Failure walkthrough

At 2:03 PM:

```text
worker-B owns run-42
TaskLedger: compare methods = running
sandbox performs analysis and writes artifact
worker-B crashes before terminal ledger save
```

Recovery:

```text
run lease expires -> worker-C claims run-42
load TaskLedger -> recover_interrupted marks task pending
inspect durable artifact/provenance
policy decides whether task can reuse artifact or rerun
if rerun has side effects -> idempotency rules apply
continue
```

No single model session is required to survive.

---

## 17. What "production complete" still does not mean

Tiny-Agent teaches reference mechanisms. Real organizations still choose/provide:

- IAM/JWT/session/mTLS implementation;
- durable Postgres/LangGraph checkpoint/Store backend;
- managed distributed job/workflow infrastructure;
- hardened sandbox/microVM platform;
- object storage/retention/backups;
- data licensing/compliance;
- egress controls;
- autoscaling and rollout strategy;
- SLOs/on-call/incident processes.

One repository cannot provide every organization's infrastructure/security policy without becoming either dishonest or several cloud providers in a trench coat.

---

## 18. Final production review questions

For every box in your design, answer:

1. What semantic responsibility does it own?
2. What trust/data boundary crosses it?
3. What state is durable vs disposable?
4. What happens if it fails mid-operation?
5. Who is authorized to create/read/resume/cancel it?
6. How is retry made safe?
7. How is it evaluated and observed?
8. Can a simpler architecture meet the requirement?

If the only answer is "enterprise diagrams have this box," remove the box.

---

## Final Tiny-Agent principle

> **A modern production Agent is not one giant autonomous loop. It is a composition of bounded model decisions, deterministic policy, externalized state, just-in-time context/procedure, governed capabilities/compute, durable recovery, evaluation, and explicit human/identity boundaries.**
