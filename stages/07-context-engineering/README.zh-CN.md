# Stage 07：别把整个仓库搬上办公桌——Context Engineering

> Language: [English](README.md) | **简体中文**

上一章我们终于让 Agent 学会了“存档”。

Checkpoint 能让执行在进程重启后继续，Long-term Memory 能保存经过允许的用户偏好，RAG 能提供外部证据，MCP 又能从外部系统带回 Tool Result、Resource 和 Prompt。

现在麻烦来了。

我们手里的信息突然多得像搬家前一天的客厅：

```text
System Instructions
Conversation History
Checkpoint State
Long-term Memory
RAG Evidence
Tool Observations
MCP Resources
Current User Message
...
```

于是一个非常自然、也非常危险的想法出现了：

> “既然这些东西都可能有用，那每次调用模型时全部塞进去吧。”

这就像为了开一个十五分钟的退款会议，把公司档案室、财务仓库和员工食堂菜单全部搬进会议室。资料确实没有遗漏，会议也基本开不下去了。

Stage 07 解决的就是这个问题：

> **在当前这一轮决策里，模型究竟应该看到什么？**

这就是 Context Engineering。

它不是“把 Prompt 写得更文艺”，也不只是“快超过 token limit 了就删前几条消息”。更准确地说，Context Engineering 是一套**选择、组织、压缩和标记模型输入信息**的方法。

---

## 1. 先把 Context 和上一章的 Memory 分开

这是最容易混的地方。

Memory 回答的是：

> 哪些信息值得被保存？

Context 回答的是：

> 这一轮模型需要看到哪些信息？

同一条 Long-term Memory 可以存在数据库里很久，却并不需要每一轮都出现在 Context 中。

比如：

```text
用户偏好：回答使用中文
```

在写中文邮件时可能有用。

如果 Agent 正在执行一个完全不需要自然语言回复的后台数据校验任务，它可能一点用都没有。

所以：

```text
stored != selected
```

同样，Checkpoint 中的数据也不等于 Context。

Checkpoint 可能包含：

```text
retry_count
workflow_phase
idempotency_key
last_node
internal_error_code
```

这些对 Runtime 很重要，但模型可能根本不需要看到。

Stage 03 的 State、Stage 06 的 Memory 和本章 Context，分别属于三层：

```text
State
    -> 程序继续执行需要什么

Memory / Persistence
    -> 什么值得跨时间保留

Context
    -> 当前模型调用应该看什么
```

把它们分开以后，很多设计问题会突然简单很多。

---

## 2. Context Window 不是仓库，是一张有限的办公桌

模型的 Context Window 有容量上限。

即使某个模型的窗口已经很大，也不代表“越多越好”。

原因有两个。

第一个最容易理解：输入越多，通常意味着更多成本和延迟。

第二个更关键：**无关信息也会参与模型的注意过程。**

你问：

> “ORDER-42 能不能原路退款？”

真正相关的也许只有：

```text
退款政策
订单日期
当前用户问题
```

如果同时塞进去：

```text
用户去年的旅行偏好
过去 80 轮对话
三个无关 Tool 的输出
团队周报
旧版退款政策
```

模型不只是多读了几页纸。

你还主动增加了冲突、误引用和被过时信息带偏的机会。

所以 Context Engineering 的目标不是：

> “把窗口填满。”

而是：

> **让有限的输入预算尽可能被当前决策真正需要的信息占据。**

---

## 3. Context Budget：先承认预算存在

我们先写一个很朴素的预算：

```python
@dataclass(frozen=True, slots=True)
class ContextBudget:
    max_input_tokens: int
    reserved_output_tokens: int = 0
```

为什么还要 `reserved_output_tokens`？

因为有些模型接口给的是整体上下文限制。输入塞得太满，输出就没有空间。

于是：

```python
usable = max_input_tokens - reserved_output_tokens
```

本章教学代码使用一个粗略 token estimate：

```python
return max(1, (len(self.content) + 3) // 4)
```

请注意：这不是精确 tokenizer。

它只是为了让选择算法离线可观察。

真实系统如果需要精确计费或硬限制，应该使用对应模型 tokenizer 或 provider 返回的 usage 信息。

不要把“平均四个字符约一个 token”这种教学近似写进财务结算系统，然后怪语言模型数学不好。

---

## 4. Context Item：不要让所有文本都变成匿名字符串

如果 Context Builder 接收的是：

```python
[
    "some text",
    "more text",
    "another text",
]
```

很快就会回答不了几个重要问题：

- 这是谁提供的？
- 它是什么类型？
- 是必须保留还是可以丢？
- 和当前任务相比有多重要？
- 它来自用户、Memory、Retriever，还是 Tool？

因此我们给 Context Item 加上结构：

```python
@dataclass(frozen=True, slots=True)
class ContextItem:
    key: str
    content: str
    kind: str
    priority: int
    required: bool = False
    provenance: str = "application"
```

这一步看起来有点像给文件贴标签。

实际上很重要。

因为 Context Engineering 的核心不是字符串拼接，而是**信息选择**。

没有 metadata，你连“选择依据”都没有。

---

## 5. 有些 Context 是 Required，不应该靠打分竞争

假设系统要求：

```text
只能根据提供的政策证据回答，证据不足时明确说明。
```

同时当前问题是：

```text
ORDER-42 可以原路退款吗？
```

这两项不是“如果预算够最好留下”。

它们是当前调用成立的前提。

于是：

```python
ContextItem(
    key="instructions",
    ...,
    required=True,
)
```

Builder 先计算 Required Context 的成本。

如果它已经超过预算，本章实现直接抛出：

```python
ContextOverflowError
```

为什么不偷偷删一点 Required 内容？

因为如果“不能删除的东西”在超限时还是被悄悄删除，那 `required=True` 就只是一个安慰奖。

有些失败应该 Fail Closed。

这和 Stage 09 以后会不断出现的可靠性原则是一脉相承的。

---

## 6. Optional Context 才需要 Priority

Required 放进去以后，剩余空间才交给 Optional Items 竞争。

本章使用一个非常简单的规则：

```python
sorted(
    optional,
    key=lambda item: (-item.priority, item.key),
)
```

高 Priority 先选。

例如：

```text
retrieved policy evidence   priority 90
recent tool observation     priority 80
history summary             priority 40
user style memory           priority 30
```

这不是在声称“所有 Context 都应该用一个整数排序”。

生产系统可能使用 recency、semantic relevance、task phase、trust class、cost、source type 等更多因素。

但这个小算法让一件事情变得可见：

> **Context 是一个 selection problem。**

不是一个 `"\n".join(all_the_things)` problem。

---

## 7. Priority 不是 Trust

这里要防止另一个常见误解。

一段 Retrieval Evidence 很相关，所以 Priority 很高。

这不代表它可信。

一条 Tool Result 可能非常重要，也可能来自外部系统。

用户刚刚发来的内容永远很重要，但用户内容当然不能自动变成 System Instruction。

所以至少要区分两个维度：

```text
relevance / priority
vs
authority / trust
```

本章的 `provenance` 字段用来保留来源：

```python
ContextItem(
    key="retrieved-policy",
    kind="evidence",
    priority=90,
    provenance="policy-handbook",
)
```

渲染时也不把所有内容糊成一段：

```text
<context kind='evidence'
         source='policy-handbook'
         key='retrieved-policy'>
...
</context>
```

这不等于完整 Prompt Injection 防御。

但至少系统没有主动把“来自哪”丢掉。

后面的安全章节会继续处理外部输入的信任边界。

---

## 8. Recent History 不是越长越好

聊天系统最容易写成：

```python
messages.append(new_message)
send_everything(messages)
```

前十轮很舒服。

第一百轮以后，Context 里开始出现：

- 早已过期的讨论；
- 已经纠正过的错误；
- 重复 Tool Result；
- 很久以前的临时计划；
- 大量与当前任务无关的寒暄。

这时一种常见策略是：

```text
保留最近消息
+
压缩更老历史
```

注意这里说的是“压缩”，不是“把最老消息删掉然后假装它们没存在过”。

---

## 9. Compaction 是有损操作

本章的 Teaching Compactor 会把旧消息压成：

```text
user: ...
assistant: ...
```

并记录：

```python
source_message_ids=("m1", "m2")
```

为什么要保留这些 ID？

因为 Summary 不是原始事实本身。

它是对原始消息的有损表示。

如果系统以后发现摘要出了问题，至少还知道摘要来自哪些消息。

这就是 Provenance。

我们可以把 Compaction 想成把一箱文件整理成一张会议纪要：

```text
raw history
    ↓ compact
summary
```

会议纪要很好用。

但如果合同纠纷需要逐字证据，你不能拿一句：

> “大概就是这个意思。”

当原件。

所以：

```text
compacted context != checkpoint
compacted context != source of truth
```

---

## 10. Compaction 解决长度，不自动解决质量

一个很长的旧对话压成 200 token，并不意味着这 200 token 一定值得放进当前 Context。

压缩之后仍然要 Selection。

正确关系更像：

```text
retained history
    ↓
optional compaction
    ↓
candidate context item
    ↓
selection
    ↓
model context
```

而不是：

```text
summarized
    ↓
therefore mandatory forever
```

“我都费劲总结了，不放进去多亏啊”不是信息架构原则。

---

## 11. RAG 和 Memory 都只是 Context 来源

Stage 04 教 RAG 时，我们强调 Retriever 返回的是 Evidence Candidate。

Stage 06 教 Memory 时，我们强调存储的是被允许长期保留的信息。

到了 Stage 07，这两者终于站到同一张桌子前：

```text
RAG Result
       \
        \
Memory ----> Context Builder ---> Model
        /
Tool Result
```

Context Builder 决定当前到底需要哪些。

例如退款问题里：

```text
退款政策 evidence
    -> 高优先级

用户喜欢中文
    -> 有用，但优先级较低

用户去年喜欢住靠窗酒店
    -> 这轮直接不选
```

Memory 和 RAG 的价值都不在于“每次自动全量注入”。

它们的价值是提供**可被按需选择的信息源**。

---

## 12. JIT Context：能晚一点拿，就别什么都提前塞

有些数据只有当任务走到某个阶段才需要。

比如：

```text
用户问普通概念
    -> 不需要订单详情

用户明确问 ORDER-42
    -> 才加载订单状态

模型决定需要退款政策
    -> 才检索对应政策
```

这种 Just-in-Time Context 的思想和 Stage 02 的 Routing、Stage 04 的 Agentic Retrieval 是连起来的。

先判断需求，再加载相关信息。

而不是开场就说：

> “欢迎来到系统，这是用户过去五年的所有数据，请慢用。”

延迟加载不仅节省 token，也减少不必要的数据暴露。

---

## 13. Tool Schema 也吃 Context

Tool 很容易被忽略。

当模型拥有几十个 Tool 时，每个 Tool 的名称、描述、参数 schema 也会占输入空间。

所以：

```text
100 个 Tool
≠
免费获得 100 项能力
```

它们会增加：

- Context 成本；
- Tool 选择难度；
- 名称混淆；
- 错误调用概率。

这也是为什么前面一直强调 Router、Capability Boundary 和 Namespace。

Context Engineering 不只管理“聊天消息”。

凡是模型这一轮必须读到的东西，都在争夺注意预算。

---

## 14. 一个完整的 Context Assembly

我们的 Demo 有五类候选：

```python
items = [
    instructions,
    current_question,
    retrieved_policy,
    memory,
    old_history_summary,
]
```

其中 Instructions 和 Current Question 是 Required。

Policy Evidence Priority 高。

History Summary 和 User Memory 根据剩余预算决定是否进入。

最终：

```python
selection = ContextBuilder().build(
    items,
    ContextBudget(
        max_input_tokens=120,
        reserved_output_tokens=30,
    ),
)
```

这段代码很短。

但它把“给模型什么”从隐式字符串拼接变成了一个可以观察、测试和调整的系统决策。

---

## 15. 为什么要记录 Omitted Items？

Builder 返回：

```python
ContextSelection(
    items=...,
    used_tokens=...,
    omitted_keys=...,
)
```

`omitted_keys` 很有用。

想象模型答错了。

你开始排查：

> “为什么它不知道退款条款？”

如果系统只能给你最终 Prompt，你可能只知道条款没进去。

如果 Context Builder 能告诉你：

```text
retrieved-policy omitted: insufficient budget
```

诊断就容易多了。

到了 Stage 10，我们会把这种决策进一步变成 Trace 和 Evaluation 信号。

所以 Context Engineering 本身也应该是可观察的。

---

## 16. Context 不是越少越高级

讲了这么多压缩和选择，也不要走向另一个极端：

> “最好的 Context 就是最短的 Context。”

不是。

如果删掉真正需要的 Evidence，答案当然会变差。

Context Engineering 追求的是：

```text
足够
+
相关
+
边界清楚
+
预算可控
```

而不是参加 token 节约比赛。

一个只剩 `"answer carefully"` 的 Prompt 确实很便宜。

它也确实什么都没告诉模型。

---

## 17. 这一章和 Prompt Engineering 是什么关系？

Prompt Engineering 通常关心：

```text
怎么表达 Instructions
怎么组织示例
怎么让输出更稳定
```

Context Engineering 的范围更大：

```text
哪些信息进入模型
何时进入
从哪里来
以什么形式进入
什么被省略
什么被压缩
```

Prompt 是 Context 的一部分。

但 Context 还包括：

- Conversation；
- Memory；
- RAG Evidence；
- Tool Schemas；
- Tool Results；
- Runtime 提供的任务数据。

因此在 Agent 系统里，只会调一句 System Prompt 远远不够。

---

## 18. 运行完整代码

运行：

```bash
python stages/07-context-engineering/code/demo.py
```

它会先压缩旧 History，再把 Instructions、当前问题、RAG Evidence、Memory 与 History Summary 作为候选交给 Context Builder。

然后观察：

```text
used_tokens
omitted
最终渲染 Context
```

边界检查：

```bash
python stages/07-context-engineering/code/checks.py
```

它验证 Required Item 不会被 Optional 挤掉；Required 超预算时直接失败；Priority 与输入顺序无关；Output Reservation 会减少可用输入预算；重复 key 被拒绝；Compaction 保留来源；Summary 明确是有损表示。

---

## 19. 下一章为什么是 Agent Skills？

现在我们的 Agent 已经会选择 Context。

但还有一种内容很尴尬。

假设 Agent 经常要做：

```text
代码审查
发布检查
数据库迁移
事故复盘
```

每种任务都有一大段固定的操作说明。

把所有流程说明永远塞进 System Prompt，会再次把 Context 撑胖。

把它们全写死进程序，又失去可移植性和可发现性。

于是下一个自然问题是：

> **能不能先只知道“有哪些可用流程”，真正需要某个流程时，再加载它的详细说明？**

这就是 Progressive Disclosure。

也是 Stage 08 的主角：Agent Skills。
