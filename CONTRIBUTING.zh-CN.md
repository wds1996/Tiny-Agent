# 贡献指南

> Language: [English](CONTRIBUTING.md) | **简体中文**

Tiny-Agent 不是一组互相独立的技术文章，而是一门按顺序展开的 Agent 课程。因此，对这个仓库的贡献首先是一项教学工作，其次才是代码工作。

一个新概念即使技术上正确，如果放错章节、写成 API 清单、需要读者提前知道三章以后的术语，仍然不算合格的课程贡献。

---

## 1. 像老师讲课，不像知识库列目录

正文应该沿着因果关系推进：上一章已经能做什么 → 现在遇到什么具体问题 → 最直觉的做法为什么开始失效 → 新概念为什么出现 → 用局部代码解释 → 运行完整示例 → 当前章还没解决什么 → 自然进入下一章。

列表和表格适合对照、总结和检查项，不应该承担主要教学叙事。避免连续十几行“一句话一段”，也避免每节都变成“定义 + 五个 Bullet”。

幽默和类比可以使用，但必须帮助理解技术边界。例如把“所有数据塞进一个 State”比喻成搬家时把整间屋子装进写着“杂物”的纸箱，类比之后仍要把 State 的真实工程含义说明白。

---

## 2. 只使用连续整数 Stage

课程编号为：

```text
00
01
02
...
15
```

不要新增 `06A`、`09B` 之类的旁支。如果新主题真的值得成为一章，应重新审视整体知识依赖，并调整整数顺序。

章节编号代表学习顺序，不只是目录名字。

---

## 3. 每章只解决当前阶段真正出现的问题

不要从未来章节倒灌知识。

Stage 03 可以讲 Graph 的循环边界，但 Checkpoint / HITL 留给 Stage 06；Stage 08 可以说明 Skill Script 没有自动执行权，但真正的 Sandbox 留给 Stage 12；Stage 13 可以指出 Worker 可能消失，但 Lease / Heartbeat 的完整机制留给 Stage 14。

允许在章节末尾提出下一章的问题，不允许提前把下一章答案讲完。

重写某一章前，先重新阅读前面的连续章节，确认前一章最终已经能做到什么、当前问题是否自然产生、当前术语是否已经有前置知识。

---

## 4. 主 README 就是教程正文

标准 Stage 结构：

```text
stages/XX-topic/
├── README.md
├── README.zh-CN.md
└── code/
```

不要重新建立 `theory/`、`exercises/`、`notes/` 等目录，再让读者在多个文件间来回跳。

如果某章真的必须拆成多个 Markdown，前一篇末尾应该直接衔接下一篇，像教材连续章节，而不是做一个目录页把读者分发到十个链接。

---

## 5. 教程正文不要写仓库维护元说明

这些内容不应该进入课程正文：

> “完整代码放在 code，避免 README 与代码不同步。”

> “本次重构删除了 theory。”

> “按照反馈重新组织了章节。”

> “为了保持单一真源头……”

它们属于维护过程，不属于 Agent 知识。贡献指南可以讨论这些规则，因为这里本来就在讲仓库维护。

---

## 6. 完整程序只放在本章 `code/`

每个 Stage 的完整教学实现属于自己的 `stages/XX-topic/code/`。不要再维护一份全局 `src/` 作为“真正实现”，再让章节代码做另一套 Demo。

README 代码块只展示正在讲的部分。讲 Reducer 就展示 Reducer，讲 Approval 就展示 Approval，讲 Budget 就展示 Budget。不要把完整 `agent.py` 复制进正文。

---

## 7. 中英文都要自然

英文版和中文版必须表达相同的技术边界，但不需要逐句直译。

中文应该像中文技术教材，而不是英语句法套中文词。Tool Call、Runtime、State、Reducer、Context、Memory、MCP、Skill、Trace、Lease 等术语可以按需要保留英文，但不要为了显得专业让普通句子变成一串英文名词。

---

## 8. 机制优先，框架其次

推荐顺序：

```text
具体问题
    ↓
最小手写机制
    ↓
确定性检查
    ↓
框架 / 协议映射
```

不推荐从 `pip install framework` 开始复制 Quickstart，再逐个解释 API 参数。框架版本变化很快，机制通常活得更久。

---

## 9. 不要夸大教学代码的保证

Teaching Hash Embedding 不是 Neural Semantic Embedding；bounded subprocess wrapper 不是 Security Sandbox；本地 Store 幂等不等于分布式 Exactly-once；Cooperative Deadline 也不等于能强杀任意代码。

课程质量很大程度来自“知道当前实现没有解决什么”。使用 Production、Secure、Durable、Idempotent、Sandboxed 等词时，要让代码真的建立并验证对应边界。

---

## 10. Proposal 和 Authority 必须分开

这是全课程最重要的不变量之一：

```text
Tool Call != execution authority
Route != dispatcher
Plan != executor
Memory Candidate != durable write permission
Retrieved Result != sufficient evidence
Skill declaration != Tool permission
Delegation != authorization
Approval != authorization
```

模型可以提出，应用必须验证、授权和执行。

---

## 11. 示例优先保证可复现

教学机制能够离线检查时，优先使用 Deterministic Model Double、Fake Provider Client、本地固定数据、临时 SQLite、临时目录、In-memory / local transport。

真实外部服务可以作为 Adapter 或集成示例存在，但核心 Runtime 不变量不应该只能通过一次在线、付费、随机的模型调用证明。

---

## 12. 每章必须有可运行的边界检查

推荐使用：

```text
code/checks.py
```

早期章节已有 `runtime_checks.py` 等清楚命名的检查文件可以保留。

检查不应该只验证 import 成功，更应该验证不变量，例如：非法参数不会进入 Handler、Unknown Tool 被拒绝、Loop 会在 Budget 停止、Reject 不产生 Side Effect、Evidence 不足会 Abstain、Required Context 不会被丢、Path Traversal 被拒绝、Expired Lease 才能 Reclaim。

Happy Path 只是最低要求。

---

## 13. 提交前自审

教学连续性：是否自然承接上一章？新概念是否由具体问题引出？是否提前使用未来概念？末尾是否自然产生下一章的问题？

文风：是否大量一句话一行？是否主要靠知识点列表推进？是否出现仓库重构元说明？类比是否帮助理解？中文是否自然？

技术：概念边界是否准确？是否夸大 Demo 的安全、可靠性或生产能力？模型是否被误赋予执行权？Retry / Memory / Context / Identity 等作用域是否明确？

代码：README Snippet 是否与完整代码一致？`code/` 是否能运行？错误路径是否有检查？网络或 Credential 要求是否明确？

仓库：中英文是否都更新？Markdown Fence 是否闭合？相对链接是否存在？是否产生缓存、数据库、日志或构建产物？

---

## 14. 运行检查

标准库章节：

```bash
python stages/XX-topic/code/demo.py
python stages/XX-topic/code/checks.py
```

有依赖的章节：

```bash
python -m pip install -r stages/XX-topic/code/requirements.txt
python stages/XX-topic/code/demo.py
python stages/XX-topic/code/checks.py
```

还可以运行：

```bash
python -m compileall -q stages
```

完成后删除 `__pycache__/` 和 `*.pyc`。

依赖只放在真正需要它的 Stage 的 `code/requirements.txt`，不要为了一个章节在仓库根目录维护全局 Agent 依赖集合。

---

## 15. 快速变化的协议和 API

MCP、A2A、模型 Provider SDK 等变化较快。修改相关内容时，应优先核对当前官方文档和版本，不要用多年前的博客更新协议章节。

强版本相关的代码应有真实可执行覆盖；没有实际验证的能力不要写成已经支持。

---

## 16. 不要提交运行产物或凭证

提交前检查：

```text
__pycache__/
*.pyc
*.db
*.sqlite
*.log
.env
.venv/
build/
dist/
*.egg-info/
```

真实 Credential 永远不要进入示例、检查输出或提交历史。

---

## 17. 最后的 Reviewer 问题

Review 一份课程贡献时，可以最后问三个问题：

> **一个第一次学习这个概念的人，为什么会在这里自然需要它？**

> **学完以后，读者能不能说清它解决了什么，以及没有解决什么？**

> **把框架名全部遮住以后，这一节还剩下一个清楚的工程机制吗？**

三个答案都清楚，通常说明这份贡献已经比较接近 Tiny-Agent 的课程标准。
