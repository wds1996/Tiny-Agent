# Stage 14 — 长时程 Agent Harness

短时 Agent 循环通常默认：任务可以在一个进程生命周期内完成，而且上下文规模仍然可控。长时程任务会直接打破这两个前提。

持续数小时甚至数天的任务，需要一个能够跨越以下边界持续推进工作的 harness（运行控制框架）：

- 模型上下文窗口；
- 进程重启；
- sandbox 过期或销毁；
- 人工暂停；
- 瞬时故障；
- 多个 worker session。

核心结论是：

> **长时程可靠性来自外部化的进度、artifact、任务状态、评估以及可恢复执行，而不是要求模型“把一切都记住”。**

## 学习目标

完成本阶段后，你应该能够：

1. 解释为什么“一个巨大 prompt / 一个永不结束的 session”不是好的长时程架构；
2. 在模型上下文之外维护 durable task ledger；
3. 区分 initializer / planner 与后续增量 worker session；
4. 为下一次 session 持久化进度备注与 artifact；
5. 构造紧凑的 handoff summary，而不是重放完整 transcript；
6. 使用新的 runtime 对象甚至新的进程恢复任务；
7. 用 evaluator / test 作为完成证据，而不是相信模型说“看起来做完了”；
8. 区分 retry、repair 与 replanning；
9. 区分 durable harness state 与 disposable sandbox compute；
10. 理解 lease、cancellation、side effect 与 job ownership 之间的关系。

## 学习顺序

1. `theory/01-why-long-horizon-agents-fail.md`
2. `theory/02-task-ledgers-and-shift-handoffs.md`
3. `code/long_horizon_demo.py`
4. `code/resume_demo.py`
5. `theory/03-context-compaction-artifacts-and-skills.md`
6. `theory/04-evaluator-repair-and-session-boundaries.md`
7. `theory/05-durable-harness-vs-disposable-compute.md`
8. `src/tiny_agent/harness.py`
9. `src/tiny_agent/jobs.py`
10. `tests/test_harness.py`、`tests/test_jobs.py`
11. `exercises/review-questions.md`

中文阅读时，对应理论文件请使用同目录下的 `*.zh-CN.md`；代码、测试和配置仍与英文教程共用同一份实现。

## 当前参考资料

- Anthropic, *Effective harnesses for long-running agents* — https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
- Anthropic, *Harness design for long-running application development* — https://www.anthropic.com/engineering/harness-design-long-running-apps
- OpenAI, *The next evolution of the Agents SDK* — https://openai.com/index/the-next-evolution-of-the-agents-sdk/
- MCP 2026-07-28 Tasks extension overview — https://blog.modelcontextprotocol.io/posts/2026-07-28/

## Tiny-Agent 实现

`TaskLedger` 以人类可读的 JSON 文件保存：

```text
objective
任务状态
attempt 次数
notes
artifact paths
```

这个 JSON 文件位于受治理的 workspace 内，并通过原子文件替换完成写入。

`LongHorizonHarness` 每次执行一个 pending task，并且：

```text
执行前持久化状态转换
-> 调用 worker
-> 执行后再次持久化
-> 为下一 worker / session 生成紧凑 handoff summary
```

Stage 13 的 `SQLiteRunQueue` 则是另一层概念：它展示的是 **service-level durable job / lease**，不是项目内部的 TaskLedger。

可以把两者区分为：

```text
SQLiteRunQueue
    = 哪个 service worker 当前拥有 run-42？

TaskLedger
    = 在 run-42 内部，哪些研究/编码子任务已经完成？
```

## 阶段里程碑

启动一个包含多个任务的 run，只完成其中一步，然后：

```text
销毁当前 runtime 对象
-> 使用同一个 workspace 创建全新的 runtime
-> 读取 durable ledger / artifacts
-> 从剩余任务继续
```

整个恢复过程不依赖重放隐藏的模型历史。

如果系统必须靠“别关这个聊天窗口”才能继续三天前的工作，那还不能叫长时程架构；那只是把浏览器标签页当成了数据库。