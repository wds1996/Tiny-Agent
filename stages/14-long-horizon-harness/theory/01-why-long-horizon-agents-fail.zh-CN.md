# 01 — 为什么长时程 Agent 容易失败

一个短时 Agent 循环通常默认：

```text
一个进程生命周期
一个仍然可管理的上下文
一个用户请求
一个连续的执行时间窗口
```

持续数小时或数天的工作会把这四个假设全部打破。

解决办法不是对模型说：

> 请把所有事情都记住，并且一直尝试到任务完成。

这不是持久化策略，只是对易失性内存发表了一段励志演讲。

---

## 1. 失败来源：上下文增长速度快于有效信息

长任务会不断产生：

```text
plans
Tool observations
失败尝试
logs
artifacts
reviews
新的 subtasks
conversation
```

如果每个 session 都把所有历史重新塞回模型，成本和噪声会越来越高，最终还可能超过 context window。

因此长时程架构需要把状态外部化，只在当前决策时加载紧凑 working set：

```text
durable ledger / artifacts
          ↓
当前 subtask
+ 最近进度
+ 相关文件 / evidence
+ 当前激活的 Skills
          ↓
model context
```

到了这里，Stage 07 的 Context Engineering 已经不是“有空再优化”的附加项，而是系统能否继续工作的基础能力。

---

## 2. 失败来源：进程死亡

进程可能因为以下原因消失：

- deployment rollout；
- host restart；
- crash / OOM；
- dependency failure；
- worker replacement；
- 人工停止并重启服务。

如果进度只存在 Python 对象里：

```text
process dies
-> project amnesia
```

进程一死，项目就“失忆”。

因此 durable state 必须存在于 **模型/runtime 对象之外**。

---

## 3. 失败来源：执行环境丢失

sandbox / container 通常应该可以被销毁和重建。

```text
container 只把重要结果写到 /tmp
-> container 消失
-> 结果也一起消失
```

重要 artifact 与 workspace 状态必须根据 policy 被写入 disposable compute 之外的 durable storage。

也就是说：

```text
harness lifetime
!=
compute lifetime
```

---

## 4. 失败来源：“完成了”只是模型的判断

模型可能非常自信地说：

```text
“项目已经完成。”
```

但实际上：

```text
测试还没过
citation 没有 evidence 支撑
required task 还没完成
```

所以长时程任务必须有模型之外的完成标准：

```text
TaskLedger status
tests / evaluators
artifact requirements
human approval
budget / stop policy
```

模型可以**提出**完成；harness 必须**验证**完成。

---

## 5. 失败来源：恢复与重试可能重复 side effect

长任务会跨越很多 failure boundary：

```text
写入外部记录
-> 进程在记录“已完成”之前死亡
-> 新 worker 恢复任务
-> 再执行一次
```

因此：

```text
resume / retry
!= exactly once
```

涉及副作用时，仍然需要 Stage 09 / Stage 13 的：

- idempotency key；
- transaction / outbox；
- downstream deduplication；
- approval policy。

恢复能力并不会赋予系统“穿越回崩溃前确认外部世界到底发生了什么”的超能力。

---

## 6. 失败来源：一个巨大计划很快过期

在第 1 分钟生成的 40 步计划，可能到第 8 步就已经失效，因为环境、新证据或失败反馈改变了前提。

更稳健的控制方式是：

```text
stable objective
-> bounded near-term tasks
-> execute / evaluate
-> update TaskLedger
-> evidence changes 时 repair / replan
```

长时程控制更像持续的项目管理，而不是第一分钟就写完未来三天的预言书。

---

## 7. 失败来源：session handoff 丢掉关键状态

新的模型 session 需要足够的信息继续，但不需要完整 transcript。

糟糕的 handoff：

```text
“接着我们刚才的地方继续。”
```

新 session 的合理反问是：

```text
“刚才的地方”到底是哪？
```

更好的 handoff 至少包含：

```text
objective
当前 / pending tasks
最近关键 decision
artifact paths
blocking failures
next recommended action
```

精确结构化状态仍然放在 ledger / workspace 中；handoff summary 只是一个紧凑的派生视图。

---

## 8. 长时程架构

```text
objective
   ↓
initializer / planner
   ↓
TaskLedger + durable workspace
   ↓
worker session
   ↓
执行一个或少数 bounded tasks
   ↓
artifacts + notes + evaluation
   ↓
persist
   ↓
必要时换一个 worker / session 继续
```

> **模型是可替换的，项目状态不是。**

---

## 9. 示例：30 篇论文综述

### 朴素方式

```text
一个 chat session
-> 阅读论文
-> notes 全堆在 conversation
-> context 越来越满
-> summary 开始丢细节
-> process restart
-> 没有可靠进度来源
```

### Harness 方式

```text
TaskLedger:
  task-1 search corpus       completed
  task-2 extract paper A    completed
  task-3 extract paper B    running
  ...

Workspace:
  evidence/paper-a.md
  evidence/paper-b.md
  synthesis/matrix.csv

Next session:
  objective + pending task + relevant artifacts
```

这样 Agent 才从“很长的一段聊天”变成“可以换班、恢复、继续工作的 durable worker”。

---

## 10. Long-horizon 不等于什么

它不必然意味着：

```text
更多 autonomy
更多 Agents
更多 model calls
```

某些最可靠的长时程 harness，主体其实是 deterministic workflow，只在少数需要语义判断的节点调用模型。

依旧遵循 Tiny-Agent 的总原则：

> **使用能够可靠解决任务的、动态性最低的架构。**

---

## 完成原则

> **长时程可靠性来自外部化进度、artifact、evaluation、resumable state 与有边界的 worker session，而不是试图让一个模型 context 获得永生。**