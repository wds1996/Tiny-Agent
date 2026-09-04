# Stage 08 — Agent Skills 与 Procedural Knowledge

> Language: [English](README.md) | 简体中文

Tool 告诉 Agent：**有哪些动作可以做**。

Skill 告诉 Agent：**一类重复任务应该怎样做得更好**。

本阶段采用开放的 Agent Skills 格式，而不是重新发明一套 Tiny-Agent 专属技能文件。

```text
skill-name/
├── SKILL.md
├── scripts/       optional
├── references/    optional
└── assets/        optional
```

## 核心区别

```text
Tool / MCP
    = executable or readable capability

Skill
    = portable procedural knowledge + instructions + optional resources

Memory
    = retained information selected by policy

Agent
    = runtime/control system that may use all three
```

一个 Skill 可以教模型怎样组合多个 Tool，但它**不会因此获得这些 Tool 的执行权限**。

## 学习目标

完成本阶段后，你应该能够：

1. 区分 Skill、prompt、Tool、MCP 和 Memory；
2. 阅读和编写开放格式的 `SKILL.md`；
3. 解释为什么 `name` 和 `description` 是必需的 discovery metadata；
4. 使用 progressive disclosure：discovery -> activation -> resource loading；
5. 在未需要之前，不把大量已安装 Skill 的完整正文塞进 active context；
6. 设计职责明确的 scripts/references/assets；
7. 理解 `allowed-tools` 是实验性 metadata，而不是授权；
8. 校验 Skill name/path，阻止 directory traversal 与 symlink escape；
9. 把第三方 Skill 的 instruction/code 当成 software supply-chain boundary；
10. 通过 eval 判断 Skill 是否真的提升 task success，并值得长期维护。

## 推荐学习顺序

1. [`theory/01-skills-vs-tools-memory-and-agents.zh-CN.md`](theory/01-skills-vs-tools-memory-and-agents.zh-CN.md)
2. [`theory/02-skill-format-and-progressive-disclosure.zh-CN.md`](theory/02-skill-format-and-progressive-disclosure.zh-CN.md)
3. [`code/skill_catalog_demo.py`](code/skill_catalog_demo.py)
4. 查看 [`skills/research-review/`](skills/research-review/)
5. [`theory/03-skill-routing-and-context.zh-CN.md`](theory/03-skill-routing-and-context.zh-CN.md)
6. [`theory/04-skill-trust-governance-and-evaluation.zh-CN.md`](theory/04-skill-trust-governance-and-evaluation.zh-CN.md)
7. [`../../src/tiny_agent/skills.py`](../../src/tiny_agent/skills.py)
8. [`../../tests/test_skills.py`](../../tests/test_skills.py)
9. [`exercises/review-questions.zh-CN.md`](exercises/review-questions.zh-CN.md)

## 安装

```bash
python -m pip install -e ".[dev,stage08]"
```

这里额外依赖 PyYAML，因为 `SKILL.md` 的 metadata 使用 YAML frontmatter。

## 参考资料

- Agent Skills specification — https://agentskills.io/specification
- Agent Skills overview — https://agentskills.io/home
- Anthropic, *Equipping agents for the real world with Agent Skills* — https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills

## 完成检查点

构建一个拥有大量 Skill metadata 的 catalog：启动时只把精简 metadata 放进 context；任务需要时才 activate 对应 Skill；reference 也按需加载；所有真正的 executable action 仍然必须经过 Tiny-Agent 正常的 validation/authorization。
