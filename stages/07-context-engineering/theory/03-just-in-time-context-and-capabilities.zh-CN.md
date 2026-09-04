# 03 — Just-in-Time Context 与 Capability Exposure

> Language: [English](03-just-in-time-context-and-capabilities.md) | 简体中文

一个 Agent 可能拥有几百个 Tool、Skill、memory、document 和 file，但模型几乎从来不需要在每一轮同时看到它们。

**Progressive Disclosure（渐进式披露）**的核心是：只有当当前决策真正需要某项细节时，才把它加载进来。

```text
large capability/data universe
        ↓ discover metadata
small relevant subset
        ↓ activate/read
current model context
```

这个原则把 RAG、dynamic Tool exposure、Agent Skills、workspace access 和 Multi-Agent context projection 串在了一起。

---

## 1. Installed != Exposed

假设 Host 能执行 200 个 Tool。

糟糕默认：

```text
all 200 schemas -> every model call
```

会带来：

- 更高 input token 成本；
- 更严重的 Tool selection confusion；
- 更大的 attack surface；
- 更多本不该出现的高风险动作候选；
- 更不稳定的 prompt prefix。

更合理：

```text
Host owns 200 Tools
-> task/phase policy selects 8
-> model sees 8 schemas
-> runtime can only execute authorized calls
```

这里有两个完全不同的控制：

```text
exposure   = 模型能看到什么
permission = runtime 允许执行什么
```

隐藏一个 Tool 是很有价值的 context policy，但它本身不是完整 authorization mechanism。

---

## 2. Dynamic Tool Exposure

概念性 policy：

```python
TOOL_GROUPS = {
    "research": {"search_papers", "read_document", "save_note"},
    "export": {"render_report", "write_report"},
}


def tools_for_phase(phase: str, all_tools):
    names = TOOL_GROUPS[phase]
    return [tool for tool in all_tools if tool.name in names]
```

不要问模型：

> “你还想看看哪些本来不允许看的 Tool？”

应用应该先定义合法 candidate set，再从中做动态选择。

---

## 3. RAG 就是 Just-in-Time Factual Context

Vector Store 里可能有几百万个 chunk，而模型最后只看到 5 个：

```text
corpus
-> query
-> candidate retrieval
-> rerank/filter/diversify
-> evidence subset
-> model
```

这就是 Progressive Disclosure 在 external knowledge 上的应用。

Conversation history 也可以这样处理：

```text
full history stored
-> retrieve relevant prior decisions
-> include only selected pieces now
```

---

## 4. Skill 是 Just-in-Time Procedural Context

Stage 08 会使用三层加载：

```text
all Skills: name + description metadata
            ↓ choose relevant Skill
activated: SKILL.md instructions
            ↓ need detail
resource: one reference/script/asset
```

`SkillCatalog.metadata_prompt()` 故意不加载每个 Skill 的完整正文：

```python
catalog = SkillCatalog("skills")
print(catalog.metadata_prompt())

# - code-review: Review code changes safely...
# - research-review: Check claims against evidence...
```

真正选中以后再：

```python
skill = catalog.activate("research-review")
print(skill.instructions)
```

这显然比每次请求都塞入 15 本“操作手册”便宜得多，也更不容易让模型分心。

---

## 5. Workspace File 是 Context Candidate，不是自动 Prompt Content

一个 coding Agent 可能面对 10,000 个文件。

错误做法：

```text
递归读取整个仓库
-> 拼接全部文件
-> 让模型修一个函数
```

更合理：

```text
search/list relevant paths
-> read target file
-> inspect neighboring definitions/tests
-> make change
-> run tests
```

Filesystem 是外部 working state；模型只在需要时读取其中的一小部分。

这同时关系到 token efficiency 和 data minimization。

---

## 6. Multi-Agent Context 应该被 Project，而不是 Clone

Supervisor 把“review citations”交给 critic Agent。

错误 handoff：

```text
复制整个 supervisor state
包括 secret、无关 Tool、全部 memory、所有用户数据
```

更合理：

```text
subtask
+ relevant draft
+ cited evidence
+ critic-specific instructions/tools
```

Sub-Agent 应该拿到完成自身角色所需的**最小上下文 + 最小权限**。

Stage 11 会把它正式称为 context ownership/projection。

---

## 7. Context Activation 应该 Phase-Aware

一个 research run 可以按阶段改变上下文和能力面：

```text
PLAN phase
  -> planner instructions
  -> user objective
  -> high-level memory
  -> no export Tool

RETRIEVE phase
  -> search/read Tools
  -> search Skill
  -> evidence budget

WRITE phase
  -> selected evidence
  -> style memory
  -> no open search Tool if research is complete

EXPORT phase
  -> approval state
  -> authorized write capability
```

不同阶段需要不同 action space。

这是一种很强的可靠性技巧：减少模型“甚至有机会提出”的无效下一步。

---

## 8. 例子：80 个 Tool + 15 个 Skill

任务：

```text
"Compare two RAG reranking strategies and write a Markdown report."
```

启动时只提供：

```text
Skill catalog metadata: 15 short descriptions
Tool catalog metadata: application-owned registry
```

Planning 阶段选择：

```text
Skills: research-review
Tools: search_papers, read_document, save_note
```

Evidence 足够以后：

```text
从 writer context 中移除 search Tools
加载 selected evidence
加载 report-writing instructions
```

只有进入 export：

```text
write_report becomes eligible
HITL/policy still controls execution
```

Agent 仍然拥有完整能力，但不需要每一轮都盯着整个宇宙。

---

## 9. Failure Mode：Relevant != Authorized

Dynamic selector 可能认为某个 Tool 或 Skill “相关”。这不代表它被授权。

```text
semantic selector: "database_admin is relevant"
        ↓
application policy: caller lacks admin permission
        ↓
not exposed / not executable
```

Selector 只负责提出 context candidate；deterministic policy 负责 trust 与 permission。

---

## 10. 如何评估 Progressive Disclosure？

比较：

```text
all-tools baseline
vs
phase-selected tools
```

测量：

- task success；
- Tool precision（useful calls / calls）；
- invalid Tool calls；
- tokens per turn；
- latency/cost；
- security exposure；
- selector recall（是否把真正需要的 capability 隐藏掉了）。

暴露过多会制造噪声；选择过度激进会造成 capability starvation。Context Engineering 就是在这两个极端之间制定 policy。

---

## 核心原则

> **让大规模 application capability/data space 保持可发现，但让 model context 保持小而及时。**

Progressive Disclosure 不是让 Agent 变弱，而是让下一次决策更清楚。
