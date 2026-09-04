# Stage 12 复习题

> Language: [English](review-questions.md) | 简体中文

1. 区分 harness、workspace、compute、container、sandbox。
2. 为什么 `asyncio.to_thread()` 不是 sandbox？
3. 为什么 filesystem read 和 write 一样需要 authorization？
4. `--network none` 防止什么？又不能防止什么？
5. 为什么 orchestration credential 应留在 model-generated execution environment 外？
6. 为 research sandbox 设计 policy：只允许访问 Crossref 与一个 internal document service。
7. Workspace file 什么时候才应该 promote 成 artifact？
8. 一个 3 小时 task 中 container 中途消失，哪些 state 必须 survive？
9. 面对 hostile multi-tenant code，你还会增加哪些 isolation？
10. 扩展 `DockerSandboxPolicy` 支持 controlled network profile，但不能接受 model-provided arbitrary Docker flags。
