# Stage 06B 复习题

> Language: [English](review-questions.md) | 简体中文

1. 为什么 Skill 不只是“一段很长的 system prompt”？
2. 为什么 Skill 不等价于 Tool 或 MCP server？
3. Progressive Disclosure 解决的核心问题是什么？
4. 在 Skill activation 之前，应该先加载哪些 metadata？
5. 为什么 `allowed-tools` 绝不能单独被视为 authorization？
6. 设计一个 script 需要 network access 的 Skill。`compatibility` 应该说明什么？runtime 还必须保留哪些 policy？
7. 如果系统安装了 200 个 Skill，怎样 routing 而不加载 200 份完整正文？
8. 比较 Skill v1 与 v2 时，哪些信息应该 trace/version？
9. 审查仓库内置 `research-review` Skill 的 supply-chain 与 context risk。
10. 设计一个 eval，证明这个 Skill 是否相较 no-skill baseline 真正提高 research-grounding quality。
