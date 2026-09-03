# 复习题

1. 为什么一段很长的 transcript 不能替代 durable TaskLedger？
2. 哪些事实必须保存在精确 structured state 中，而不能只存在 compact handoff summary 里？
3. 一个 worker 在自己的 context window 结束之前，至少应该持久化哪些内容？
4. 分别用一个具体例子解释 retry、repair 与 replan。
5. 为什么只有在 harness / workspace state 已经外部化时，sandbox 丢失才真正可恢复？
6. 设计一个持续 6 小时、期间经历 3 次 worker restart 仍能继续的 run。说明哪些状态必须 durable、每次 worker 如何重新接手，以及如何避免重复副作用。
7. 一个带有外部 side effect 的长时程 workflow 中，human approval 应该放在哪个位置？审批本身需要持久化哪些信息？
8. 如何防止两个 worker 同时认为自己拥有同一个 service-level job？请结合 lease / atomic claim 解释。
9. 哪些 evaluator 应在每个 task 后运行，哪些更适合只在 final completion 前运行？请分别举例。
10. 扩展教学版 `TaskLedger`，增加 `blocked` 和 `cancelled` 状态，并画出允许的状态转换。说明：什么事件进入 `blocked`、如何解除阻塞、取消后哪些操作仍需要清理或补偿。

## 自检重点

完成这些题后，你应当能够不看笔记区分：

```text
transcript != TaskLedger
handoff summary != source of truth
retry != repair != replan
run queue != TaskLedger
checkpoint != TaskLedger
sandbox lifetime != run lifetime
resume != exactly once
model says done != harness verifies done
```

如果这些边界还能混在一起，建议重新阅读 Theory 01、02、04、05，再运行 `long_horizon_demo.py` 与 `resume_demo.py`。