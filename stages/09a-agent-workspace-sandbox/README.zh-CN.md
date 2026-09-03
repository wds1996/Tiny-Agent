# Stage 09A — Sandboxed Agent Workspace 与 Computer Environment

> Language: [English](README.md) | 简体中文

现代 Agent 越来越不只调用窄 API Tool。它们会查看文件、执行命令、修改代码、创建 artifact、安装依赖，并在许多 step 中维护 working directory。

这会改变 architecture：

```text
Agent harness
    |
    | proposals / tool requests
    v
execution policy
    |
    v
sandbox / compute environment
    |
    +--> filesystem
    +--> shell/processes
    +--> packages
    +--> artifacts
```

核心结论：

> **Workspace 是 application state；subprocess 是 process boundary；container 是更强 isolation boundary；这些名字都不能随便升级成“完美 sandbox”。**

---

## 为什么放在 Safety 和 Multi-Agent 之后？

在给模型 computer-like environment 前，应该先理解 least privilege、approval vs authorization、timeout/retry safety、prompt injection、Multi-Agent context/authority boundary。

否则“给 Agent shell access”不是 architecture，而是在做 blast-radius 实验。

---

## 学习目标

你应该能：

1. 区分 harness、workspace、process、container、VM、sandbox；
2. 把 file read/write 限定在 application-owned root；
3. 把 durable artifact 显式外置，而不是塞进 model context；
4. 解释 `subprocess` 为什么不是 security sandbox；
5. 不用 `shell=True`、不拼 model string 执行 command；
6. 给 container baseline 应用 network/capability/PID/CPU/memory/user/filesystem restriction；
7. 把 orchestration credential 留在 model-generated environment 外；
8. 解释 egress policy 与 data-exfiltration risk；
9. 区分 disposable compute 与 durable harness/run state；
10. output 在 promotion 前先 evaluate/snapshot。

---

## 推荐学习顺序

1. [`theory/01-harness-workspace-compute-and-sandbox.zh-CN.md`](theory/01-harness-workspace-compute-and-sandbox.zh-CN.md)
2. [`theory/02-files-artifacts-and-workspace-policy.zh-CN.md`](theory/02-files-artifacts-and-workspace-policy.zh-CN.md)
3. `code/workspace_demo.py`
4. [`theory/03-container-isolation-and-threat-model.zh-CN.md`](theory/03-container-isolation-and-threat-model.zh-CN.md)
5. `code/docker_sandbox_demo.py`
6. [`theory/04-credentials-network-snapshots-and-recovery.zh-CN.md`](theory/04-credentials-network-snapshots-and-recovery.zh-CN.md)
7. `src/tiny_agent/workspace.py`
8. `tests/test_workspace.py`
9. [`exercises/review-questions.zh-CN.md`](exercises/review-questions.zh-CN.md)

---

## 当前行业方向

OpenAI 2026 年 4 月 Agents SDK 更新明确把 model-native harness 与 controlled sandbox compute 分开，并增加 filesystem/shell-oriented workspace，用于 long-horizon task。

Provider-independent 的核心并没有变化：**强 Agent 需要 execution environment，但 orchestration credential 与 policy 应留在 environment 外。**

参考：https://openai.com/index/the-next-evolution-of-the-agents-sdk/

---

## Tiny-Agent Baseline

`AgentWorkspace` 通过 resolved-root check 限制 filesystem path。

`DockerSandboxRunner` 默认使用：

```text
network none
read-only root filesystem
writable mounted workspace
cap-drop ALL
no-new-privileges
PID limit
memory limit
CPU limit
non-root user
tmpfs /tmp
no shell interpolation
```

这比在 host process 直接执行 arbitrary model text 安全得多，但仍然不宣称普通 Docker config 足以保护所有 hostile multi-tenant workload。

---

## Milestone

你应该能明确回答：model-generated code 在哪里跑？能碰哪些文件？能访问哪些 network destination？能看哪些 credential？container 丢失后什么仍然存在？哪个 deterministic component 仍可以 deny execution？
