# 04 — Credential、Network、Snapshot、Promotion 与 Recovery

> Language: [English](04-credentials-network-snapshots-and-recovery.md) | 简体中文

好 sandbox 不只是 Linux flags，还要决定哪些 credential 进入 environment、哪些 network path 存在、哪些 artifact survive、compute 消失后怎样 resume。

Sandbox 可以 disposable，但用户的工作不应该跟着意外一次性报废。

---

## 1. Orchestration Credential 留在 Generated Compute 外

Agent service 可能持有 model provider、job DB、artifact store、MCP/A2A、telemetry credential。Sandbox task 往往一个都不需要。

坏：把 web/Agent process 所有 env vars 原样复制进 container。

好：harness 保留 orchestration credential，sandbox 只拿 task-scoped data/credential。

如果 sandbox 不需要 secret，最安全的 secret injection 方法就是——**不要注入**。

---

## 2. Task-scoped Credential

需要 external access 时，优先 minimal scope、short lifetime、specific tenant/project、restricted destination/action、可 revocation/audit。

这比给每个 analysis environment 一个永久 master API key，再指望生成代码“职业素养良好”强得多。

---

## 3. Network Egress 是 Data-exfiltration Channel

问：任务是否需要 network？如果需要，哪些 host/service、method/protocol、request size/data class、credential、egress logging？

可选 architecture：network none、allowlisted proxy、typed service Tool、sandbox 前独立 download phase。

窄 Tool 通常比 arbitrary `curl` 更容易控制。

---

## 4. Dependency Download 要 Deliberate

```text
pip install definitely-not-malware
```

会引入 supply-chain、non-reproducibility、network、startup latency。

更好：prebuilt/pinned image、approved manifest、internal mirror、separate dependency-resolution policy。

让 Agent 心情好时就把所有东西安装成 `latest`，是把环境变得不可复现的最快方法之一。

---

## 5. Snapshot vs Durable Artifact

```text
snapshot -> whole/partial runtime environment state
artifact  -> meaningful output: report/patch/data/log
```

Snapshot 可加速 rehydration，但可能捕获 secret/stale state。长期系统常更适合 explicit artifact + reproducible environment manifest，而不是把 opaque machine snapshot 当唯一 truth。

---

## 6. Disposable Compute，Durable Harness

```text
TaskLedger / job state / ownership   durable
            ↓
sandbox compute                     disposable
            ↓
workspace artifacts                 durable
```

Container 消失后，新 worker 读 ledger、加载 workspace、重建 environment、继续 task。

Stage 10A 实现这套心智模型。

---

## 7. Promotion 是独立 Decision

Sandbox output 不自动变 production output。

代码：edit -> sandbox tests -> static/eval -> optional human review -> promote patch。

研究：chart/data -> validate -> link provenance -> final report。

Sandbox 是车间，production artifact store 是展厅；锯末没有必要一起上展台。

---

## 8. Recovery 与 Side Effect

External write 成功后 sandbox crash，harness 未记录 completion，再 retry 就可能 duplicate。

使用 idempotency key、transaction boundary、downstream dedup、external operation record、risk action human review。

Sandbox isolation 不创造 exactly-once semantics。

---

## 9. Long-running Analysis 示例

10GB experiment data：service auth user/tenant -> durable run -> TaskLedger subtasks -> governed storage/workspace -> sandbox 无 model-service master key -> network default off -> writes figures/results -> evaluator -> promote artifacts -> ledger completion。

Compute 中途死掉，run identity 与 completed artifacts 仍然存在。

---

## 10. Checklist

任何 Agent compute environment 都应回答：能读写哪些文件？能去哪里联网？能看哪些 credential？OS privilege/resource？死亡后什么 survive？怎么重建？哪些 output 自动 trusted/promoted？side effect 怎样 retry-safe？

如果答不上这些，“我们跑在 container 里”还不能称为完整 architecture。
