# 为 Tiny-Agent 做贡献

[English](CONTRIBUTING.md) | **简体中文**

Tiny-Agent 既是一个学习项目，也是一个持续演进的 Agent runtime。任何贡献都应同时保护这两个目标。

## 1. 仓库模型

Tiny-Agent 有两个互补层次：

```text
stages/          稳定的教学快照
src/tiny_agent/  持续演进的最新集成 runtime
```

即使主 runtime 之后变得更复杂，一个已经完成的学习 Stage 仍然应该可以独立阅读和理解。

仓库还保留：

```text
tests/           Agent 机制的可执行规范
README*.md       面向学习者的公共入口
docs/            跨 Stage 学习地图
```

仓库维护元数据应尽量保持精简。除非确实直接服务于学习项目，否则不要随意加入无关 CI、模板、badge、生成文件或其它维护工具。

## 2. Stage 目录约定

使用基于能力的目录名，而不是日期或个人学习日程。

推荐：

```text
stages/04-agentic-rag/
```

避免：

```text
day11/
week2/
my-rag-notes/
```

在适用时，一个 Stage 应包含：

```text
stage-name/
├── README.md
├── README.zh-CN.md
├── theory/
├── code/
└── exercises/
```

### `README.md` / `README.zh-CN.md`

必须说明：

- 为什么需要这个 Stage；
- 前置知识；
- 学习目标；
- 推荐阅读 / 编码顺序；
- 预期里程碑；
- Stage 内所有重要文件的链接。

### `theory/`

详细 Markdown 理论解释放在这里。

相比一个极长的“万能文档”，更推荐多个聚焦的小章节。

一个 theory 章节通常应包含：

- 动机；
- 心智模型；
- 适用时的架构 / 流程；
- 常见误区；
- 工程含义；
- 关键结论；
- 复习问题；
- 使用外部材料时给出参考资料。

### `code/`

保存当前 Stage 对应的实现快照。

教学代码优先追求清晰，而不是最大化抽象。如果最新 `src/tiny_agent/` 已经复杂到超出当前 Stage 初学者所需，应在 Stage 中保留更简单、可独立理解的实现。

每个可运行示例都应明确说明如何运行。

### `exercises/`

用于：

- 编码练习；
- 调试任务；
- 设计问题；
- 面试题；
- 扩展挑战。

## 3. 纯理论 Stage

一个能力主要是概念性的，并不意味着它必须硬塞可执行代码才能拥有独立 Stage。

如果主要目标是理论学习，可以保留：

```text
stage-name/
├── README.md
├── README.zh-CN.md
└── theory/
```

不要为了满足目录模板而添加没有教学意义的代码。

## 4. 更新最新 runtime

如果某个 Stage 引入的能力也应该进入可复用的 Tiny-Agent runtime，那么同时更新 `src/tiny_agent/`。

示例：

```text
Stage snapshot                  Latest runtime
--------------                  --------------
minimal ToolRegistry      ->    src/tiny_agent/tool.py
minimal Agent loop        ->    src/tiny_agent/runtime.py
provider adapter          ->    src/tiny_agent/models/
RAG mechanism             ->    src/tiny_agent/retrieval.py + rag.py
memory/HITL policy        ->    src/tiny_agent/memory_policy.py + approval.py
safety/governance         ->    src/tiny_agent/reliability.py + governance.py
multi-Agent mechanism     ->    src/tiny_agent/multi_agent.py
long-horizon harness      ->    src/tiny_agent/harness.py
```

Stage snapshot 负责教清楚概念；latest runtime 负责把它与已有能力干净地集成起来。

## 5. 不要过早隐藏底层机制

Tiny-Agent 有意在高层框架之前教授 first principles。

引入 LangGraph 之类框架时，应展示：

1. 底层问题是什么；
2. 手写版本或此前 Tiny-Agent 的实现；
3. 框架新增了什么抽象；
4. 框架又引入了什么复杂度或 trade-off。

避免只剩下这种逻辑的教学示例：

```python
agent = create_agent(...)
agent.run(...)
```

却完全不解释底层发生了什么。

## 6. 分离模型责任与 runtime 责任

项目核心原则之一是：

> LLM 提议动作；runtime 执行并治理动作。

不要让模型无约束地控制本地函数、文件、shell、数据库、凭证或外部副作用。

执行策略应由确定性的 runtime 代码负责。

## 7. 测试要求

把 tests 当成**可执行的教学规范**，而不仅仅是回归测试工具。

修改某个机制之前，先阅读 [tests/README.zh-CN.md](tests/README.zh-CN.md)，确认这个机制对应哪些 Stage 和测试文件。

runtime 行为优先使用确定性单元测试。

测试以下机制时，优先使用 fake / scripted model：

- loop transition；
- Tool 执行；
- stopping condition；
- error handling；
- state update；
- permission logic。

只有真正需要评估模型质量时，才在单独的 integration / evaluation tests 中使用真实模型。

不要让所有单元测试都依赖网络、API key 或随机模型行为。

如果新增了有实际教学意义的 `test_*.py` 文件，同时更新：

- `tests/README.md`；
- `tests/README.zh-CN.md`。

说明它保护什么机制、对应哪个 Stage，以及失败通常意味着哪一层语义被破坏。

## 8. 双语文档维护要求

Tiny-Agent 同时维护英文与简体中文两条完整学习路线。

面向学习者的 Markdown 应保持：

```text
README.md                 <-> README.zh-CN.md
chapter.md                <-> chapter.zh-CN.md
review-questions.md       <-> review-questions.zh-CN.md
```

新增或实质修改 learner-facing 文档时：

1. 同一个 contribution 中同步更新中英文版本；
2. 两个版本必须保持相同的技术含义、架构边界、警告、示例和练习完整度；
3. 不要翻译代码标识符、API 名、命令或代码文件路径，除非目标本身就是有中文副本的 Markdown；
4. 中文文档中的课程内部链接，只要存在 `.zh-CN.md` 对应页，就必须继续指向中文页；
5. 每篇文档顶部的语言切换应明确指向另一语言版本；
6. 不允许把完整英文教程翻译成只有摘要的中文版本。

翻译应自然，不需要逐字硬译；但技术正确性始终优先于语言风格本地化。

## 9. 文档链接

新增重要文件时：

- 从对应 Stage 的 `README.md` 与 `README.zh-CN.md` 链接它；
- 如果它改变了公开学习路线，则同步更新根 README 中英文版本；
- 英文学习页继续留在英文链路，中文学习页继续留在中文链路；
- 避免死链和占位链接。

## 10. Pull Request

一个 PR 应聚焦于一个能力或一个完整、连贯的维护目标。

良好示例：

```text
feat: add provider-neutral OpenAI adapter
feat: introduce planner-executor stage
feat: add tool-call trajectory evaluator
docs: explain MCP trust boundaries
test: cover Agent step-limit behavior
```

PR 应解释：

- 学习者获得了什么；
- runtime 行为发生了什么变化；
- 哪些文件是教学快照，哪些是集成实现；
- 如何测试这次修改；
- 如果修改了教学文档，中英文是否已经同步。

## 11. 写作风格

目标是：

- 技术准确；
- 初学者可读；
- 工程导向；
- 明确说明 trade-off；
- 避免无意义的框架营销语言。

优先使用具体图示、小例子和清晰的责任边界。

如果幽默能帮助记忆或理解，可以使用；但不能为了段子牺牲技术准确性。

## 12. 长期目标

一次成功的贡献，应该让下一位学习者更容易回答三个问题：

1. **这个 Agent 能力到底是怎么工作的？**
2. **为什么真实工程团队会这样设计它？**
3. **我如何验证实现仍然保持了这些语义？**
