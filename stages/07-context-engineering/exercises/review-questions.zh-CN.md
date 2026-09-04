# Stage 07 复习题

> Language: [English](review-questions.md) | 简体中文

1. 为什么 model context 在语义范围上小于 application state？
2. 为什么在选择 optional context 之前，要先扣除 output reserve 和 runtime/tool reserve？
3. 哪些 context item 应该 fail closed，而不是在预算不足时被静默删除？
4. 为什么 compaction 产生的是 derived state，而不是 original truth？
5. 举一个“发送过多历史”导致失败的例子。
6. 举一个“过度 aggressive summarization”导致失败的例子。
7. RAG、dynamic Tool exposure、Agent Skills 和 workspace file read 为什么都可以看作 Progressive Disclosure？
8. 为什么更大的 context window 并不会消除 prompt-injection 风险？
9. 为一个拥有 50 篇论文、20 条 memory、80 个 Tool 和 15 个 Skill 的 research Agent 设计 context policy。
10. 设计一组 eval，比较 full-history、last-N、summary+recent、retrieval-based context policy 在质量、token 与成本上的差异。
