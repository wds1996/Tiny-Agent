# Stage 04：这笔订单到底按哪份条款处理？——从查资料到 Agentic RAG

> Language: [English](README.md) | **简体中文**

[上一章](../03-stateful-orchestration/README.zh-CN.md)，小林的天气简报终于有了清楚的处理过程：取数、起草、检查，必要时修改，最后决定是否交付。我们能从状态里知道检查了哪份稿，也能解释为什么走到下一步。不过，流程再清楚，也有一个前提：程序得先拿到回答所需的资料。状态图不会替我们把一本尚未读过的手册变进模型输入。

这次，小林把助手拿到虚构的 Acme 商店试用。顾客问：“我在 2026 年 8 月 3 日下单，普通商品已经付款、完好未使用，现在是第 38 天。还能申请原路退款吗？办理审核手续需要哪些材料？”她手边恰好有一份 8 月刚更新的售后政策。旧宣传页写着 30 天，新政策则对部分订单改成了 45 天。助手应该读哪份，怎样回答，才不会把一段顺口的话说成商家的承诺？

本章始终处理这条咨询。我们先像工作人员一样翻到有关条款，再把找资料的过程交给程序；等一次检索能工作，再处理“只找到了半个答案”的情况。商店、条款和日期都属于教学设定，不是现实商家的政策。本章也没有订单验证或支付接口，顾客提供的情况只能作为这道题的前提，不能当成已经核实的交易记录。

## 1. 先把书翻开：这道题缺的是依据，不是一个更复杂的循环

先不安装向量数据库，也不着急给模型起一个“高级客服”的名字。直接打开 [`acme-refunds-v2.zh-CN.md`](code/data/acme-refunds-v2.zh-CN.md)，在“新订单的原路退款期限”里，可以找到：2026-08-01 当日及之后下单的已付款普通商品，可在下单后 45 个日历日内申请原路退款；下单日是第 0 天，第 45 天仍包含在内。这个条件还要求商品完好、未使用，定制品和已交付数字商品不在其中。

因此，**按照顾客提供的条件**，8 月 3 日的这笔普通商品订单走到第 38 天，还在申请窗口内。但顾客问了两件事。期限条款只回答了第一件；要回答“需要哪些材料”，还得继续读“提交材料与审核手续”，它要求订单编号、退款原因及商品状态资料，并说明客服核验、授权人员审核和支付系统执行是不同的事情。

现在可以给出一段有出处的说明：这笔订单按题设尚未超过申请期限，应提交上述材料并等待核验与审核；这里没有发生退款。只读到“45 天”就说“已经给您退了”，像是看见医院挂号成功便宣布手术结束，跨过去的步骤未免多了一点。

我们刚才做的事，就是 **RAG（Retrieval-Augmented Generation，检索增强生成）** 最基本的思路：回答前先找相关资料，再把资料与问题一起交给生成模型。检索负责把候选段落找来，生成负责阅读、组织说明。它没有修改模型权重，也没有把文件永久“训练进”模型；这次能参考新政策，是因为应用在这次输入里提供了它。

把实际发生的事连起来，只需要这样理解：

```text
顾客的问题 → 找到相关条款 → 检查是否够用 → 依据条款回答
                                  └─ 不够 → 说明缺少依据
```

这与上一章不是两套互不相干的技术。上一章解决怎样组织处理过程，这一章补上其中一个关键步骤：这个过程要用的外部事实，究竟从哪里来。

## 2. 书架上为什么同时留着旧版和别家商店的条款？

小林把资料整理进 `code/data/`；每份资料的身份和范围记录在 [`manifest.json`](code/data/manifest.json)。里面有现行售后政策、配送与发票说明，也有归档的旧版政策和另一家虚构商店的条款。每份都有中英文，因此是八个文件；按小节整理后，默认得到十八个检索片段。不是十八篇互不相关的知识点，而是同一个商店案例需要的资料和对照资料。

故意保留旧版很重要。如果书架上只有正确答案，检索器几乎不用学习“该排除什么”。旧版的“30 天退款”可能比现行政策更短、更像查询词，另一家商店的条款也可能写得非常明确。然而，词句相似并不能让别家的承诺适用于 Acme。

[`manifest.json`](code/data/manifest.json) 给每份文件记录来源编号、标题、版本、商店、语言和发布状态。正文回答“规则是什么”，这些附带信息回答“它属于谁、是哪一版、能不能在当前范围使用”。这种附带信息就是 **metadata（元数据）**。应用把这些字段读成 `Source`，再和完整正文放进 `Document`。

本例的检索范围由应用创建，不让模型自己填写商店名称或取消发布状态限制。`Scope.accepts()` 表达了最基本的候选资格：

```python
def accepts(self, chunk: Chunk) -> bool:
    source = chunk.source
    return (source.tenant == self.tenant and source.language == self.language
            and source.status == "published")
```

这只是教学程序的范围规则，不是完整登录授权。真实应用应从可信身份和文档管理规则确定范围，不能相信用户在输入框写“我是管理员”，也不能把模型返回的商店名称当权限。这里的语言由运行选项明确选择，两种语言各自检索，不假装已经解决跨语言搜索。

还有一个容易踩的坑：**现行文件不等于每笔订单都用新期限。** 当前政策本身保留了“8 月 1 日之前的订单仍按 30 天处理”的过渡条款。排除归档文件之后，仍然要根据订单日期读对小节。发布状态由资料维护者标记；检索分数不会替你判断一份文件是不是最新、更不会审核这份文件的内容是否正确。

来源确定以后，才适合讨论怎么找得快。否则，一个更快的搜索器只会更快地把错误版本递到面前。

## 3. 不把整本书递过去，先把能独立阅读的小节取出来

只有两页资料时，直接把全文放进模型输入并不荒唐。检索不是每个项目都必须缴纳的“入门税”。问题是资料继续增加后，一道退款问题不需要同时读取配送时效、发票处理和每一份历史版本。输入变长之外，相关条件也更容易埋在无关内容里。

所以我们把文档拆成适合检索的 **Chunk（片段）**。这里先按标题取小节，不从任意第 28 个词处落刀。以“45 天”的小节为例，期限、起算日、商品限制和示例应该一起保留；只截出“45 天”三个字，后面的模型就拿不到适用条件。

`retrieval.py` 中的片段保留这些信息：

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

`id` 用于定位片段，`source` 保留文档身份，`heading` 让我们知道它在谈什么。`start` 和 `end` 是这份原文中的 Python 字符位置，所以 `document.text[start:end]` 必须能取回原样正文。它们不是 UTF-8 字节位置，也不是模型的 Token 位置。`topic` 是资料整理时给小节起的标签，不是搜索模型猜出的事实。

如果一个小节过长，切块器才使用带重叠的字符窗口。相关代码是：

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

默认 `max_chars=1200`，`overlap=80`；相邻窗口会重复一部分字符，降低一句条件恰好被切断的概率，但这不是保留完整语义的保证。中文不靠空格分词，所以不能直接把英文的 `text.split()` 当成通用切块方法。

这里还做了一件保守的事：长小节被拆开后，每个碎片的 `complete_section` 都是 `False`。后面的本地检查不会因为命中一个碎片，就宣布整项规则已经收齐。完整小节也不保证一定能回答问题；这个标记只说明“有没有被这个切块器拆开”。真正的大型资料可以采用邻近段落展开、父小节回取等办法，但不能把重叠本身误称为完整性验证。

切块越小，条件被拆散的风险越高；切块越大，一个片段又可能混入多个问题。合适大小取决于原文和任务。本例的默认小节都能完整容纳；把窗口故意缩小，正好可以观察它为什么不再足够。

## 4. 人会找“退款那一页”，程序怎样找？

现在有了十八个片段，小林的问题却只是一段文字。程序需要一个办法，把可能有关的条款排在前面。最容易理解的起点是看共同词语：“原路退款”“期限”“审核材料”出现在哪些小节里？这不是落后的办法，精确术语本来就是有用的检索线索。

为了把这种线索写成可以比较的数字，我们给每个词项安排一个位置。可以先想象只有“退款、期限、审核”三个位置：一个小节在每个位置上的数值，表示这个词项在小节中的权重。这一串数就是向量，不需要先学会神经网络才能理解它。

本例使用 **TF-IDF** 做一个可解释的词项向量基线。TF 大致反映词出现的次数；IDF 会降低到处都出现的词的区分力。假如每一页都有“顾客”，这个词就不太能帮助我们分辨是退款期限还是发票说明。初始化时，代码统计每个词出现于多少个片段，并在同一份语料上建立词表与权重：

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

查询也必须使用这张词表和这组权重，而不能另建一套坐标。`embed_query()` 用实际词频填入每个位置，再进行归一化：

```python
def embed_query(self, text: str) -> list[float]:
    counts = Counter(tokenize(text))
    vector = [counts[term] * weight for term, weight in zip(self.vocabulary, self.idf)]
    return normalize(vector)
```

`tokenize()` 对英文取普通词项，对连续中文使用相邻两个字的组合，例如“退款手续”可产生“退款、款手、手续”。这只是本地可观察的特征提取，不是 DeepSeek 使用的 Tokenizer，也不等于中文分词已经完美解决。`embed_documents()` 与 `embed_query()` 使用一致的表示，正是为了让同一个位置始终有同一个含义。

**这个类虽然提供 embedding 接口，但它不是经过训练的语义模型。** 用户说“钱沿着付钱的路退回来”，资料写“原路退款”，词项基线可能联系不起来。真正的神经网络 Embedding 可以学习不同表述之间的关系，但也不保证理解所有否定、日期或例外。生成答案的 DeepSeek 和负责向量化的组件是两份工作；替换生成模型，并不会自动改变检索表示。

至此我们只把“文字有什么检索线索”变成了数字，还没有判断任何退款结论。下一步才是比较这些数字。

## 5. 分数高，只表示排得靠前，不表示“退款有九成把握”

假设一个小节反复谈原路退款和申请期限，另一个主要谈配送。查询向量与第一个小节的方向通常更接近。**余弦相似度**就是比较向量方向的一种方式：

$$
\mathrm{cosine}(a,b)=\frac{a\cdot b}{\lVert a\rVert\lVert b\rVert}
$$

先把每个向量缩放到长度为 1，再把对应位置相乘并求和，就得到了这个值：

```python
def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise ValueError("Vector dimensions differ")
    return sum(a * b for a, b in zip(normalize(left), normalize(right)))
```

`normalize()` 会拒绝空向量和非有限数值；全零向量按本例约定保留为零，因此与其他向量的相似度为零。一般实数向量的余弦在 -1 到 1 之间；本例 TF-IDF 权重非负，实际分数通常在 0 到 1 之间。`0.82` 是这个表示和这次查询下的排序信号，不是“82% 的退款成功率”，更不是条款真实性证明。

进入比较之前，候选必须先符合前面确定的范围。`InMemoryVectorRetriever.retrieve()` 的主体是：

```python
for chunk, stored in zip(self.chunks, self.vectors):
    if not scope.accepts(chunk):
        continue
    score = cosine_similarity(vector, stored)
    if score > 0.0:
        ranked.append(SearchResult(chunk, score))
return sorted(ranked, key=lambda hit: (-hit.score, hit.chunk.id))[:top_k]
```

这段代码先排除别的商店、另一种语言和归档文件，再比较剩余片段。`top_k` 表示最多取前 K 项，不保证总能得到 K 项。没有正分候选时返回空列表；在这个词项基线里，它表示缺少词项匹配信号，不等于“所有知识库都没有答案”。换成神经表示后，阈值更需要单独验证，不能沿用某个小数就宣布可靠。

先在仓库根目录运行这一步，不需要模型密钥：

```bash
python stages/04-agentic-rag/code/retrieval.py
python stages/04-agentic-rag/code/retrieval.py --language en
```

检查每一项的来源、小节名、版本和分数，别只看第一名。检索返回的是 `SearchResult(chunk, score)`，不是“同意退款”。程序把片段身份与正文放在一起，后续才能确认引用的是哪一份资料。

这个内存实现逐项比较合格片段，适合小语料和观察机制。建立片段向量发生在创建检索器时，处理问题时才生成查询向量。资料更新以后要重新建立相应表示；仅修改磁盘文件，不会自动修改已经构造好的内存索引。

## 6. 先找候选，再决定把哪几页放到桌上

第一次检索如果只取一项，很可能只得到“申请期限”，漏掉审核材料。把所有结果都发给模型也不是最佳答案：此时它又得读一堆同问题关系很弱的条款。小林需要的是足够完整、又不过量的材料。

我们因此区分两个数量：`candidate_k` 是初筛候选数，`top_k` 是进一步排序后本次保留的数量。默认先取六项候选，再做一次很简单的 **reranking（重排）**，比较查询词项在每个候选中的覆盖情况：

```python
query_terms = set(tokenize(query))
def key(hit: SearchResult) -> tuple[float, float, str]:
    coverage = len(query_terms & set(tokenize(searchable_text(hit.chunk)))) / max(1, len(query_terms))
    return (-coverage, -hit.score, hit.chunk.id)
return sorted(candidates, key=key)[:top_k]
```

这里返回的仍是原候选，只改变排序，分数仍保留原来的向量相似度，不能把它误读成新的模型评分。这也是重排的边界：初筛根本没找到审核条款，重排器不会在空气里把它造出来。

本例的覆盖率排序只是另一个词项规则，并不是总比初筛好。更强的重排器可以让一个 CrossEncoder 同时阅读查询和候选，逐对打分；它多做了工作，也需要测是否值得。[Sentence Transformers 的检索与重排说明](https://www.sbert.net/examples/sentence_transformer/applications/retrieve_rerank/README.html)给出了这类两阶段结构。

排好序之后还要控制材料总量。`pack_evidence()` 按片段 ID 去重，只接纳能够完整放入当前字符预算的段落：

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

正文预算默认是 6000 个字符、最多八个片段。太长的片段会被跳过，不会偷偷切掉最后一句“但定制商品除外”来凑长度。字符预算不是 Token 预算，也不包含系统规则等全部输入；真实模型客户端还会检查序列化输入的总字符数。

这个选择也有代价：按已有顺序装材料，可能让早来的相关性较低片段占住空间。我们没有宣称它是最优上下文选择器。预算不足而放不下必要条件时，正确行为是承认证据不齐，而不是把缺少的条件当不存在。

## 7. 两段都找到了，才能回答这条两部分的问题

现在回到顾客原话：“还能申请原路退款吗？审核需要哪些材料？”一个片段只讲期限，即使分数最高，也只回答了半道题。我们需要区分三件事：它是否相关，它是否足够，以及它适不适用于这个问题。三者不能压成一句“有结果就回答”。

`BasicRAG` 采用一条固定路径：检索一次，整理证据，检查是否足够，再生成。它不会在检查不通过后自动增加搜索。关键位置如下：

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

这里第一次出现 `policy.assess()`，先说清它负责什么：阅读原问题和当前材料，提出“可以回答”或“还缺什么”的判断。它交回的是结构化数据，而不是一句含糊的“应该差不多了”：

```python
@dataclass(frozen=True)
class EvidenceDecision:
    sufficient: bool
    evidence_ids: tuple[str, ...]
    reason: str
    rewritten_query: str = ""
```

`sufficient=True` 时必须列出实际支持判断的片段 ID；不足时则不给出获准证据，可以提出新的检索词。应用还会检查这些 ID 是否真的在当前材料里、是否属于允许范围、是否仍与本次索引中的正文一致。模型不能编一个存在感很强的文档编号，就让引用获得来源。

为了先观察这一条线路，离线入口使用 `ChecklistPolicy`。**它是明确的教学替身，不是能够判断任意语义的审核模型。** 本章通过 `--case` 选择已经配置的业务题；“新订单退款与材料”这道题的应用清单要求 `window-new` 与 `approval` 两类完整小节。替身检查的是这张清单有没有收齐，不是通过标题证明每一句结论。真实服务需要对每类请求确定证据要求，并真正阅读适用条件；不能把本例的小节标签包装成通用事实核验算法。

配套的 `ExtractiveAnswerer` 也不冒充 LLM：它把选中段落原样取出，附上 ID，便于确认资料确实经过了这条线路。

```python
class ExtractiveAnswerer:
    """Return the selected source text verbatim; no LLM and no inferred eligibility."""
    kind = "extractive"
    def answer(self, task: RAGTask, evidence: Sequence[SearchResult]) -> AnswerDraft:
        text = "\n\n".join(f"[{hit.chunk.id}] {hit.chunk.text}" for hit in evidence)
        return AnswerDraft(text, tuple(Citation(hit.chunk.id, hit.chunk.text) for hit in evidence))
```

运行固定路径：

```bash
python stages/04-agentic-rag/code/basic_rag.py --show-evidence
python stages/04-agentic-rag/code/basic_rag.py --top-k 1
```

第一条默认保留三项，随后选出期限和审核两段，显示 `status: answered`、`answer_kind: extractive`；这里的“answered”只表示走完了当前答案契约，不代表做了智能推断。第二条只留一项，应该得到 `insufficient_evidence`，没有最终答案。你仍能看到找到过的段落，只是不能把半份材料当完整回复。

这道题中的订单日期、状态和第 38 天也只是明确提供的假设。检索政策不会顺便核实用户是谁、订单是否真实。我们现在已经把该读的内容送到了桌上，接下来才请真正的模型把它解释成顾客容易理解的话。

## 8. 接入 DeepSeek，让它读材料，而不是背印象

[`deepseek_rag.py`](code/deepseek_rag.py) 用真实 DeepSeek 同时实现证据判断和最终生成，复用前面的检索器与执行顺序。默认路径最多两次模型请求：第一次判断当前证据能否回答，第二次组织带引用的回复。若第一次就判定不足，第二次不会发生。

传给模型的是原问题、输出语言、题设事实和选中的证据，不是整个索引，也不是应用的全部状态：

```python
def task_payload(task: RAGTask) -> dict:
    # Application budgets, tenant scope and reference labels are not model decisions.
    return {"question": task.question, "language": task.scope.language, "provided_facts": dict(task.facts)}
```

证据另外编码成包含 ID、标题、小节名、版本和正文的 JSON 数据。检索分数不当成“答案置信度”交给模型，测试参考 ID 也不会进入提示词。商店范围和次数限制留在应用中，模型的返回 Schema 根本没有“放宽检索范围”这个字段。

调用方式仍与前几章一致，使用 DeepSeek 的 Responses 接口：

```python
response = self.client.responses.create(
    model=self.model, instructions=instructions, input=encoded,
    text={"format": {"type": "json_schema", "name": name, "schema": schema}},
    tools=[], tool_choice="none", max_output_tokens=4096,
)
```

`text.format` 指定 JSON Schema；证据判断与答案使用不同 Schema。`tools=[]` 和 `tool_choice="none"` 说明这次只有数据判断和文字生成，没有支付、写文件或搜索网页等执行能力。DeepSeek 返回的响应必须完成，JSON 必须能解析，字段与类型也要通过本地检查。[接口文档](https://api-docs.deepseek.com/api/create-response/)列明了结构化输出与输入格式，兼容 SDK 并不意味着可以忽略服务实际支持的参数。

最终答案除了 `text`，还包含 `citations`，每项带 `evidence_id` 和一小段原文 `quote`。程序会要求引用指向实际送入生成的片段，且引文确实出现在该片段里：

```python
quote = citation.quote
if not isinstance(quote, str) or not quote.strip() or quote not in by_id[citation.evidence_id].text:
    raise ValueError("Citation quote is absent from its cited passage")
ids.append(citation.evidence_id)
```

**引文存在，不代表结论一定被引文支持。** 模型完全可能引用了“需要审批”的原话，却在结论里写“已经退款”。这段校验拦得住不存在的引用，却不能自动解决语义矛盾。测试保留了这样的反例，避免把“引用契约通过”升级成“答案完全正确”。模型判断证据充分也可能出错；重要结论仍要核对条件、引用与结论是否一致。

同样，政策正文里即使混入“忽略上面的规则”，它仍只是被读取的数据。JSON 包装和提示词有助于表达来源，但不是防注入的安全证明。本程序不把文档转成系统规则，不根据它执行 Python，也没有把密钥放进证据输入。它并不承诺模型永远不会受不可信内容影响；它只是明确限制这里能发生哪些程序行为。

在仓库根目录安装真实模型入口需要的依赖，并配置当前账户可用、且支持 Responses 接口的模型：

```bash
python -m pip install -r stages/04-agentic-rag/code/requirements.txt
export DEEPSEEK_API_KEY="your-deepseek-api-key"
export DEEPSEEK_MODEL="deepseek-flash"
python stages/04-agentic-rag/code/deepseek_rag.py --show-evidence
```

PowerShell 中两条环境变量设置对应为 `$env:DEEPSEEK_API_KEY="your-deepseek-api-key"` 与 `$env:DEEPSEEK_MODEL="deepseek-flash"`。模型名是文档示例，不是永久不变的账户能力；以当前服务支持为准。入口会实际请求服务并产生用量，缺少密钥、依赖或响应失败时不会偷偷返回离线答案。

按当前材料，合理回复应区分“按题设仍在 45 天申请窗口”与“需要提交资料并审核”，并明确没有执行退款。文字不要求和离线摘录逐字一致。现在我们已经有一条能真正调用模型的固定 RAG 流程；下一处问题是，第一次递到桌上的材料可能并不完整。

## 9. 第一次只找到期限，第二次该搜什么？

把固定入口的 `top_k` 改成 1 后，程序找到了期限条款，却没有审核材料。小林这时不需要助手再重复一句“退款期限”，而是希望它指出缺口：“现在还不知道要提交哪些材料，下一次应找审核手续。”这才是继续搜索的理由。

**Agentic RAG** 在这里指把这样的反馈判断放进检索控制：读取已有材料，决定回答、补搜，还是停止。名字里的 Agentic 不是因为多画了一个节点，而是因为新的证据会影响接下来的行动。真实模型版本会阅读材料并提出改写；离线版本仍使用前面的清单替身，只用来观察控制行为。

新的检索词可以是“提交材料 退款审核手续 授权人员”，而不是把原问题整个重复一遍，更不应该写成“这笔退款肯定获批，找到证明”。改写应对准缺少的信息，不能偷偷换题、放宽商店范围，或把猜测结论塞进查询后再拿搜索结果证明猜测。

补搜之后还要保留第一次已经找到的期限。`RAGNodes.search()` 会先合并新旧片段、去重和限制总量，再清掉针对旧材料的判断：

```python
chosen = lexical_rerank(query, candidates, top_k=self.top_k)
evidence = pack_evidence([*state["evidence"], *chosen],
                         max_chars=self.max_evidence_chars, max_items=8)
ids = ", ".join(hit.chunk.id for hit in chosen) or "none"
return dict(**common, evidence=list(evidence), assessment=None, selected=(),
            next_node="assess", events=[f"search: {ids}; retained={len(evidence)}"])
```

这里 `evidence` 是当前保留的资料集合，`selected` 是获准送去生成的子集。两者分开，才能知道“检索过哪些资料”和“最后依据哪些资料”不是同一件事。每次加入新材料以后重新判断，而不是把上一次的 `sufficient` 沿用到另一组证据上。

现在运行这个受限的补搜实验：

```bash
python stages/04-agentic-rag/code/agentic_rag.py --show-evidence
```

默认一次只从候选中选一个新片段。第一次拿到 `window-new`，判断缺少 `approval`；第二次搜索审核手续，把两段一起交给判断组件，最后返回有引用的原文摘录。可以在输出中检查 `searches: 2`、`rewrites: 1` 和两次查询，不必相信程序自己说“我认真查了”。

这个实验**没有证明动态检索永远优于固定 RAG**。固定入口默认 `top_k=3`，本来就能一次收齐两段；把动态入口改成 `--top-k 3`，也只会搜一次。我们故意收窄单次选择量，是为了看清缺失证据怎样驱动下一次搜索。实际选择应比较资料质量、额外调用和失败路径，而不是认为“再调用一次模型”必然更聪明。

## 10. 用上一章的状态和节点，把补搜过程接住

一旦允许补搜，程序就需要记住原问题、正在搜什么、已经拿到什么，以及还剩多少继续的空间。这正是上一章的 State；不是因为学过图就必须画图，而是眼前这些事实确实决定下一步。

本章的运行状态如下：

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

原始任务保留在 `task`，改写只更新 `query`。`query_history` 记录尝试过的查询，`searches` 计检索次数，`rewrites` 计实际接受的改写。`assessment` 与 `selected` 描述当前证据判断；`status` 和 `answer` 则区分成功生成、证据不足及程序失败。它们不会全部作为模型输入发送出去。

主体流程只有四份工作：`prepare` 判断是否为明确的问候入口，`search` 找资料，`assess` 检查能否回答，`answer` 生成并验证引用。问候入口只返回一条普通招呼，不检索。这里的入口类别来自演示选项，不声称程序能够靠几条字符串规则识别任意用户意图。

```text
prepare → search → assess ── 材料够用 ──→ answer → 结束
                     │
                     ├─ 不足且允许改写 → search
                     └─ 无法继续       → 保留证据，说明不足
```

[`agentic_rag.py`](code/agentic_rag.py) 先用普通循环运行这些节点；[`langgraph_agentic_rag.py`](code/langgraph_agentic_rag.py) 再用 LangGraph 表达相同节点与出口。条件边只根据已经产生的结果选路，不在选路函数里偷偷发起查询：

```python
builder.add_conditional_edges("assess", lambda state: state["next_node"],
                              {"search": "search", "answer": "generate_answer", "end": END})
builder.add_edge("generate_answer", END)
```

图中的 `generate_answer` 调用的就是同一个 `nodes.answer`。两种执行方式不另外复制一份证据判断规则。`query_history` 与 `events` 使用追加 Reducer，每次只返回本次新记录；`evidence` 由搜索节点明确合并后整体替换；当前判断、当前选择和最终答案都是替换字段。随便给每个列表都加一个追加规则，反而会让旧选择和旧判断混进新一轮。

安装可选框架依赖后，可以观察同一条路径：

```bash
python -m pip install -r stages/04-agentic-rag/code/requirements-frameworks.txt
python stages/04-agentic-rag/code/langgraph_agentic_rag.py --show-evidence
```

入口只执行一次流式运行：

```python
for state in graph.stream(initial_state(task, args.initial_query), stream_mode="values",
                          config={"recursion_limit": 30}):
    print("graph position:", state["next_node"], "searches:", state["searches"])
```

`values` 是每一步的完整当前状态，`updates` 则侧重各节点的新更新，区别见 [LangGraph Streaming](https://docs.langchain.com/oss/python/langgraph/streaming)。这里取最后一个状态作为结果，不在 `stream()` 之后又 `invoke()` 一次。`TypedDict` 和 Reducer 的职责与[上一章及官方 Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)一致：表达字段与合并方式，不替业务完成来源验证。

真实模型入口使用相同的节点和图，只把判断与生成换成 DeepSeek：

```bash
python stages/04-agentic-rag/code/langgraph_deepseek_rag.py --show-evidence
```

运行前需要同时完成前面的模型依赖、框架依赖和环境变量配置。一次补搜最多带来两次证据判断、一次答案生成；真实模型是否选择补搜、是否觉得证据足够，要看实际响应，不预先保证它重演离线轨迹。

## 11. 找不到，不等于可以一直找下去

小林接着问：“如果手册压根没有量子设备保修条款，助手会不会换十个说法，最后编出一个听起来像真的答案？”这时必须由应用决定继续的边界，而不是让模型自己评估今天还剩多少热情。

本例默认最多一次改写，因此最多两次检索。证据判断后的控制代码是：

```python
query = decision.rewritten_query.strip()
if state["rewrites"] >= self.max_rewrites or not query:
    return self.stop("insufficient_evidence", decision.reason, assessment=decision)
if query_key(query) in {query_key(old) for old in state["query_history"]}:
    return self.stop("insufficient_evidence", "Repeated query", assessment=decision)
return dict(assessment=decision, query=query, rewrites=state["rewrites"] + 1,
            next_node="search", events=[f"rewrite: {decision.reason}"])
```

`query_key()` 先统一大小写、空白和部分 Unicode 形式，再判断是否重复。把同一个英文查询改成全大写，不算新策略。不同措辞表达同样意思仍可能绕过这种文本去重，但总次数上限还在；这里没有把字符串比较吹成语义去重。

真实判断与生成还共享同一个模型请求预算。默认最多三次，每次发出请求前计数，失败也占用；客户端设置 `max_retries=0`，不会在背后增加自动尝试。一次请求的 `timeout=30.0` 不是整个任务严格三十秒结束的承诺，字符预算也不是精确费用预算。

需要区分两个结局：正常查完却没有足够条款，是 `insufficient_evidence`；检索器报错、模型超时、结构错误或引用无效，是 `failed`。两者都没有最终答案，但前者是可接受的知识边界，后者是需要排查的程序问题。失败时仍保留已取到的材料和尝试记录，不把原始异常中的敏感请求内容打印成顾客答复，也不自动重试。

实际运行这两道反例：

```bash
python stages/04-agentic-rag/code/agentic_rag.py --max-rewrites 0
python stages/04-agentic-rag/code/agentic_rag.py --case unknown
```

第一条只找到期限后就停下；第二条即使命中“本文件不覆盖量子设备保修”的相关段落，也不能把它变成保修规则。`insufficient_evidence` 是明确的正常结果，CLI 不把它当 Python 崩溃；`failed` 才以退出码 1 结束。要确认业务是否答出问题，应读状态，而不是只看终端有没有红字。

## 12. 资料多起来，再替换负责搜索的那一层

到这里，找资料、检查缺口和回答已经接起来了。若条款扩展到成千上万段，逐个用 Python 计算可能不再合适；这时才需要考虑专门的向量索引或数据库。我们不换题，仍用同一份退款政策、同一组向量和同一个检索范围来比较。

**FAISS** 的 `IndexFlatIP` 是一个容易核对的基线：它用内积做精确、穷举的向量搜索。文档向量和查询向量都归一化后，内积就是余弦相似度。核心操作如下：

```python
faiss.normalize_L2(matrix)
faiss.normalize_L2(query_vector)
backend = faiss.IndexFlatIP(matrix.shape[1])
backend.add(matrix)
scores, positions = backend.search(query_vector, min(top_k, len(eligible)))
```

这里先在应用侧筛出合格片段，再建立这个小索引，因此不是“全库 Top-K 以后才把别人的内容扔掉”。`min(top_k, len(eligible))` 和结果位置检查避免候选不足时把无效位置当成最后一个片段。为了演示，函数每次构建索引；实际服务通常会复用并更新索引，而不是把建库时间算进每次查询。

`IndexFlatIP` 仍比较全部索引向量，不会因为用了 FAISS 就自动变成近似搜索。更大规模时可以再研究近似索引及召回取舍，但它们不是本例的性能保证。归一化与距离的关系见 [FAISS 距离说明](https://github.com/facebookresearch/faiss/wiki/MetricType-and-distances)。正文、版本和权限的管理责任也不会因为有了索引就消失。

**Qdrant** 则把向量与 payload 放在 point 中，查询能够同时携带过滤条件。本例的本地内存模式保存片段 ID、商店、语言和状态，使用同一组限制：

```python
filters = models.Filter(must=[models.FieldCondition(key=key, match=models.MatchValue(value=value))
            for key, value in {"tenant": scope.tenant, "language": scope.language, "status": "published"}.items()])
result = client.query_points("policies", query=vector, query_filter=filters,
                             with_payload=True, limit=top_k)
```

返回 ID 后，再到本次语料快照里取回正文并核对范围。`finally` 会关闭本地客户端，不在演示结束后留下连接。这里只运行内存实例，不测试远端部署或真正的多用户认证；payload 过滤也不能替代应用获取可信身份。[Qdrant Filtering](https://qdrant.tech/documentation/search/filtering/)解释了这种条件组合。

安装前一节的框架依赖后，分别运行：

```bash
python stages/04-agentic-rag/code/vector_backends.py --backend faiss
python stages/04-agentic-rag/code/vector_backends.py --backend qdrant
```

两个入口仍默认使用词项向量。它们改变的是“在哪里、怎样搜索向量”，不是“怎样理解中文隐喻”。要研究后者，可以另装 `requirements-neural.txt`，提供一个已经下载好的、适合所用语言和检索任务的 Sentence Transformers 模型目录，再使用 `--embedding-model /path/to/local/model`。适配器用同一模型编码文档与查询，不会隐式联网下载权重。更换表示后需要重新编码全部片段，不能只换查询向量而保留旧索引。

训练过的语义表示可能改善改写匹配，但也需要比较实际结果。[Sentence Transformers 的语义检索说明](https://www.sbert.net/examples/sentence_transformer/applications/semantic-search/README.html)介绍了查询与文档编码的用法。我们没有把“神经模型”“向量数据库”和“答案正确”当成一件事：前者产生表示，中间层找候选，最后仍需判断证据及回答是否成立。

## 13. 用同一条咨询检查检索，而不是只看最后一句好不好听

小林已经知道默认题能跑，她更想知道改动切块或排序以后，会不会漏掉审核材料。不能每次只看答案语气，因为模型可能在没看到材料时凭印象把材料说对，也可能引用正确却解释反了。

先给检索单独出题。当前退款问题需要 `window-new` 与 `approval` 两段；如果前两名只有期限和发票，真正相关的两段只找到一段。**Recall@K** 在本例按片段计算，就是前 K 项覆盖了多少个参考片段：

```python
def recall_at_k(retrieved_ids: Sequence[str], relevant_ids: set[str], *, k: int) -> float:
    positive_int(k, "k")
    if not relevant_ids:
        raise ValueError("Recall is undefined here without relevant passages")
    return len(set(retrieved_ids[:k]) & relevant_ids) / len(relevant_ids)
```

不能只检查“有没有命中 Acme 政策这个文件”。同一文件中，命中配送外的无关小节并不等于找到了审核材料。重复返回同一个正确片段也只计一次，不会通过重复凑出更高召回。

另一个问题是第一段有用材料排在哪里。**Reciprocal Rank（倒数排名）** 在前 K 项里找到第一个相关项，取其排名的倒数：

```python
def reciprocal_rank(retrieved_ids: Sequence[str], relevant_ids: set[str], *, k: int) -> float:
    positive_int(k, "k")
    if not relevant_ids:
        raise ValueError("Reciprocal rank needs nonempty reference evidence")
    return next((1 / rank for rank, ident in enumerate(retrieved_ids[:k], 1)
                 if ident in relevant_ids), 0.0)
```

排第一是 1，排第二是 0.5，截断范围内没找到是 0。多道题取平均得到这里的 MRR@K。它可能在只找到一段材料时已经得 1，所以不能代替需要两段同时存在的完整性检查。

运行小型检索评测：

```bash
python stages/04-agentic-rag/code/evaluation.py --k 3
```

八道中英文题包含直接术语，也包含“钱能沿着付钱的路退回来吗”这样的说法。程序打印每题实际 ID，再算平均，而不是只给一个漂亮总分。词项基线在改写题上会暴露不足；这正是要观察的结果，不需要把难题删掉才能证明程序有用。

这些题是公开可见的开发案例，不是独立保留的线上效果评测。参考片段 ID 只在评测代码中使用，不作为生成模型的答案提示。没有相关条款的题不适合硬塞进这里的 Recall 分母，程序会拒绝空参考集合；“未知事项是否停止”单独做行为检查。

再检查整条业务线路：

```bash
python stages/04-agentic-rag/code/checks.py
```

检查既验证片段位置、中文特征、过滤顺序和去重，也验证遗漏审核材料时不生成、改写后保留已有证据、重复查询停止、预算共享及伪造引用被拒绝。适配器使用伪响应做离线检查；安装可选库后，还会实际检查 LangGraph、FAISS、Qdrant 和 SDK 的本地行为。缺少依赖会明确显示跳过，不能把跳过算成框架已运行。

其中有一个刻意保留的反例：把最终文字改成“已经退款”，却保留完全正确的引文，本地引用检查仍会通过。它让我们看见这份保证的边界。检索命中、材料完整、引文存在和自由文字正确，是可以分别验证、也可以分别出错的四件事。

## 14. 再接一条真实需求之前，先带着证据把这件事讲完

最后做几个仍围绕小林工作的问题。把 `--case` 换成 `earlier`，检查现行文件里的旧订单过渡规则，而不是从文件版本猜适用期限；必要时用 `--top-k 6` 观察排序与证据完整性各自的影响。把切块字符数缩小，检查片段是否变得不完整。再把来源中的 45 改成另一个教学值并重新创建索引，看看摘录是否真的跟着源资料变化，而不是输出一段预先写死的成功话术。

也可以给动态入口设置 `--max-evidence-chars 1`：资料几乎放不进去，程序应在边界内说明不足，不会为获得答案偷偷放大预算。真实 DeepSeek 的自由文字还要另行阅读，尤其检查日期范围、未覆盖事项和“可以申请”是否被错误说成“已经处理”。离线线路正确，不替代真实模型的语义验收。

回到开头，我们不再凭记忆猜 30 天还是 45 天。程序先限定合适来源，保留完整条件，找到能回应问题的段落，再让模型依据这些材料解释；材料不足时可以有边界地补搜，也可以明确停下。这里的资料保留在本次运行状态里，不是自动获得了跨进程恢复或永久引用审计。

小林下一步想把政策库交给文档团队维护，同时接上订单查询和工单服务。眼前的本地文件与 Python 检索器已经说明怎样使用证据，但还没有约定：外部系统怎样告诉应用它提供哪些能力，参数怎样描述，结果与错误又怎样返回。如果每个服务各发明一套办法，助手很快就要背满一书包不同插头。

[Stage 05：从本地工具到 MCP](../05-mcp/README.zh-CN.md)就从这个连接问题继续。无论资料后来怎样被取回，今天这条边界仍然保留：来源要能核对，材料不够就不要替它补事实，外部文本也不会因为被检索到就获得执行权。
