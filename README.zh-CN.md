<p align="center">
  <img src="assets/agent_readme.png" alt="Tiny-Agent —— 从第一性原理学习现代 AI Agent" width="100%" />
</p>

# Tiny-Agent：从一次模型调用，到真正的 Agent 系统

> Language: [English](README.md) | **简体中文**

很多 Agent 教程从安装框架开始，然后很快写出 `create_agent()`。代码能跑，但当 Agent 第一次重复调用 Tool、把检索结果当成事实、在审批前产生副作用，或者因为 Context 越塞越长开始行为异常时，往往很难回答：这一层到底是谁负责？

Tiny-Agent 走另一条路。

这是一门从零开始的 Agent 工程课程。我们先把模型调用、Structured Output、Tool Calling、Runtime、Workflow、State、Retrieval 这些基础机制一层层搭起来，再进入 MCP、Memory、Context Engineering、Skills、Safety、Evaluation、Multi-Agent、Sandbox、Production 与 Long-Horizon。

框架会出现，但不会毓�{�题更早出现。最终目标也不是记住一套 2026 年流行 API，而是面对一个新的 Agent 系统时，能够自己判断：哪些决定真的需要模型，哪些控制逻辑应该留在普通代码里，模型能提出什么又真正有权做什么，以及系统怎样停止、恢复、审批、评估和上线。

---

## 课程地图

课程使用连续的 `00–15` Stage。每一章只解决前一章自然暴露出来的新问题。

| Stage | 主题 | 这一章真正要回答的问题 |
|---|---|---|
| [00](stages/00-foundations/README.zh-CN.md) | Foundations | 模型调用怎样从“返回一段文字”变成程序可用的接口？ |
| [01](stages/01-react-runtime/README.zh-CN.md) | ReAct Runtime | Tool Call 怎样形成一个有边界、会停止的 Agent Loop？ |
| [02](stages/02-workflows-routing-planning/README.zh-CN.md) | Workflow / Routing / Planning | 哪些控制权该留给代码，哪些判断值得交给模型？ |
| [03](stages/03-stateful-orchestration/README.zh-CN.md) | Stateful Orchestration | 流程复杂以后，怎样把 State 与状态转移摊到桌面上？ |
| [04](stages/04-agentic-rag/README.zh-CN.md) | Retrieval / Agentic RAG | Agent 怎样获取外部 Evidence，并知道什么时候证据不够？ |
| [05](stages/05-mcp/README.zh-CN.md) | MCP | 外部 Tool、Resource、Prompt 怎样跨标准协议边界接入？ |
| [06](stages/06-memory-persistence-hitl/README.zh-CN.md) | Memory / Persistence / HITL | 进程消失以后怎样继续？什么值得长期记住？什么时候必须等人？ |
| [07](stages/07-context-engineering/README.zh-CN.md) | Context Engineering | 已经保存了这么多信息，这一轮模型到底应该看到什么？ |
| [08](stages/08-agent-skills/README.zh-CN.md) | Agent Skills | 可复用 Procedure 怎样被发现，并只在需要时加载？ |
| [09](stages/09-reliability-safety/README.zh-CN.md) | Reliability / Safety | Agent 真能行动以后，怎样限制权限、重试、循环、错误与预算？ |
| [10](stages/10-evaluation-observability/README.zh-CN.md) | Evaluation / Observability | 怎样知道 Agent 为什么这样做，以及改版到底有没有变好？ |
| [11](stages/11-multi-agent/README.zh-CN.md) | Multi-Agent | 什么时候真的需要第二个 Agent，而不是多画几个方框？ |
| [12](stages/12-agent-workspace-sandbox/README.zh-CN.md) | Workspace / Sandbox | Agent 能读写文件、运行代码以后，执行边界在哪里？ |
| [13](stages/13-production-deployment/README.zh-CN.md) | Production Service | 一个本机 Demo 怎样变成有身份、队列、Backpressure 和 Durable Run 的服务？ |
| [14](stages/14-long-horizon-harness/README.zh-CN.md) | Long-Horizon Harness | Worker 消失以后，长任务怎样靠 Ledger、Lease 和 Artifact 换班继续？ |
| [15](stages/15-capstone-enterprise-agent/README.zh-CN.md) | Capstone | 面对真实业务，怎样只选择真正需要的 Agent 机制？ |

建议严格按顺序学习。课程里很多边界是前面一层层建立的，直接跳到后面往往只能看到“怎么写”，看不到“为什么现在才需要它”。

---

## 每一章怎么学

标准 Stage 结构只有三部分：

```text
stages/XX-topic/
├── README.md
├── README.zh-CN.md
└── code/
```

README 是完整课程正文。正文里的代码块只展示当前正在讲的局部机制；完整可执行程序放在本章 `code/`。

推荐学习节奏：

```text
读一段讲解
    ↓
看当前局部代码
    ↓
解释它解决了什么问题
    ↓
运行本章完整 Demo
    ↓
运行 checks.py / runtime_checks.py
    ↓
故意改坏一个不变量
    ↓
解释为什么检查失败
```

不要只运行 Happy Path。Agent 工程里，真正值得学习的地方经常藏在“错误输入应该怎样被拒绝”“不该发生的副作用是否真的没有发生”这些边界里。

---

## 运行代码

课程以 Python 3.10+ 为基线。大量后半程示例只使用标准库，可以直接运行：

```bash
python stages/06-memory-persistence-hitl/code/demo.py
python stages/06-memory-persistence-hitl/code/checks.py
```

有外部依赖的章节，在自己的 `code/requirements.txt` 中声明依赖。例如：

```bash
python -m pip install -r stages/05-mcp/code/requirements.txt
python stages/05-mcp/code/in_memory_client.py
python stages/05-mcp/code/checks.py
```

课程不要求在仓库根目录安装一个“大而全”的 Agent 环境。学习某一章时，只安装这一章真正需要的依赖。

Stage 00、01 等章节包含真实模型 Provider 的教学 Adapter；对应环境变量和运行方式写在章节正文。课程检查尽量使用 Deterministic Model Double、Fake Client 或离线数据，因为 Runtime 是否越权、是否无限循环、是否重复副作用，本来就不该依赖一次随机在线模型调用来证明。

---

## 为什么先讲机制，再讲框架

一个抽象只有在你知道它替你做了什么以后，才真正有价值。

Stage 03 先从 State / Node / Edge / Reducer 推到 Graph，再映射 LangGraph；Stage 04 先从 Chunk / Embedding / Similarity / Top-K 推到向量后端；Stage 05 先分清 Function Calling 和外部协议边界，再进入 MCP。

这不是反框架。恰恰相反，它会让框架更容易学：看到一个高层 API 时，你不需要死记参数，而是知道它正在替你承担哪一层责任。

---

## 一条贯穿全课的原则：Proposal 不等于 Authority

如果只记住 Tiny-Agent 的一句话，可以记这句。

模型可以提出 Tool Call、Route、Plan、Memory Candidate、Refund Action 或 Delegation；Retriever 可以返回高相关内容；Skill 可以建议使用某个 Tool；另一个 Agent 也可以请求协作。

这些都不自动获得执行权。

应用拥有的 Validation、Policy、Ownership、Approval、Authorization 与 Execution Boundary 必须继续存在。

Agent 工程的很多事故，本质上都是把“建议”错当成了“授权”。

---

## 仓库结构

重构后的仓库保持课程本身需要的最小结构：

```text
Tiny-Agent/
├── README.md
├── README.zh-CN.md
├── CONTRIBUTING.md
├── CONTRIBUTING.zh-CN.md
├── LICENSE
└── stages/
    ├── 00-foundations/
    ├── 01-react-runtime/
    ├── ...
    └── 15-capstone-enterprise-agent/
```

每一章都拥有自己的完整教学实现和可执行检查。没有第二套全局 `src/` 或 `tests/` 需要学生与章节代码来回对照。

---

## 适合谁

只要会基础 Python 就可以开始：函数、类、`dict` / `list`、异常、基本 JSON 和命令行运行 Python 已经足够。`async/await`、SQLite、Subprocess、Graph、Service 等知识会在课程真正需要它们时再进入。

学完以后，目标不应该只是“我会用某个 Agent Framework”，而是拿到一个新的业务需求时，能先把模型决策、Tool 权限、State Scope、Durability、Memory Policy、Context Selection、Evidence、Retry、Idempotency、Approval、Authorization、Execution Isolation、Trace、Eval、Service Identity 和 Worker Recovery 的边界说清楚。

当这些问题能在选框架之前回答，框架才真正变成工具。

从 [Stage 00](stages/00-foundations/README.zh-CN.md) 开始即可。

---

## Star History

<a href="https://www.star-history.com/?repos=wds1996%2FTiny-Agent&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=wds1996/Tiny-Agent&type=date&theme=dark&legend=top-left&sealed_token=XS_WU0y8HydmsHz6LTueLxesinCg4gXRd-EpaRl6ATjiKesmm8eBUKFxeGsBdOVkvKn10SYjq0sZ1aD4SgzAIARbUcbD2g22nYQYpId-Pi95XI6qasNgGn6je9vJJTGhq3BJ9BlSQx1HfSqyII_bkFQNT6M3IEC-MoUe82x53EE2DIRiF4eoFQo-5yK_" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=wds1996/Tiny-Agent&type=date&legend=top-left&sealed_token=XS_WU0y8HydmsHz6LTueLxesinCg4gXRd-EpaRl6ATjiKesmm8eBUKFxeGsBdOVkvKn10SYjq0sZ1aD4SgzAIARbUcbD2g22nYQYpId-Pi95XI6qasNgGn6je9vJJTGhq3BJ9BlSQx1HfSqyII_bkFQNT6M3IEC-MoUe82x53EE2DIRiF4eoFQo-5yK_" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=wds1996/Tiny-Agent&type=date&legend=top-left&sealed_token=XS_WU0y8HydmsHz6LTueLxesinCg4gXRd-EpaRl6ATjiKesmm8eBUKFxeGsBdOVkvKn10SYjq0sZ1aD4SgzAIARbUcbD2g22nYQYpId-Pi95XI6qasNgGn6je9vJJTGhq3BJ9BlSQx1HfSqyII_bkFQNT6M3IEC-MoUe82x53EE2DIRiF4eoFQo-5yK_" />
 </picture>
</a>

<p align="center">在 Star History 上查看 Tiny-Agent 的成长。</p>
