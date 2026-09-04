# 01 — Harness、Workspace、Compute 与 Sandbox

> Language: [English](01-harness-workspace-compute-and-sandbox.md) | 简体中文

现代 Agent 会检查 repository、编辑文件、执行命令、安装依赖、产生 artifact，并跨许多 step 工作。

几个概念容易混淆：

```text
Agent harness
    = 围绕 model work 的 orchestration/control layer

workspace
    = 一个 run/project 的 application-owned files/artifacts

process
    = 一个 OS execution unit

container / VM
    = 更强的 compute/isolation boundary

sandbox
    = 带显式 threat model 的 governed execution environment
```

把 `subprocess.run()` 叫 sandbox，并不会让它突然拥有 sandbox 性质。就像给纸箱贴上“银行金库”的牌子，保险公司通常也不会因此改变看法。

---

## 1. Harness 拥有 Orchestration，而不是 Arbitrary Code Execution

Harness 可以拥有 objective、Tool/Skill exposure、context assembly、budget、approval state、task ledger、artifact refs、trace/eval。

它决定“下一步应该做什么”。

Risky/model-generated code 应在需要时放到独立 compute boundary 后：

```text
model proposal
-> harness policy
-> execution request
-> sandbox/compute
-> artifact/result
-> harness evaluates and continues
```

这样 orchestration credential 与 durable state 不会跟 disposable compute 混在一起。

---

## 2. Workspace 是 Externalized Working Memory

可以存 source、notes、intermediate data、report、test log、patch、artifact。

这些不需要全放 model context：

```text
workspace: potentially GBs
model context: selected KB/MBs
```

这就是 Context Engineering 应用于文件。

---

## 3. `AgentWorkspace`

```python
workspace = AgentWorkspace("./work/run-42")
workspace.write_text("notes/plan.md", "# Plan\n1. inspect tests")
```

默认 exclusive creation；要覆盖必须 `overwrite=True`。

这个小设计很有用：silent destructive write 并不是一种值得鼓励的“便捷体验”。

---

## 4. Ordinary Subprocess != Security Sandbox

```python
subprocess.run(["python", "generated.py"])
```

通常继承 host kernel、caller filesystem permission、environment variable、network、process spawn 能力、reachable local service。

Timeout 只控制时间，不会撤销 filesystem/network authority：

```text
timeout != isolation
```

---

## 5. Container 增加 Isolation Control

Tiny-Agent baseline：read-only root、network default off、drop capabilities、no-new-privileges、PID/memory/CPU limit、non-root user、bounded writable workspace、tmpfs `/tmp`。

显著强于直接在 web/Agent process 跑生成代码，但仍只是 baseline，不是“Docker=对所有 hostile workload 完美安全”的证明。

---

## 6. Harness State 应能 Survive Compute Loss

```text
TaskLedger
-> container analyzes
-> container dies
```

如果 ledger 只存在 container 里，orchestration state 也死了。

更好：durable harness/workspace metadata + disposable compute + governed artifact。

Stage 14 会建立 long-horizon recovery。

---

## 7. Coding Agent 示例

```text
1. harness selects coding/review Skill
2. workspace contains repo snapshot
3. model reads failing test + relevant source
4. model proposes patch
5. patch applied in governed workspace
6. sandbox runs pytest with no network
7. result returns to harness
8. evaluator checks tests + diff constraints
9. accept / repair / review
```

修一个本地单测，模型通常不需要 host SSH key 或 production DB credential。

Least privilege 往往从一个看起来很“傻”的问题开始：

> **这个测试进程为什么需要访问互联网？**

---

## 8. Narrow Tool 何时优于 Shell？

只需 `get_invoice(invoice_id)`，就用 typed API Tool。它比 `shell + DB credential + curl + hope` 更容易 validation/authorization/observability/evaluation。

只有任务真正需要 open-ended filesystem/process interaction 时，再使用 sandboxed computer environment。

---

## 9. Threat-model Ladder

从较弱到较强、通常成本也更高：

```text
same process
child process
container
hardened container runtime
microVM / VM
separate worker/host/account/project
```

没有 universal best sandbox；根据 code trust、tenant isolation、secret/data sensitivity、network、performance、ops maturity 选择。

---

## Completion Principle

> **Harness 是 durable control；workspace 是 governed working state；compute 是 risky execution 发生的地方；sandbox 是 threat-model decision，不是 `subprocess` 的同义词。**
