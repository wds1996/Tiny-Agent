# 05 — Durable Harness 与 Disposable Compute

当我们把两种生命周期明确分开后，长时程 Agent 会容易理解很多：

```text
durable control state
        vs
disposable execution environment
```

harness 应该能够比任何单个 sandbox、model call、HTTP connection 或 worker process 活得更久。

---

## 1. Durable Harness State

典型内容包括：

```text
run / job identity and owner
objective
TaskLedger
thread / checkpoint
approval state
artifact metadata
progress notes
budget usage
external task handles
```

这些属于 continuity / control-plane state。

如果丢失它们，系统可能无法履行“任务可以恢复”的产品承诺。

---

## 2. Disposable Compute State

典型内容：

```text
container process
/tmp files
package caches
one notebook kernel
one shell session
one model call
```

这些通常可以重建。

真正重要的 artifact 必须在执行环境销毁前，根据 policy 写入或提升到 governed durable storage。

---

## 3. 分离为什么提升安全性

如果 sandbox 并不持有 run database credential、model master credential 或 service-level authority，那么即使 generated code 被攻破，blast radius 也更小。

```text
Harness / service
  owns identity, leases, credentials, policy
        |
        | narrow execution request
        v
Sandbox
  owns task-scoped files / compute only
        |
        | result / artifact
        v
Harness validates / promotes
```

这比“把整个应用以及所有 master credential 都塞进执行不可信代码的同一个环境”稳健得多。

---

## 4. 分离为什么提升 Durability

```text
sandbox dies
-> harness 仍知道 task 当时是 running
-> recover_interrupted / lease expiry
-> start new sandbox
-> mount / load artifacts
-> retry / repair
```

如果 harness state 也跟着 sandbox 一起消失，就没有可靠状态可供恢复。

---

## 5. Service Run、Agent Thread、Task Ledger、Sandbox 是不同层

一个完整长时程部署可能同时有：

```text
run_id
  = product / service job ownership

thread_id / checkpoint
  = orchestration resume position

TaskLedger
  = project / subtask progress

sandbox_id
  = temporary compute instance
```

这些 ID 可以互相关联，但不应该被当成同一个抽象。

特别是：

```text
one run
-> many sandbox instances over time
```

完全正常。

---

## 6. Rehydration

重新创建 compute 环境，需要恢复足够的可重现条件：

```text
approved base image
+ code version
+ dependency manifest
+ workspace / artifact mount
+ task-scoped config / credentials
+ pending task
```

环境越接近 reproducible configuration，crash recovery 越容易。

如果环境的唯一说明是：

> “旧 container 里之前手动装过几个包，具体什么版本不太记得了。”

那恢复就不再是工程流程，而开始接近软件考古。

---

## 7. Durable Queue 与 TaskLedger 解决的是不同层级

Stage 10 `SQLiteRunQueue` 回答：

```text
哪个 worker 当前拥有 run-42？
```

Stage 10A `TaskLedger` 回答：

```text
run-42 内部哪些 research / coding task 已经完成？
```

完整流程可能是：

```text
worker claims run-42
-> load its TaskLedger
-> 在 new sandbox 执行一个 pending task
-> save artifact
-> update ledger
-> 根据 service contract 完成 / 释放 run
```

---

## 8. 完整示例

```text
POST /runs
-> authenticate tenant / user
-> durable run-42 queued

worker-B claims lease
-> load thread checkpoint + TaskLedger
-> pending task: "analyze dataset"
-> create constrained sandbox-9
-> run analysis
-> save result.csv to durable workspace
-> evaluator validates
-> TaskLedger marks task complete
-> checkpoint next phase
-> destroy sandbox-9

later:
worker-C claims / resumes
-> new sandbox-10 for next task
```

项目状态跨越多个 process 与 compute environment 继续存在。

---

## 9. 什么应该 Durable？

不是所有东西都应该永久保存。
durability 有成本，也有隐私风险。

判断某项状态是否需要 durable，可以问：

```text
丢失它是否违反 correctness / resume promise？
能否低成本重新计算？
是否含敏感数据？
需要保留多久？
```

package cache 可以 disposable；已经批准的 final report 通常不可以。

---

## 10. 最终心智模型

```text
Durable control plane
  identity / job / checkpoint / ledger / artifact metadata
               |
               v
Disposable data / compute plane
  sandbox / processes / temporary caches
               |
               v
Governed artifacts + evaluator feedback
               |
               +----> durable control plane continues
```

> **长时程 Agent 的 durability，本质上是让 compute 可以随时替换，同时保存继续工作所需的最小外部状态，并且保证这些状态仍受到正确的安全与所有权治理。**