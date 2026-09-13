# Stage 04: Which Policy Applies to This Order? — From Looking Things Up to Agentic RAG

> Language: **English** | [简体中文](README.zh-CN.md)

[Stage 03](../03-stateful-orchestration/README.md) gave Lin's weather brief an understandable process: collect the readings, draft the brief, check it, revise when necessary, and decide whether it can be delivered. We could identify the draft that had been checked and explain the next transition. There was still a prerequisite, though: the application needed the facts it was going to use. A state graph cannot place an unread handbook into a model's input by itself.

Lin now wants to try the assistant at the fictional Acme shop. A customer asks: “I ordered ordinary goods on August 3, 2026. They are paid for, unused, and intact, and the order is now on day 38. Can I request an original-payment refund? What evidence do I need for approval?” Lin has a policy revised in August. An older page says 30 days; the revised policy gives some orders 45 days. Which passage should the assistant read, and how can it explain the rule without inventing a promise?

We will follow that one inquiry. First we will find the relevant passages ourselves, then turn that lookup into a program. Once one search works, we will handle the more interesting case where it finds only half the required evidence. The shop, policies, and dates are teaching fixtures, not a real merchant's rules. There is no order-verification or payment interface here either: the customer's facts are assumptions for the question, not verified transaction records.

## 1. Open the book before making the loop more complicated

Do not install a vector database yet. Open [`acme-refunds-v2.en.md`](code/data/acme-refunds-v2.en.md) and read “Original-payment window for new orders.” It says that paid ordinary-goods orders placed on or after August 1, 2026 may enter the original-payment refund application process within 45 calendar days. The order date is day zero and day 45 is included. The goods must be unused and intact; custom-made goods and delivered digital products are excluded from this ordinary-goods rule.

Under the facts the customer supplied, the August 3 order on day 38 is within that application window. But the customer asked two questions, not one. We still need “Evidence submission and approval procedure” to answer the second part. That section asks for an order identifier, a refund reason, and evidence of the item's condition. It distinguishes support verification, authorization by a reviewer, and execution by the payment system.

A useful explanation can now say: under those stated conditions, the order is within the window to apply; provide the specified information and wait for verification and approval. No refund has occurred in this conversation. Reading “45 days” and replying “I have refunded it” would be rather like treating a restaurant reservation as proof that dinner has been cooked. A few relevant stages remain.

This is the basic idea behind **RAG, Retrieval-Augmented Generation**: find relevant external material before answering, then give that material and the question to a generation model. Retrieval finds candidates; generation reads them and writes an explanation. This does not update the model's weights or permanently train the file into it. The current request can use the revised policy because the application supplied that policy as input.

The smallest useful path is easy to follow:

```text
customer question → find passages → check whether they suffice → answer from them
                                             └─ not enough → explain the gap
```

The previous chapter and this one solve different parts of the same problem. Stage 03 organized the work. We are now providing a source of facts for that work to operate on.

## 2. Why leave an archived policy and another shop's terms on the shelf?

Lin has collected the material in [`code/data/`](code/data/). It contains the current refund policy, delivery and invoice information, an archived refund policy, and another fictional shop's terms. Each has a Chinese and an English version: eight files, yielding eighteen section-sized chunks with the default settings. These are not eighteen unrelated examples. They are the sources and distractors for the same policy question.

The distractors matter. If the collection contains only the correct answer, the retriever hardly has to demonstrate exclusion. A short archived “30-day refund” page may match the query very well. Another shop's promise may be even more explicit. Neither lexical similarity nor confident wording makes those promises applicable to Acme.

[`manifest.json`](code/data/manifest.json) records each file's source ID, title, version, tenant, language, and publication status. The text tells us what a rule says; these additional fields tell us whose rule it is and which version we are reading. Those additional fields are **metadata**. The loader turns them into a `Source` and pairs the source with its full text in a `Document`.

The application chooses the search scope. The model does not get to choose a different shop or remove the publication filter. `Scope.accepts()` states the basic eligibility rule:

```python
def accepts(self, chunk: Chunk) -> bool:
    source = chunk.source
    return (source.tenant == self.tenant and source.language == self.language
            and source.status == "published")
```

This is a teaching scope check, not a complete authentication system. A real application should derive its access scope from trusted identity and document policy, not a user typing “I am an administrator” or a model returning a different tenant name. The demo also selects its output language explicitly. Each language searches its own sources; we are not claiming to have solved cross-language retrieval.

There is an important wrinkle in the policy: **current document does not mean new window for every order.** The published document explicitly retains the 30-day rule for orders placed before August 1. Excluding the archived file does not remove the need to read the transition clause for an older order. A source maintainer, not a similarity score, supplies the publication status. That status also does not prove the document itself is correct.

Only after deciding which sources may participate is it useful to optimize the search. Otherwise, a faster retriever merely delivers the wrong edition sooner.

## 3. Give the reader a coherent section, not an isolated number

With two short pages, placing the complete text into a model request can be reasonable. Retrieval is not a tax every application must pay. The difficulty appears when more material accumulates: a refund question does not need every delivery note, invoice rule, and historical edition. Relevant conditions can become harder to locate among that extra text.

We therefore create **chunks**: units small enough to retrieve, but large enough to read meaningfully. This corpus is split at section headings first, not at an arbitrary twenty-eighth word. The 45-day rule should travel with its starting date, item restrictions, and example. Passing only the number 45 gives the answer model none of those conditions.

A chunk in `retrieval.py` carries the following fields:

```python
@dataclass(frozen=True)
class Chunk:
    id: str
    source: Source
    topic: str
    heading: str
    text: str
    start: int
    end: int
    complete_section: bool
```

The ID locates the passage, `source` identifies its document, and `heading` describes the topic. `start` and `end` are Python character offsets in that exact source text, so `document.text[start:end]` must reproduce the passage. They are not UTF-8 byte offsets and not model-token offsets. `topic` is a label assigned when organizing this corpus, not a fact inferred by the retriever.

If a section is too long, the chunker uses overlapping character windows inside that section:

```python
for part, left in enumerate(range(start, end, max_chars - overlap)):
    right = min(left + max_chars, end)
    chunks.append(Chunk(
        f"{document.source.id}:{topic}:{part}", document.source, topic, title,
        document.text[left:right], left, right, end - start <= max_chars,
    ))
    if right == end:
        break
```

The defaults are `max_chars=1200` and `overlap=80`. Some characters appear in both neighboring windows, reducing the chance that a condition disappears at one boundary. Overlap is not a proof of semantic completeness. It also creates duplicate content. Chinese text does not normally separate every word with spaces, so an English-oriented `text.split()` is not a general multilingual chunker.

The example takes a conservative approach to fragmented sections: each fragment of an oversized section has `complete_section=False`. Later local checks will not treat one such fragment as the whole rule. Conversely, a complete section is not automatically sufficient for a question; the flag only describes what this chunker did. Larger systems can expand neighbors or fetch a parent section, but must explicitly recover the missing context rather than trusting overlap to have done that job.

Smaller chunks can separate a rule from its exception. Larger ones can mix several questions into one retrieval unit. There is no universal best size. Our default sections fit whole; deliberately reducing the limit provides a concrete way to inspect the consequences before changing the generator.

## 4. People look for the refund page. What does the program look for?

We now have eighteen chunks and one question. A first search strategy is to count useful shared terms: which sections mention an original-payment refund, a window, or approval evidence? Exact terms are not an embarrassing baseline. A specific product name or policy phrase can be a very strong signal.

To compare these signals numerically, assign a position to each term. Imagine just three positions for a moment: refund, window, and approval. A passage receives one weight at each position. That list of numbers is a vector. There is no requirement to understand neural-network training before understanding this representation.

The example uses **TF-IDF** as an inspectable lexical baseline. Term frequency reflects how often a term occurs. Inverse document frequency reduces the distinguishing power of terms that appear almost everywhere. If every page says “customer,” that word is not particularly helpful for choosing between refund timing and invoice corrections. During initialization, the model builds one vocabulary and one set of weights from the corpus:

```python
document_frequency: Counter[str] = Counter()
for text in texts:
    document_frequency.update(set(tokenize(text)))
if not document_frequency:
    raise ValueError("Corpus has no indexable terms")
self.vocabulary = tuple(sorted(document_frequency))
self.dimension = len(self.vocabulary)
self.idf = [1 + math.log((1 + len(texts)) / (1 + document_frequency[t]))
            for t in self.vocabulary]
```

The query must use those same coordinates and weights. A separate query vocabulary would put different meanings at the same positions. `embed_query()` fills the fitted coordinates from the query's actual terms and normalizes the result:

```python
def embed_query(self, text: str) -> list[float]:
    counts = Counter(tokenize(text))
    vector = [counts[term] * weight for term, weight in zip(self.vocabulary, self.idf)]
    return normalize(vector)
```

The local `tokenize()` extracts ordinary English terms and adjacent Chinese character pairs. For example, 退款手续 can yield 退款, 款手, and 手续. This is a visible feature-extraction rule, not DeepSeek's tokenizer and not a claim of perfect Chinese word segmentation. Both document encoding and query encoding use the same representation so a coordinate means the same thing on both sides.

**An embedding-shaped interface does not make this a trained semantic model.** “Can the money go back the way it came?” may not match “original-payment refund” well. Neural embeddings can learn useful relationships between different expressions, but still do not guarantee correct handling of negation, dates, or exceptions. The component that represents text for retrieval and the DeepSeek component that writes an answer have different jobs. Changing the answer model does not automatically change the search representation.

So far, we have turned textual clues into comparable numbers. We have not decided whether any customer is entitled to anything. That distinction will remain important when the first score appears.

## 5. A high score means a high rank, not a high probability of a refund

A passage about refund timing is likely to point in a direction closer to a refund query than a passage about shipping. **Cosine similarity** compares vector directions:

$$
\mathrm{cosine}(a,b)=\frac{a\cdot b}{\lVert a\rVert\lVert b\rVert}
$$

Normalize both vectors to length one, multiply corresponding coordinates, and sum the products:

```python
def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise ValueError("Vector dimensions differ")
    return sum(a * b for a, b in zip(normalize(left), normalize(right)))
```

`normalize()` rejects empty vectors and nonfinite values. An all-zero vector stays zero by this implementation's convention, making its score against another vector zero. Cosine values for general real vectors lie between -1 and 1. This baseline uses nonnegative TF-IDF weights, so its scores normally lie between 0 and 1. A score of 0.82 is a ranking signal for this representation and query, not an 82% refund-success probability or a source-quality certificate.

Candidates must be eligible before they enter that comparison. The relevant part of `InMemoryVectorRetriever.retrieve()` is:

```python
for chunk, stored in zip(self.chunks, self.vectors):
    if not scope.accepts(chunk):
        continue
    score = cosine_similarity(vector, stored)
    if score > 0.0:
        ranked.append(SearchResult(chunk, score))
return sorted(ranked, key=lambda hit: (-hit.score, hit.chunk.id))[:top_k]
```

Other tenants, other languages, and archived sources are excluded before ranking. `top_k` is a maximum, not a promise to return exactly K results. No positive-scoring candidates means an empty result. With this lexical baseline, that can mean the wording did not overlap, rather than that the knowledge collection contains no answer. With a different representation, score thresholds require their own evaluation; a copied threshold does not become a guarantee.

Run this part from the repository root without a model key:

```bash
python stages/04-agentic-rag/code/retrieval.py
python stages/04-agentic-rag/code/retrieval.py --language en
```

Inspect the source, heading, version, and score of each item. The return type is `SearchResult(chunk, score)`, not “refund approved.” Keeping text and identity together lets later code say exactly which passage it used.

The in-memory implementation compares all eligible passages. That is sufficient for this small corpus and easy to inspect. Passage vectors are created when the retriever is constructed; a query vector is created when a question arrives. If a source changes, the corresponding indexed representation must be rebuilt. Editing a file on disk does not magically update an existing in-memory index.

## 6. First collect candidates, then choose what belongs on the desk

Keeping only the first match may find the refund window but miss the approval procedure. Sending every match to the generator creates the opposite problem: it must read passages with little relevance to the question. Lin needs enough evidence to answer both parts, not the largest possible pile of paper.

We therefore distinguish two counts. `candidate_k` limits the initial pool; `top_k` limits what this search retains after another ordering step. The default initial pool is six. The example's small **reranker** then compares how much of the query's term set each candidate covers:

```python
query_terms = set(tokenize(query))
def key(hit: SearchResult) -> tuple[float, float, str]:
    coverage = len(query_terms & set(tokenize(searchable_text(hit.chunk)))) / max(1, len(query_terms))
    return (-coverage, -hit.score, hit.chunk.id)
return sorted(candidates, key=key)[:top_k]
```

It returns the same candidate objects in a different order. Their `score` field remains the original vector score; it has not silently become a new model-based relevance score. A reranker also cannot manufacture an approval passage that initial retrieval failed to include.

This coverage rule is another lexical heuristic, not an improvement guaranteed for every question. A more capable reranker may use a CrossEncoder that reads each query-passage pair together. That costs more work and still needs to demonstrate a benefit. The [Sentence Transformers retrieve-and-rerank guide](https://www.sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html) describes the two-stage structure.

After ordering comes packing. `pack_evidence()` deduplicates chunk IDs and accepts only whole passages that fit inside the current budget:

```python
for hit in results:
    if hit.chunk.id in seen:
        continue
    if len(kept) >= max_items or used + len(hit.chunk.text) > max_chars:
        continue
    kept.append(hit)
    seen.add(hit.chunk.id)
    used += len(hit.chunk.text)
return tuple(kept)
```

The default is 6000 passage-text characters and at most eight chunks. A passage that does not fit is skipped; the code does not trim away “except custom-made goods” to save space. These are character counts, not token counts, and this limit excludes instructions and other request fields. The live client separately checks the size of its serialized input.

This simple first-seen packing strategy has a limitation: earlier, weaker material can occupy space that would be useful later. It is not an optimal context selector. When required conditions do not fit, however, the program must report insufficient evidence rather than pretend the missing condition does not exist.

## 7. Two parts of the question require two parts of the evidence

Return to the actual request: “Can I apply, and what evidence is needed for approval?” A top-ranked window clause can still answer only half of it. Relevance, sufficiency, and applicability are different questions. “There is a result” cannot substitute for all three.

`BasicRAG` uses a fixed path: search once, pack the evidence, assess it, and then generate. It does not automatically search again when assessment fails. The key boundary is:

```python
candidates = self.retriever.retrieve(task.question, scope=task.scope, top_k=candidate_k)
evidence = pack_evidence(lexical_rerank(task.question, candidates, top_k=top_k),
                         max_chars=self.max_evidence_chars)
self.retriever.verify(evidence, task.scope)
decision = self.policy.assess(task, task.question, evidence)
if not isinstance(decision, EvidenceDecision):
    raise ValueError("Policy did not return EvidenceDecision")
if not decision.sufficient:
    return RAGResult("insufficient_evidence", None, evidence, decision.reason)
```

The job of `policy.assess()` is now specific: inspect the original question and the material currently available, and propose either “enough to answer” or “something is missing.” Its output is structured rather than a vague sentence about probably having enough:

```python
@dataclass(frozen=True)
class EvidenceDecision:
    sufficient: bool
    evidence_ids: tuple[str, ...]
    reason: str
    rewritten_query: str = ""
```

An affirmative decision must identify the passages it relies on. An insufficient decision approves no evidence and may propose a new query. The application checks that cited IDs were actually retrieved, belong to the allowed scope, and still match the corpus snapshot. Inventing a convincing-looking document number does not establish provenance.

For an offline view of this path, the demo uses `ChecklistPolicy`. **This is a declared teaching double, not a general semantic assessor.** The `--case` option selects a product fixture with an application-defined evidence checklist. The new-order refund-and-materials case requires complete `window-new` and `approval` sections. The double checks whether those categories arrived, not whether every possible conclusion follows from their headings. A real service needs appropriate evidence requirements and an assessment of actual conditions; these labels must not be marketed as universal fact verification.

The accompanying `ExtractiveAnswerer` is equally explicit about its role. It copies selected source passages with their IDs so we can inspect the data flow. It is not pretending to have generated a thoughtful customer reply:

```python
class ExtractiveAnswerer:
    """Return the selected source text verbatim; no LLM and no inferred eligibility."""
    kind = "extractive"
    def answer(self, task: RAGTask, evidence: Sequence[SearchResult]) -> AnswerDraft:
        text = "\n\n".join(f"[{hit.chunk.id}] {hit.chunk.text}" for hit in evidence)
        return AnswerDraft(text, tuple(Citation(hit.chunk.id, hit.chunk.text) for hit in evidence))
```

Run the fixed path:

```bash
python stages/04-agentic-rag/code/basic_rag.py --show-evidence
python stages/04-agentic-rag/code/basic_rag.py --top-k 1
```

The first command retains three candidates by default, then selects the window and approval sections. It reports `status: answered` and `answer_kind: extractive`. Here, answered means that the current answer contract completed, not that the program performed intelligent inference. The second command retains only one item and should report `insufficient_evidence`, with no final answer. It may still show what it found; that is not the same as having enough to answer the full inquiry.

The order date, item condition, and day-38 age are also supplied assumptions. Retrieving a policy does not verify who the customer is or whether an order exists. We have now placed the relevant material on the desk. Only now will we ask a real model to explain it.

## 8. Give DeepSeek the passages, not an invitation to remember the policy

[`deepseek_rag.py`](code/deepseek_rag.py) uses a real DeepSeek model for both evidence assessment and answer generation while retaining the same retriever and fixed control path. The default allows at most two model requests: one to assess the current bundle, another to write a cited answer. If assessment says there is not enough evidence, generation does not run.

The model receives the original question, requested language, supplied facts, and selected evidence—not the full index or every field in application state:

```python
def task_payload(task: RAGTask) -> dict:
    # Application budgets, tenant scope and reference labels are not model decisions.
    return {"question": task.question, "language": task.scope.language, "provided_facts": dict(task.facts)}
```

Evidence is encoded separately with its ID, title, heading, version, and text. Similarity scores are not handed to the model as answer-confidence values. Evaluation reference IDs are not supplied as hints. Tenant scope and request budgets remain application controls, and the response schema contains no “relax the filter” field.

The request uses the same DeepSeek Responses interface as the preceding chapters:

```python
response = self.client.responses.create(
    model=self.model, instructions=instructions, input=encoded,
    text={"format": {"type": "json_schema", "name": name, "schema": schema}},
    tools=[], tool_choice="none", max_output_tokens=4096,
)
```

`text.format` supplies a JSON Schema, with different schemas for assessment and generation. `tools=[]` and `tool_choice="none"` keep these calls data-only: there is no payment function, arbitrary file operation, or web-search capability here. The response must complete, its JSON must parse, and local shape and type checks must succeed. The [Responses API reference](https://api-docs.deepseek.com/api/create-response/) specifies this interface; a compatible SDK does not remove the need to check what the actual service supports.

An answer contains `text` and `citations`. Each citation has an `evidence_id` and a short verbatim `quote`. The application requires the ID to belong to the exact generation bundle and the quote to exist in that passage:

```python
quote = citation.quote
if not isinstance(quote, str) or not quote.strip() or quote not in by_id[citation.evidence_id].text:
    raise ValueError("Citation quote is absent from its cited passage")
ids.append(citation.evidence_id)
```

**An existing quote does not prove an entailed conclusion.** A model can quote “approval is required” accurately and still conclude “your refund has been issued.” This validator detects invented citations, not every semantic contradiction. The tests deliberately retain that counterexample. Evidence assessment can also be wrong; significant conclusions still need their scope, quotations, and wording checked against each other.

Likewise, a retrieved passage saying “ignore the earlier rules” remains retrieved data. JSON packaging and instructions help identify provenance, but are not a complete prompt-injection defense. The application does not turn policy text into system instructions or Python code, does not supply its key as evidence, and exposes no action tools in these requests. Those are concrete execution limits, not a promise that generated prose can never be influenced by untrusted content.

Install the live-model dependencies from the repository root and select an account-accessible model that supports Responses:

```bash
python -m pip install -r stages/04-agentic-rag/code/requirements.txt
export DEEPSEEK_API_KEY="your-deepseek-api-key"
export DEEPSEEK_MODEL="deepseek-v4-flash"
python stages/04-agentic-rag/code/deepseek_rag.py --language en --show-evidence
```

In PowerShell, the variable assignments are `$env:DEEPSEEK_API_KEY="your-deepseek-api-key"` and `$env:DEEPSEEK_MODEL="deepseek-v4-flash"`. The model name is a documented example, not a permanent account guarantee. This entry point makes live requests and incurs API usage. Missing configuration, dependencies, or a failed response never trigger a silent fallback to the extractive double.

For the supplied facts, a sensible reply distinguishes being inside the 45-day application window from completing verification and approval. It must not claim a refund occurred. Its wording need not match the offline passages word for word. We now have a fixed RAG path that genuinely uses an LLM; the next difficulty is what to do when its first evidence bundle is incomplete.

## 9. The first search found timing. What should the second search ask?

With `top_k=1`, the fixed path finds a window clause but not the requested approval materials. Lin does not need the assistant to repeat “refund window” more confidently. She needs it to identify the gap: “We still lack the submission and approval procedure. Search for that next.”

That is the dynamic control in this chapter's **Agentic RAG**: inspect the evidence, then choose between answering, searching for something missing, or stopping. Adding a node does not by itself make retrieval agentic. A new observation must affect the next action. The live version asks the model to read the bundle and propose a rewrite. The offline version still uses the declared checklist double to make that control path observable.

A useful rewrite is “evidence submission refund approval procedure authorized reviewer.” A poor one simply repeats the entire original question. A more dangerous one inserts the answer it hopes to find: “Prove that this refund has already been approved.” Query rewriting should target missing information, not change the question, widen the tenant scope, or turn a guess into supposed evidence for itself.

After the second search, we must keep the first window clause. `RAGNodes.search()` combines new and old passages, deduplicates and bounds the bundle, and invalidates the previous selection and assessment:

```python
chosen = lexical_rerank(query, candidates, top_k=self.top_k)
evidence = pack_evidence([*state["evidence"], *chosen],
                         max_chars=self.max_evidence_chars, max_items=8)
ids = ", ".join(hit.chunk.id for hit in chosen) or "none"
return dict(**common, evidence=list(evidence), assessment=None, selected=(),
            next_node="assess", events=[f"search: {ids}; retained={len(evidence)}"])
```

`evidence` means the material currently retained. `selected` is the subset approved for generation. Separating them lets us distinguish what was found from what the answer actually used. A changed evidence bundle receives a fresh assessment; a previous `sufficient=True` cannot simply be applied to different material.

Run the bounded search experiment:

```bash
python stages/04-agentic-rag/code/agentic_rag.py --language en --show-evidence
```

The default retains one new passage per search. First it finds `window-new` and notices that `approval` is missing. The second search obtains the procedure and assesses both passages together, then returns cited source excerpts. Inspect `searches: 2`, `rewrites: 1`, and the two actual queries rather than accepting a sentence that claims the assistant “searched carefully.”

This experiment **does not establish that dynamic retrieval is always better than fixed RAG**. The fixed path with its default `top_k=3` can collect both sections in one pass. Setting the dynamic path to `--top-k 3` also makes it search only once here. We narrow the per-search selection deliberately to expose a feedback-driven search. In a real design, compare evidence quality, extra model requests, and new failure paths instead of treating an additional model call as an automatic improvement.

## 10. Use the state and nodes we already know to hold the process together

Allowing a second search creates several facts the program must retain: the original question, current query, retrieved evidence, and remaining attempts. This is precisely the State from the preceding chapter. We need it because these facts govern execution, not because every example must contain a graph.

The runtime state is:

```python
class RAGState(TypedDict):
    task: RAGTask
    query: str
    query_history: list[str]
    evidence: list[SearchResult]
    selected: tuple[SearchResult, ...]
    assessment: EvidenceDecision | None
    searches: int
    rewrites: int
    status: str
    reason: str
    answer: AnswerDraft | None
    answer_kind: str
    events: list[str]
    next_node: str
```

The original task remains in `task`; a rewrite only replaces `query`. `query_history` records attempts, `searches` counts retrievals, and `rewrites` counts accepted rewrites. `assessment` and `selected` describe the current evidence decision. `status` and `answer` distinguish a generated result, insufficient evidence, and a program failure. The model does not automatically receive this whole structure.

There are four jobs. `prepare` handles the explicitly identified greeting fixture or proceeds to evidence search. `search` finds material. `assess` proposes whether to answer or keep looking. `answer` generates and validates citations. A greeting returns a simple greeting without retrieval. Its category comes from the demo option; this is not a claim that a few keyword tests recognize arbitrary user intent.

```text
prepare → search → assess ── sufficient ──→ answer → end
                     │
                     ├─ missing evidence, rewrite allowed → search
                     └─ cannot continue → retain evidence and explain the gap
```

[`agentic_rag.py`](code/agentic_rag.py) executes these jobs in an ordinary loop. [`langgraph_agentic_rag.py`](code/langgraph_agentic_rag.py) expresses the same nodes and exits with LangGraph. The conditional edge chooses from an existing decision; it does not secretly perform a search:

```python
builder.add_conditional_edges("assess", lambda state: state["next_node"],
                              {"search": "search", "answer": "generate_answer", "end": END})
builder.add_edge("generate_answer", END)
```

The graph's `generate_answer` node calls the same `nodes.answer`. It does not maintain a second copy of the evidence policy. `query_history` and `events` have append reducers and receive only new entries. The search node explicitly combines the retained evidence and returns the replacement collection. Current assessment, current selection, and answer are replacement fields. Appending every list indiscriminately would mix stale selections into new decisions.

Install the optional framework dependencies and observe the same path:

```bash
python -m pip install -r stages/04-agentic-rag/code/requirements-frameworks.txt
python stages/04-agentic-rag/code/langgraph_agentic_rag.py --language en --show-evidence
```

The entry point performs one streaming execution:

```python
for state in graph.stream(initial_state(task, args.initial_query), stream_mode="values",
                          config={"recursion_limit": 30}):
    print("graph position:", state["next_node"], "searches:", state["searches"])
```

`values` yields current state snapshots; `updates` focuses on node-produced updates. See [LangGraph Streaming](https://docs.langchain.com/oss/python/langgraph/streaming). The final streamed state is used as the result; the program does not call `invoke()` afterward and accidentally execute the task twice. `TypedDict` and reducers retain their responsibilities from [the Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api): expressing fields and merge behavior, not validating the truth of a source.

The live graph entry uses the very same nodes, replacing only assessment and generation:

```bash
python stages/04-agentic-rag/code/langgraph_deepseek_rag.py --language en --show-evidence
```

It requires both the model dependencies and framework dependencies, plus the configured key and model. One allowed rewrite permits at most two assessments and one final generation. Whether a real model requests the rewrite or judges the material sufficient depends on its actual response; the offline trajectory is not a promise about live behavior.

## 11. Not finding an answer does not authorize endless searching

Lin asks one more practical question: “What happens if the handbook has no quantum-device warranty? Will the assistant try ten phrasings and eventually make up a plausible answer?” This is where the application, rather than the model's enthusiasm, must own the continuation boundary.

The default allows one rewrite, hence at most two searches. After an insufficient assessment, control passes through these checks:

```python
query = decision.rewritten_query.strip()
if state["rewrites"] >= self.max_rewrites or not query:
    return self.stop("insufficient_evidence", decision.reason, assessment=decision)
if query_key(query) in {query_key(old) for old in state["query_history"]}:
    return self.stop("insufficient_evidence", "Repeated query", assessment=decision)
return dict(assessment=decision, query=query, rewrites=state["rewrites"] + 1,
            next_node="search", events=[f"rewrite: {decision.reason}"])
```

`query_key()` normalizes case, whitespace, and some Unicode forms before comparing queries. Uppercasing the same English words is not a new strategy. Different phrases with the same meaning can still evade this textual check, but the total attempt limit remains. We have not presented string comparison as semantic deduplication.

Live assessment and generation also share one request budget. The default is three; it is incremented before sending a request, and failed requests still consume it. `max_retries=0` disables hidden SDK retries. The client's `timeout=30.0` is not a hard thirty-second deadline for the whole task, and character counts are not precise billing estimates.

Two endings need different names. Completing a search without enough policy support is `insufficient_evidence`. A retriever exception, model timeout, malformed decision, or invalid citation is `failed`. Neither produces a final answer, but one is a normal knowledge boundary and the other needs diagnosis. Existing evidence and attempted queries remain recorded. Raw exception details are not copied into the customer response, and failures do not trigger automatic retries.

Run both counterexamples:

```bash
python stages/04-agentic-rag/code/agentic_rag.py --max-rewrites 0
python stages/04-agentic-rag/code/agentic_rag.py --case unknown
```

The first stops after the incomplete initial bundle. The second may retrieve a paragraph saying the policy does not cover quantum-device warranties; that paragraph is not a warranty rule. Insufficient evidence is an explicit normal outcome, so the CLI does not treat it as a Python crash. Program failures exit with code 1. To determine whether the business question was answered, inspect the status, not merely whether the terminal showed an exception.

## 12. When the collection grows, replace the search layer without changing the question

We now have retrieval, evidence checks, and generation connected. If the collection grows to thousands of sections, computing every comparison in Python may be inconvenient. That is a reason to consider a specialized vector index or database. We will still search the same policy corpus with the same representation and scope, rather than switch to an unrelated database trivia question.

**FAISS** provides a straightforward comparison baseline in `IndexFlatIP`: exact, exhaustive inner-product search. Normalize both document and query vectors and the inner product equals cosine similarity. The central operations are:

```python
faiss.normalize_L2(matrix)
faiss.normalize_L2(query_vector)
backend = faiss.IndexFlatIP(matrix.shape[1])
backend.add(matrix)
scores, positions = backend.search(query_vector, min(top_k, len(eligible)))
```

The function filters eligible chunks before constructing this small index, rather than searching all tenants and removing unauthorized top results afterward. Limiting K to the eligible count and checking returned positions prevents invalid positions from being mistaken for the last chunk. The demonstration builds an index per call; a real service would normally reuse and update its indexes rather than include construction in every query.

`IndexFlatIP` still examines all indexed vectors. Using FAISS does not automatically turn exact search into approximate search or promise a different asymptotic cost. Approximate indexes and their recall trade-offs are separate choices. The normalization relationship is described in the [FAISS distance reference](https://github.com/facebookresearch/faiss/wiki/MetricType-and-distances). Text, document versions, and authorization also remain application responsibilities around the index.

**Qdrant** keeps vectors with payload data and supports filtered vector queries. The local in-memory example stores chunk IDs, tenant, language, and publication status, then applies the same scope conditions:

```python
filters = models.Filter(must=[models.FieldCondition(key=key, match=models.MatchValue(value=value))
            for key, value in {"tenant": scope.tenant, "language": scope.language, "status": "published"}.items()])
result = client.query_points("policies", query=vector, query_filter=filters,
                             with_payload=True, limit=top_k)
```

Returned IDs are resolved against this corpus snapshot and rechecked before their text is used. A `finally` block closes the local client. This is an in-memory demonstration, not a remote deployment or a test of multi-user authentication; payload filtering does not establish caller identity. [Qdrant Filtering](https://qdrant.tech/documentation/search/filtering/) documents this style of condition combination.

After installing the optional framework requirements, run the backends separately:

```bash
python stages/04-agentic-rag/code/vector_backends.py --backend faiss --language en
python stages/04-agentic-rag/code/vector_backends.py --backend qdrant --language en
```

Both default to the lexical TF-IDF representation. They change where vectors are searched, not how “money back the way it came” is understood. To explore the latter, install `requirements-neural.txt`, provide an existing local Sentence Transformers model directory appropriate for the language and retrieval task, and add `--embedding-model /path/to/local/model`. The adapter encodes queries and documents with that model and does not implicitly download weights. Replacing the encoder means rebuilding all passage vectors, not mixing new query vectors with an old index.

A trained semantic representation may help with paraphrases but needs its own measured comparison. [Sentence Transformers semantic search](https://www.sbert.net/examples/sentence_transformer/applications/semantic-search/README.html) explains query and document encoding. A neural encoder, a vector database, and a correct answer remain three separate things: representation, candidate search, and evidence-based interpretation.

## 13. Test the evidence path, not only the pleasantness of the final sentence

Lin knows the default example can run. What she needs now is a way to notice when a chunking or ranking change loses the approval section. Reading only the final sentence is inadequate: a model might guess the required paperwork without seeing it, or quote the right passage while interpreting it incorrectly.

Start by evaluating retrieval separately. The current refund question needs both `window-new` and `approval`. If the first two results are the window and an invoice section, only one of the two relevant passages arrived. This example measures **Recall@K at passage level**:

```python
def recall_at_k(retrieved_ids: Sequence[str], relevant_ids: set[str], *, k: int) -> float:
    positive_int(k, "k")
    if not relevant_ids:
        raise ValueError("Recall is undefined here without relevant passages")
    return len(set(retrieved_ids[:k]) & relevant_ids) / len(relevant_ids)
```

It does not merely ask whether some chunk from the Acme policy file was returned. A hit in the wrong section of the right document is not a hit on the approval requirement. Repeating one correct passage also counts once, rather than inflating recall with duplicates.

The first useful passage's position is a different question. **Reciprocal Rank** finds the first relevant item within the first K positions and takes the reciprocal of its rank:

```python
def reciprocal_rank(retrieved_ids: Sequence[str], relevant_ids: set[str], *, k: int) -> float:
    positive_int(k, "k")
    if not relevant_ids:
        raise ValueError("Reciprocal rank needs nonempty reference evidence")
    return next((1 / rank for rank, ident in enumerate(retrieved_ids[:k], 1)
                 if ident in relevant_ids), 0.0)
```

Rank one gives 1; rank two gives 0.5; no relevant item before the cutoff gives 0. Averaging across cases produces the MRR@K reported here. A single relevant passage at rank one can already earn a perfect reciprocal rank, so this metric cannot replace a requirement for two complementary passages.

Run the small retrieval evaluation:

```bash
python stages/04-agentic-rag/code/evaluation.py --k 3
```

The eight Chinese and English queries include explicit terms and paraphrases such as “Can the money go back the way it came?” The program prints actual IDs for every case before averaging. The lexical representation exposes weaknesses on those paraphrases. That is useful evidence, not a reason to remove the difficult cases until the score looks respectable.

These are visible development examples, not a held-out assessment of production quality. Reference IDs stay in evaluation code and are not supplied as generation hints. Questions with no supporting policy do not fit this implementation's nonempty relevant-set denominator; an empty reference set is rejected. Unknown-topic abstention is checked separately as behavior.

Now run the complete path checks:

```bash
python stages/04-agentic-rag/code/checks.py
```

They inspect source offsets, Chinese features, filter order, deduplication, generation blocked by missing evidence, retention across rewrites, repeated queries, shared budgets, and rejected fabricated citations. Provider adapters use fake responses for offline tests. With optional libraries installed, additional checks execute actual local LangGraph, FAISS, Qdrant, and SDK behavior. Missing dependencies are explicitly skipped, not counted as successful integrations.

One deliberate counterexample keeps valid quotes but changes the final sentence to “Your refund has already been issued.” The local citation check accepts it. That documents its boundary: retrieval success, evidence completeness, quotation provenance, and correct prose are four properties that can fail independently.

## 14. Finish this inquiry with evidence before connecting the next system

Try a few variations that still belong to Lin's task. Select `--case earlier` and inspect the current document's older-order transition rule, rather than assuming the file version alone decides the window. Use `--top-k 6` when needed to separate ranking limitations from evidence completeness. Reduce the chunk character limit and inspect fragmented conditions. Change 45 in the fictional source, reconstruct the index, and check whether the excerpts actually change instead of reproducing a hard-coded success response.

Set the dynamic entry's `--max-evidence-chars 1` as another counterexample. Almost no passage can fit, so the program must stop within its limits without silently enlarging the budget. Live model prose requires separate inspection, especially around date applicability, uncovered topics, and whether “may apply” has become “already processed.” Correct offline control flow does not substitute for live semantic evaluation.

At the beginning, the question looked like a choice between remembering 30 and remembering 45. It is now an evidence process: restrict the sources, preserve conditions, retrieve the necessary passages, and explain them. When material is missing, search for the gap within a bound or explicitly stop. Evidence retained in this run does not imply cross-process recovery or a permanent citation audit trail.

Lin's next request is to let a documentation team maintain the policy collection and connect the assistant to order and ticket services. Local files and a Python retriever have shown how to use evidence, but have not agreed on how an external system advertises its capabilities, describes arguments, or returns results and errors. If every service invents a different answer, the assistant will soon need a suitcase of adapters.

[Stage 05: From Local Tools to MCP](../05-mcp/README.md) continues with that connection problem. However evidence is obtained later, the boundary stays the same: keep its source inspectable, do not invent missing facts, and do not grant execution authority to text merely because it was retrieved.
