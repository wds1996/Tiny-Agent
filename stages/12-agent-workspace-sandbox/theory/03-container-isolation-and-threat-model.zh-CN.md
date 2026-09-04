# 03 — Container Isolation 与 Threat Model

> Language: [English](03-container-isolation-and-threat-model.md) | 简体中文

Child process 与 host 共用 kernel，并继承 ambient authority；container 加入 isolation mechanism，但是否安全取决于 configuration 与 threat model。

有用的问题不是：

> Docker 安全吗？

而是：

> **面对哪种 attacker、哪些 data/credential/network access、什么 runtime configuration，它是否足够安全？**

---

## 1. Docker Baseline

```text
docker run --rm
  --read-only
  --cap-drop ALL
  --security-opt no-new-privileges
  --pids-limit 128
  --memory 512m
  --cpus 1.0
  --user 65534:65534
  --tmpfs /tmp:rw,noexec,nosuid,size=64m
  --volume <workspace>:/workspace:rw
  --workdir /workspace
  --network none
  python:3.12-slim
  <argv...>
```

每个 flag 处理不同 failure mode。

---

## 2. Read-only Root

`--read-only` 减少 container image 内可修改文件；workspace 作为单独 writable mount。

```text
runtime/dependencies -> read-only
working artifacts    -> explicit writable mount
```

---

## 3. Drop Capability / Privilege Escalation

```text
--cap-drop ALL
--security-opt no-new-privileges
--user 65534:65534
```

不要因为 container 之后会删除，就让 generated code 用 root。临时 root 问题仍然是 root 问题，只是它很守时地按时消失。

---

## 4. Resource Exhaustion

防 infinite spawn/memory allocation/loop：PID limit、memory、CPU、wall-clock timeout、output cap。

单项不够，组合约束常见 DoS path。

---

## 5. Network Default Off

`--network none` 对很多 local test/code task 完全合理，并从结构上切断多种 exfiltration/download path。

真需要 network，应明确 destination/protocol/credential/data class/logging。`needs internet` 通常过于宽泛。

---

## 6. 不要拼 Shell String

坏：

```python
subprocess.run(f"docker run ... {model_command}", shell=True)
```

好：argv vector，让 Docker CLI/container process 收到显式 arguments，不经过 host shell interpolation。

---

## 7. Ordinary Docker 不是终点

更高风险可能需要 custom seccomp、AppArmor/SELinux、rootless、gVisor/Kata、microVM/VM、tenant host/account isolation、signed/pinned image、egress proxy、ephemeral workload identity。

“Docker = perfectly safe sandbox”很好记，也能以很有创意的方式把人带沟里。

---

## 8. Threat Model Examples

- trusted internal script + no secrets + local data：constrained container 可能足够；
- arbitrary attacker code + sensitive multi-tenant host：需要更强 isolation；
- model-generated data science + private data + selected package access：需要 ephemeral sandbox、controlled mount、allowlisted egress、无 orchestration master credential。

同一个“sandbox”词，背后可能是完全不同 threat model。

---

## 9. CI 应真正执行 Boundary

Unit test 检查 flags/policy；integration smoke 真正启动受限 container。

从未实际运行过的 security configuration，属于一种非常有抱负的文档写作。

---

## 10. Sandboxing 不解决什么？

不会自动解决 prompt injection、Tool authorization、tenant ownership、malicious artifact、licensing/privacy、exactly-once、generated-code correctness。

Sandbox 只限制 execution blast radius，其他层由其他 stage 负责。

---

## Invariant

> **Open-ended/model-generated code 只获得完成任务所必需的最小 filesystem、network、credential、privilege 与 resource authority；isolation boundary 必须由明确 threat model 选择。**
