# 08 — Modern production profile: semantic retrieval, identity, bounded serving, and long-horizon execution

The capstone's offline path is deliberately deterministic. A real deployment swaps infrastructure behind stable domain boundaries rather than rewriting the Agent.

## 1. Retrieval upgrade

Teaching:

```text
HashEmbeddingModel
+ InMemoryVectorRetriever
```

Production-shaped:

```text
neural EmbeddingModel
+ Qdrant
+ metadata/tenant filters
+ document diversity
+ optional reranker
```

`OpenAIEmbeddingModel` implements the same Stage 04 `EmbeddingModel` protocol. `RetrieverResearchCorpus` maps any Retriever into the OpenScholar Evidence contract.

## 2. Document diversity

Top-k chunks can all come from one document. That may create the illusion of multiple independent sources.

`DiversifiedResearchCorpus` can limit repeated chunks per `document_id` before the Agent's evidence-count gate.

This is still a retrieval heuristic, not a universal scientific evidence rule. Domain-specific evidence policy may need source quality, date, design type, contradiction, or claim coverage.

## 3. Deterministic vs semantic grounding

Keep deterministic checks for:

```text
citation exists
status valid
local evidence present
forbidden path blocked
HITL resume works
```

Add semantic evaluation for questions ordinary code cannot answer:

```text
Does [E2] actually support the sentence that cites it?
Is the wording stronger than the evidence?
```

`StructuredCitationSupportJudge` uses schema-constrained model output but remains an evaluator, not an execution authority.

## 4. Trusted service identity

Production requests should not contain an authoritative `user_id` field.

```text
credential
-> trusted authenticator
-> subject/roles/tenant
-> bound ResearchRequest
```

The demo `build_authenticated_openscholar_app()` accepts an application-supplied authenticator so JWT/session/mTLS implementation remains deployment-specific.

## 5. Bounded service execution

The upgraded API passes research work through `BoundedAgentService`:

```text
admission semaphore
-> queue timeout
-> run deadline
-> Agent
```

This integrates Stage 10 rather than bypassing it.

Long work should instead enter a durable job queue and return a run handle.

## 6. Durable HITL and owner binding

The LangGraph version demonstrates checkpointed pause/resume. Production must combine that with:

- durable checkpointer;
- durable Store where needed;
- authenticated thread ownership;
- approval identity/audit;
- idempotent side effects.

Knowing a `thread_id` is never authorization to resume it.

## 7. Sandbox and long-horizon research

A future/extended OpenScholar can move document/code/data analysis into Stage 09A governed workspaces and Stage 10A long-horizon task ledgers:

```text
research run
-> durable job
-> task ledger
-> sandboxed analysis workspace
-> evidence artifacts
-> context compaction
-> evaluator/repair
-> final report
```

The harness and compute environment should remain separable so sandbox loss does not destroy run state or expose orchestration credentials.

## Final production test

For every box in your deployment diagram, answer:

1. what semantic responsibility does it own?
2. what data/trust boundary crosses it?
3. what happens if it fails?
4. which state survives?
5. who is authorized to use/resume it?
6. how is it evaluated/observed?

If the answer is only “because enterprise architectures use this box,” remove the box.
