# 01 — Agent vs Workflow：选择最小且足够的 Control System

Agent Engineering 最重要的能力之一，是知道什么时候**不要**构建 autonomous Agent。

初学者很容易形成这样的路线：

```text
LLM -> Tools -> ReAct -> "让 model 决定一切"
```

这条路线有助于理解 autonomy，但容易制造错误工程直觉。

在 production 中，autonomy 不是系统成熟以后自动获得的“奖章”，而是一项用 predictability 换 flexibility 的 design choice。

---

## 1. 先问 Control-Flow Question

对于 application 中的每一步，都先问：

> 下一步发生什么，应该由 ordinary software 决定，还是由 model 决定？

### Predefined Control Flow

application code 事先知道允许的路径：

```text
request
  |
  v
validate
  |
  v
fetch data
  |
  v
transform
  |
  v
save
```

model 可以参与其中某些 node，但 graph 由 code 拥有。

这就是 **Workflow**。

### Model-Directed Control Flow

model 根据 current state 选择 next action：

```text
request
  |
  v
model decision
  |
  +--> Tool A
  +--> Tool B
  +--> ask user
  +--> finish
```

观察结果后再决定下一步。

这就是 Agent 的核心形态。

> 区别在于 **control ownership**，而不是系统里“有没有 LLM”。

---

## 2. Workflow 完全可以包含多个 LLM Call

例如：

```text
input
  |
  v
LLM: extract facts
  |
  v
Python: validate schema
  |
  v
LLM: write summary
  |
  v
END
```

有两次 LLM call，但 LLM 没有决定 validation 是否发生，也没有决定 next stage 是什么。

所以：

```text
multi-step LLM application
```

不自动等于：

```text
autonomous Agent
```

产品营销可以把很多东西都叫 Agent，但工程师仍然应该识别真实 control architecture。

---

## 3. Agent 也可以包含 Deterministic Workflow

反过来也成立。

Agent 可能决定：

```text
“I need to ingest this document before answering.”
```

但 ingestion capability 本身可以是 fixed pipeline：

```text
parse -> normalize -> chunk -> embed -> index
```

Agent 决定**要不要调用**这个 capability；ordinary software 决定**这个 capability 内部怎么可靠执行**。

```text
Agent decision
      |
      v
Document-ingestion Tool
      |
      v
fixed deterministic pipeline
```

外层系统是 Agent，并不意味着所有内部流程也必须变成 nested LLM decision。

---

## 4. Complexity Ladder

### Level 0 — Ordinary Deterministic Code

```python
result = calculate_price(items)
```

问题能由 code 完全定义时使用。

### Level 1 — One LLM Call

```text
user -> LLM -> answer
```

一次 call 已经可靠解决时使用，例如：

- sentiment classification；
- short document summarization；
- known field extraction；
- rewrite。

### Level 2 — Fixed LLM Workflow

```text
LLM extract -> validate -> LLM synthesize
```

fixed decomposition 能让每步更简单、更可验证时使用。

### Level 3 — Routing Workflow

```text
input -> choose branch -> specialized handler
```

存在几个稳定 downstream process，只是不容易确定该走哪个时使用。

### Level 4 — Planner–Executor

```text
high-level task -> Plan -> execute bounded steps
```

task 是 multi-step，且 milestone 会随 request 变化时使用。

### Level 5 — Bounded Autonomous Agent

```text
decide -> act -> observe -> decide -> ...
```

步骤数量和顺序无法可靠提前知道时使用。

### Level 6 — Long-Running / Multi-Agent

增加 delegation、persistence、coordination、background work、multi-session state。

只有 simpler architecture 无法满足 measurable requirement 时才值得引入。

---

## 5. 为什么 Simpler Architecture 经常更好

每一个 model-controlled decision 都增加 uncertainty。

如果每一步正确概率简单记成 `p`，连续 `n` 次全正确可以粗略想成：

```text
p^n
```

真实 Agent step 并不独立，所以这不是严格 reliability formula，但直觉很重要：

> 动态 decision 越多，错误累积机会越多。

同时也增加：

- model latency；
- token cost；
- Tool cost；
- prompt surface；
- debugging difficulty；
- evaluation requirement。

如果 application 永远要求：

```text
validate payment -> create invoice -> store receipt
```

每次都请 LLM 决定顺序，没有增加 intelligence，只增加 uncertainty。

---

## 6. Workflow 更合适的场景

如果大部分条件成立，优先 Workflow：

- step sequence 已知；
- branch 由稳定 business rule 定义；
- action side effect 明显；
- correctness 比 flexibility 更重要；
- compliance 要求 explicit path；
- intermediate state 要易 audit；
- 可以写 deterministic tests；
- 高频重复 task；
- latency / cost 敏感。

例如：

### Data Ingestion

```text
upload
-> antivirus check
-> parse
-> normalize
-> chunk
-> index
```

### Order Processing

```text
validate cart
-> reserve stock
-> charge payment
-> create shipment
```

### Model-Assisted Document Processing

```text
LLM extracts fields
-> validate required fields
-> human review if needed
-> save
```

LLM 可以参与，但不必拥有全部 control flow。

---

## 7. Agent 真正有价值的场景

当 correct path 强依赖难以预先枚举的 observation 时，Agent 开始有价值。

典型信号：

- open-ended task；
- unknown number of steps；
- dynamic Tool selection；
- exploration / search；
- repeated environment feedback；
- recovery 需要 semantic judgment；
- user goal 有多种合法 strategy。

### Coding Example

```text
Fix the failing authentication bug in this repository.
```

可能需要：

```text
inspect files
run tests
read error
search symbols
edit code
run tests again
inspect new error
...
```

exact path 取决于 observation。

### Research Example

```text
Compare the latest approaches to a niche technical problem.
```

可能需要 search、排除 irrelevant result、refine query、inspect evidence，再决定什么时候 evidence 足够。

---

## 8. 一个实用判断：Runtime 前能否画完完整 Path？

面试中很好用的问题：

> 在收到真实 user request 之前，我能不能把完整 control flow 画出来？

如果能，倾向 Workflow。

如果只有一小部分未知，可以做 hybrid：

```text
fixed workflow
    |
    +--> one model router
    |
    +--> one Agent node for open-ended subtask
```

如果整个 sequence 都必须在 environment interaction 中逐步产生，Agent 更合适。

---

## 9. Deterministic When Possible, Agentic When Useful

Tiny-Agent 的核心设计原则：

> **Deterministic when possible, agentic when useful.**

这不等于“少用 LLM”，而是把问题分成两类。

### Software Problems

例如：

- value 是否存在；
- JSON validation；
- retry limit；
- permission check；
- enum dispatch；
- database write。

用 software。

### Semantic Decision Problems

例如：

- ambiguous support category；
- novel research task decomposition；
- evidence 是否足够；
- next useful search query。

LLM 可能有价值。

---

## 10. Bad Architecture：把固定 CSV 流程 Agent 化

Requirement：

```text
1. Read CSV.
2. Validate required columns.
3. Calculate statistics.
4. Generate natural-language explanation.
```

坏设计：

```text
Agent
  +-> decide whether to read CSV
  +-> decide whether to validate
  +-> decide whether stats are needed
  +-> decide whether to explain
```

前三步是 mandatory / predictable。

更好：

```text
Python: read CSV
   |
Python: validate
   |
Python: calculate
   |
LLM: explain results
```

如果 user 可能选择不同 analysis，再增加一个 bounded semantic router。

---

## 11. 另一个 Bad Architecture：Agent All the Way Down

外层 Agent 决定发邮件后，不需要再做一个：

```text
Email Agent
  -> decide whether SMTP is necessary
  -> decide whether address validation is necessary
  -> decide whether encoding is necessary
  -> decide whether to send
```

更合理：

```text
Outer Agent decides: send_email(...)
                 |
                 v
           deterministic API client
```

这会形成清晰 authority boundary。

---

## 12. Workflow 也能提高 Safety

例如：

```text
LLM extracts refund reason
      |
      v
Python policy engine checks eligibility
      |
      +-- eligible --> refund workflow
      +-- not eligible --> human review
```

如果 hard business rule 能由 code enforcement，就不要要求 LLM“重新理解一遍”。

当 action 涉及 money、account、file、production infrastructure、external communication 时，这一点尤其重要。

---

## 13. Workflow 与 Agent 是 Continuum

真实系统可能是：

```text
                     User
                      |
                      v
                 LLM Router
               /      |      \
              /       |       \
             v        v        v
      fixed FAQ   refund    research
      workflow    workflow     Agent
                     |           |
                     v           v
                 approval    Tools/search
                     |           |
                     +-----+-----+
                           |
                           v
                         answer
```

只有一个 branch 需要高 autonomy。

这通常比“一个 giant Agent + 所有 Tool”更好。

---

## 14. Enterprise Design Questions

加 Agent loop 前问：

1. 一次 model call 能否可靠解决？
2. path 是否已经由 business rule 定义？
3. 哪些 decision 真正需要 semantic judgment？
4. 哪些 decision 可以直接写 condition？
5. model 选错 branch 会发生什么？
6. model 是否始终需要看到全部 Tool？
7. Workflow 能否缩小 action space？
8. latency / cost 能接受几次 model turn？
9. 能否测量 autonomy 是否提高 success rate？
10. 是否存在 deterministic success criterion？

如果无法解释 autonomy 如何改善系统，就不要因为 architecture diagram 看起来更“agentic”而加它。

---

## 15. 面试级回答

> 在 Workflow 中，application code 定义 control path，LLM 只在预定义 step 中使用；在 Agent 中，model 会依据当前 context 和 environment observation 动态决定部分 action sequence。我会对可预测任务优先使用 deterministic Workflow，只在 semantic / open-ended decision 能带来可测量价值时引入 model-directed control。

比下面的说法更准确：

> Agent 能调用 Tool，Workflow 不能。

因为 Workflow 完全可以包含 Tool 与 LLM call。

---

## 16. 自检

### A

```text
PDF -> parse -> chunk -> embed -> vector DB
```

**Deterministic Workflow**。

### B

```text
Question -> LLM decides whether to search
-> search
-> LLM decides whether more search is needed
```

**Agentic Loop**。

### C

```text
Ticket -> LLM chooses billing / technical / general
-> specialized fixed handler
```

**Routing Workflow**。

### D

```text
Task -> LLM creates 4-step plan
-> application executes in order
```

**Planner–Executor Workflow**。

### E

```text
Agent chooses database Tool
-> Tool runs deterministic SQL client
```

**Agent containing a deterministic capability**。

如果这五类你能稳定区分，就可以继续 Routing。