# 08 — 现代生产 Profile：从 OpenScholar Demo 到 Deep-Research System

Stage 11 的 offline Agent 故意保持 deterministic、inspectable。

真正生产部署不应该每换一个 backend 就重写 Agent；更合理的方式是：**在稳定的 domain boundary 后面组合更强的 infrastructure。**

这一章是整个 Tiny-Agent curriculum 的最终架构地图。

先把一个事实说清楚：

> `BaseOpenScholarAgent` 和 `LangGraphOpenScholarAgent` 展示的是核心 research path。ContextBuilder、Skills、sandbox compute、durable jobs 与 LongHorizonHarness 都是可以按需组合的高级层；默认 short-run path 不会假装每个问题都必须启动所有 subsystem。

成熟系统应该使用任务真正需要的、动态性和 capability 最低的架构。

---

## 1. 两种 Profile，而不是一个无所不能的 Giant Agent

### Interactive Research Profile

适合一个 bounded request / session 能完成的问题：

```text
request
-> memory / style context
-> plan
-> local + metadata retrieval
-> evidence gate
-> synthesize
-> critic / writer review
-> evaluation
-> optional approved export
```

### Deep-Research Profile

适合跨很多 document、Tool、analysis step、sandbox 或 session 的任务：

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

不要因为三天任务的架构图很帅，就强迫一个五秒钟的问题也先走一遍项目管理系统。

---

## 2. Production Retrieval：替换 Infrastructure，不改 Evidence Contract

教学 baseline：

```text
HashEmbeddingModel
+ InMemoryVectorRetriever
```

生产形态：

```text
neural EmbeddingModel
+ QdrantRetriever
+ metadata / tenant filters
+ candidate diversity
+ optional sparse / hybrid retrieval
+ optional reranker
```

Tiny-Agent 把任意 `Retriever` 映射回 OpenScholar 的 evidence contract：

```python
corpus = RetrieverResearchCorpus(retriever)
corpus = DiversifiedResearchCorpus(
    corpus,
    max_per_document=1,
)
```

Agent 仍然只消费 `Evidence` 对象。

storage / search implementation 不应该一路泄漏到整个 control flow。

---

## 3. Diversity 不等于 Scientific Independence

`DiversifiedResearchCorpus` 可以避免 top-k 全部来自同一篇文档的四个 chunk。

这很有用，但科学证据质量还可能取决于：

```text
source quality
study design
publication date
independent replication
contradictions
claim coverage
retraction / correction status
```

所以 document-diversity heuristic 不能宣传成“自动 systematic review methodology”。

Tiny-Agent 一贯的原则仍然适用：

> **准确描述一个 mechanism 真正保证了什么。**

---

## 4. Deterministic Grounding 与 Semantic Grounding

普通代码能精确检查的问题，继续 deterministic：

```text
citation label 是否存在？
used evidence 是否属于当前 run？
minimum full-text evidence 是否满足？
status value 是否有效？
export path 是否 contained？
HITL resume state 是否有效？
```

semantic evaluation 处理另一类问题：

```text
[E2] 是否真的支持这句话？
当前 wording 是否比 evidence 本身更强？
```

```python
semantic = evaluate_citation_support(
    report,
    StructuredCitationSupportJudge(decision_model),
)
```

model judge 仍然只是 evaluator，不是 execution authority。

还要特别区分：

```text
no cited claims to evaluate
!=
100% demonstrated support
```

如果根本没有 claim 可评，production dashboard 应明确表示：

```text
not_applicable / no_claims
```

不能让一个 empty set 看起来像“所有 citation 都 100% 获得了验证”。

---

## 5. Personalization / Persistence 之前先建立 Trusted Identity

错误的 production API：

```json
{
  "question": "...",
  "user_id": "admin",
  "tenant_id": "tenant-a"
}
```

生产形态应该是：

```text
credential
-> deployment authenticator
-> AuthenticatedIdentity(subject, tenant, roles)
-> bind_trusted_identity
-> BoundedAgentService
-> OpenScholar
```

OpenScholar production handler 会把 personalization identity 作用域化：

```python
user_id = f"{tenant_id}:{subject_id}"
```

所以两个 tenant 中碰巧都叫 `user-17` 的 subject 不会发生 namespace collision。

同样：知道 `thread_id` / `run_id` 从来不构成 resume authorization。

---

## 6. Bounded Interactive Service

短请求仍然需要明确 admission 与 deadline：

```python
service = BoundedAgentService(
    OpenScholarServiceHandler(agent),
    max_concurrency=8,
    queue_timeout_seconds=0.25,
    request_timeout_seconds=60.0,
)
```

它增加：

```text
admission semaphore
queue timeout
run deadline
metrics
safe sync / async handling
```

HTTP route 依旧只是 adapter。

面对长任务，不要把：

```text
request_timeout_seconds=60
```

改成：

```text
request_timeout_seconds=86400
```

然后宣布“durability 已解决”。超长 timeout 不是 durable job architecture。

---

## 7. Deep Research 的 Durable Run Layer

长任务应该先得到 durable acknowledgment：

```text
POST /runs
-> authenticate / authorize
-> SQLiteRunQueue / production queue enqueue
-> 202 + run_id
```

worker 再 claim：

```python
job = queue.claim(
    worker_id="worker-7",
    lease_seconds=30,
)
```

之后 worker 才加载或创建 long-horizon project state。

生产环境通常会使用 distributed database / queue / workflow backend，但 semantics 不变：

```text
durable enqueue
atomic ownership
lease / recovery
terminal result
```

---

## 8. TaskLedger 组织 Run 内部 Sub-Work

一个 deep research run 可能包含：

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

`TaskLedger` 把这些 progress 放在 model context 之外：

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

新的 session / worker 可以从同一 workspace 恢复，而无需重放隐藏历史。

---

## 9. ContextBuilder 构造 Current Working Set

一个 deep run 可以拥有几百个 artifact 与 evidence item，但当前 worker 只应看到当前决策真正需要的内容。

用真实 Tiny-Agent primitive 的概念组合：

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

完整 project state 仍然 externalized。

---

## 10. Skills 提供 Phase-Specific Procedure

Deep research 可以按阶段激活：

```text
research-review
paper-extraction
report-formatting
```

流程：

```text
Skill metadata catalog
-> choose relevant Skill
-> activate SKILL.md
-> load reference only when needed
```

Skill 可以建议 procedure，但不会授予 filesystem / network / Tool permission。

这使 organizational procedure 与 run-specific memory / evidence 保持分离。

---

## 11. 只有需要 Compute 时才启动 Sandbox

有些问题只需要 retrieval / synthesis，没必要为了“看起来像高级 Agent”额外开 sandbox。

当 subtask 真正需要下面能力时再用 workspace / compute：

```text
run analysis code
inspect repository
parse / transform large data
produce figures
execute tests
```

```python
runner = DockerSandboxRunner(workspace)
result = runner.run([
    "python",
    "analysis.py",
])
```

Tiny-Agent baseline 默认禁用 network，并降低 container privilege / resource authority。

harness 把 durable state 与 orchestration credential 留在 disposable compute 外部。

---

## 12. Artifact-First Long-Horizon Continuity

Deep research 应产生显式 artifacts：

```text
evidence/paper-a.md
evidence/paper-b.md
analysis/comparison.csv
figures/result.png
reports/draft.md
```

下一 worker 接收 path / preview，而不是把所有 byte 全塞进 context。

这样 context 更小，工作也更 audit-friendly。

---

## 13. Evaluator / Repair Loop

```text
worker result
-> deterministic checks
-> semantic judge where needed
-> pass: task complete
-> fail: repair / replan / human
```

例如：

```text
draft report
-> citation inventory check fails
-> create repair task
-> activate research-review Skill
-> load offending claims + evidence
-> revise
-> evaluate again（bounded）
```

不要构造无限：

```text
critic until perfect
```

Stage 07 budget 仍然适用。

---

## 14. Durable HITL

LangGraph 展示 checkpointed：

```text
interrupt
Command(resume=...)
```

production 还需要再增加：

```text
durable checkpointer
thread owner binding
reviewer identity / audit
approval expiry / version
idempotent post-approval action
```

知道 checkpoint / thread ID 并不会授权 resume。

approval 也不会绕过 deterministic path / Tool authorization。

---

## 15. 完整 Deep-Research Architecture

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
                    evaluators / HITL
                           |
                           v
                     final report
```

每一个 box 都有明确 semantic responsibility。

---

## 16. Failure Walkthrough

下午 2:03：

```text
worker-B owns run-42
TaskLedger: compare methods = running
sandbox performs analysis and writes artifact
worker-B crashes before terminal ledger save
```

恢复：

```text
run lease expires
-> worker-C claims run-42
-> load TaskLedger
-> recover_interrupted marks task pending
-> inspect durable artifact / provenance
-> policy decides reuse artifact or rerun
-> if rerun has side effects, idempotency rules apply
-> continue
```

整个过程不要求任何一个 model session 永远存活。

---

## 17. “Production Complete” 仍然不意味着什么

Tiny-Agent 提供 reference mechanism，但真实组织仍然需要自己提供：

- IAM / JWT / session / mTLS implementation；
- durable Postgres / LangGraph checkpoint / Store backend；
- managed distributed job / workflow infrastructure；
- hardened sandbox / microVM platform；
- object storage / retention / backups；
- data licensing / compliance；
- egress controls；
- autoscaling / rollout strategy；
- SLO / on-call / incident process。

一个仓库不可能诚实地替所有组织解决这些问题——除非它打算穿着风衣假装自己是好几家云厂商叠在一起。

---

## 18. 最终 Production Review Questions

设计里的每一个 box 都应该能回答：

1. 它拥有哪项 semantic responsibility？
2. 哪个 trust / data boundary 会跨过它？
3. 哪些 state durable，哪些 disposable？
4. 它在 operation 中途失败会发生什么？
5. 谁被允许 create / read / resume / cancel？
6. retry 如何保证安全？
7. 它如何被 evaluated / observed？
8. 更简单的架构能否满足 requirement？

如果某个 box 存在的唯一理由是：

> enterprise diagram 都有这个。

那就把它删掉。

---

## Tiny-Agent 最终原则

> **现代生产 Agent 不是一个巨大的 autonomous loop。它是 bounded model decision、deterministic policy、externalized state、just-in-time context / procedure、governed capability / compute、durable recovery、evaluation，以及显式 human / identity boundary 的组合。**