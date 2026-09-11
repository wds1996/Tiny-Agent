# Stage 13：让任务穿过 Worker 故障继续执行——Long-Horizon Agent Harness

> Language: [English](README.md) | **简体中文**

[Stage 12](../12-agent-workspace-sandbox/README.zh-CN.md) 为一次 Agent 工作会话建立了 Workspace 和执行边界。但真实产品里也会有无法在一次会话内完成的任务：例如 Agent 先起草报告、等待校验、按反馈修复，再生成最终产物，整个过程可能持续数分钟甚至数小时。

现在设想：报告刚起草完，正在执行任务的 Worker 就崩溃了。接手的 Worker 不能假定上一个 Python 变量、模型 Context 或 Workspace 仍然存在；它必须从一个持久化记录中知道已经完成了什么，以及接下来允许做什么。

**Long-Horizon Harness（长任务执行框架）** 就是这份记录及其恢复规则。本章会跟踪同一个报告任务经历 draft、verify、一次 repair 与 finalize。离线版本使用确定性函数，便于观察状态变化；最后再把真实 DeepSeek 调用放进同一套持久化结构。

---

## 1. 为什么普通循环无法恢复长任务

短任务通常可以只靠内存里的循环：

```python
def draft(progress: dict) -> dict:
    return {"draft": "first draft"}


def verify(progress: dict) -> dict:
    return {"verified": True}


def finalize(progress: dict) -> dict:
    return {"artifact": f"report built from {progress['draft']}"}


def run_task() -> dict:
    progress: dict = {}
    for step in (draft, verify, finalize):
        progress.update(step(progress))
    return progress


print(run_task()["artifact"])
```

这里的 `progress` 只存在于当前 Python 进程。若进程在 `draft()` 之后停止，接手的新进程无法可靠回答三个问题：

```text
刚才执行的是哪一个任务？
哪个步骤已经成功完成？
下一步应该拿到什么输入？
```

从聊天总结或一条日志去猜这些答案并不可靠。任务运行时间变长后，执行状态必须保存到 Worker 之外。

## 2. 把一个任务拆成可以交接的 Work Unit

本章固定使用四个名称：

| 名称 | 含义 |
| --- | --- |
| **Task** | 一个需要持续追踪、面向用户的工作，例如“准备这份报告”。 |
| **Work Unit** | Task 内一个有边界的操作，例如 draft 或 verify。 |
| **Worker** | 临时执行一个 Work Unit 的进程；完成后它可以消失。 |
| **Ledger** | 记录 Task 当前状态的持久化账本，任何 Worker 都从这里接手。 |

本章的 `TaskLedger` 使用 SQLite 实现。它的 `TaskRecord` 会保存任务的 `status`、下一步 `step_index`、小型 `progress` 字典、Repair Budget，以及临时 Lease 信息。核心生命周期是：

```text
创建 task
    → 一个 Worker 领取一个 Work Unit
    → 持久化该 unit 的 output
    → 排队下一步、排队 repair，或完成 task
    → 任意符合条件的 Worker 领取下一步
```

先从仓库根目录运行完整离线示例：

```bash
python stages/13-long-horizon-harness/code/demo.py
```

示例会故意要求一次 repair。请把输出轨迹理解为“同一个 Task 被交接”，而不是“某个 Worker 一直持有一个循环”：

| Work Unit | 本次输出 | 本次结束后的 Durable Task |
| --- | --- | --- |
| draft，attempt 0 | `draft-v0` | `queued`，下一步 `step_index=1` |
| verify，attempt 0 | 请求从 step 0 repair | `queued`，`step_index=0`，`repair_count=1` |
| draft，attempt 1 | `draft-v1` | `queued`，下一步 `step_index=1` |
| verify，attempt 1 | verified | `queued`，下一步 `step_index=2` |
| finalize，attempt 1 | artifact | `completed`，`step_index=3` |

Task 能穿过任意两行之间的 Worker 故障继续执行，因为 Ledger 已经持久化了交接所需的信息。

## 3. 每个 Worker 只领取并持久化一个 Unit

构造 `LongHorizonHarness` 时，会传入 Ledger 和按顺序排列的 Step 函数。下面的完整 `work_once` 操作展示了它的边界：领取一个 Task、运行一个 Step、保存该 Step 的 Output，然后推进或请求 Repair。

```python
def work_once(ledger, steps, *, worker_id: str):
    task = ledger.claim(worker_id=worker_id, lease_seconds=10)
    if task is None:
        return None

    output = steps[task.step_index](dict(task.progress))
    ledger.record_step_output(
        task.task_id,
        worker_id=worker_id,
        step_index=task.step_index,
        output=output,
    )

    if output.get("needs_repair"):
        progress = {**task.progress, **output}
        progress.pop("needs_repair", None)
        progress.pop("restart_step", None)
        return ledger.request_repair(
            task.task_id,
            worker_id=worker_id,
            restart_step=int(output.get("restart_step", 0)),
            progress=progress,
        )

    return ledger.advance(
        task.task_id,
        worker_id=worker_id,
        progress={**task.progress, **output},
    )
```

真实实现位于 [`code/harness.py`](code/harness.py)，逻辑相同，只是用 `WorkResult` 包装了返回的 Task 与 Output。注意它**没有**把 Task 从 0% 一直占有到 100%：状态一旦被保存，下一位符合条件的 Worker 就可以继续。

`needs_repair` 与 `restart_step` 是本次状态迁移的 Host 控制指令。它们会保留在 Output History 中，但会从后续 `progress` 里移除；后续模型调用需要 Task 事实，而不是一条旧的“继续 repair”指令。

## 4. Lease 提供的是临时所有权

只把 Task 标为 `running` 不够。Worker 死亡后，Task 可能永远停在 `running`。**Lease（租约）** 同时记录 Owner 和到期时间：

```text
lease_owner = worker-a
lease_until = 105
```

在时间 104，其他 Worker 不能领取它；到时间 106，另一个 Worker 可以接手：

```python
from pathlib import Path
import tempfile

from ledger import TaskLedger

with tempfile.TemporaryDirectory() as tmp:
    ledger = TaskLedger(Path(tmp) / "ledger.db")
    ledger.create_task(total_steps=1)

    first = ledger.claim(worker_id="worker-a", lease_seconds=5, now=100)
    assert ledger.claim(worker_id="worker-b", lease_seconds=5, now=104) is None

    replacement = ledger.claim(worker_id="worker-b", lease_seconds=5, now=106)
    print(first.lease_owner, replacement.lease_owner)  # worker-a worker-b
```

如果一个 Work Unit 可能超过 Lease 时长，Owner 需要调用 `heartbeat()`。Ledger 只接受当前 Owner 且 Lease 尚未到期时的 Heartbeat、Output 写入、推进和 Repair 请求。过期的 Worker 在别人接手后无法再写入过时结果。

这保护的是 Ledger，并不保证外部动作“恰好执行一次”。Worker 可能已经发送邮件，却在记录成功前崩溃，接手者仍可能重复该操作。正如 Stage 06 与 Stage 09 所学，外部工作仍需 Idempotency Key、完成验证或补偿策略：

```text
recovery != exactly once
```

## 5. 分开保存恢复状态、Output History 与 Repair 限制

Ledger 有意把不同性质的信息分开：

```text
Task progress  → 下一 Work Unit 需要的少量事实
Step outputs   → 每一次尝试实际返回了什么
Artifact       → 必须活过本次会话的大型或面向用户的结果
Model Context  → 当前这一次模型调用应看到的信息
```

Step Output History 使用 `(task_id, attempt, step_index)` 作为键。Repair 重新运行 step 0 时，`draft-v1` 不能覆盖 `draft-v0`：二者共同说明 Task 为什么发生变化。`ledger.step_outputs(task_id)` 返回完整历史；`step_output(task_id, step_index)` 为方便使用而返回最新的一份。

Verify 发现问题时，可以只返回这样的数据：

```python
{
    "needs_repair": True,
    "restart_step": 0,
    "revision": 1,
    "feedback": "add one repair pass",
}
```

执行状态迁移的是 Host，不是 Verifier：Host 保存 Output、增加 `repair_count`、释放 Lease，并重新排队 step 0。如果已经达到 `max_repairs`，Task 会变为 `failed`。时间、成本、权限、Tool Scope 与审批等待也需要同样明确的限制。长任务的含义是可以恢复，不是拥有无限自主权。

Stage 12 的 Workspace 仍然是当前的工作台。新 Worker 若需要源文件、输入数据、依赖或大型结果，应用必须保存 Artifact Reference 并重建 Workspace。Continuation Prompt 可以使用 Task ID、Progress、Output History 与这些 Reference；一段自然语言总结有助于理解，但不足以作为恢复状态。

理解这些状态迁移后，运行离线检查：

```bash
python stages/13-long-horizon-harness/code/checks.py
```

检查覆盖 Lease 到期和归属、过期 Worker 写入、Repair 前后的 Output History、单 Unit 交接、Repair 耗尽、Progress 恢复以及 Completed Task 行为。

## 6. 把真实 DeepSeek 调用放进同一条边界

离线 Demo 使用确定性函数，因此轨迹和检查稳定。真实 Agent 可以在某些 Work Unit 内调用模型，同时不把恢复控制权交给模型。[`code/deepseek_long_horizon.py`](code/deepseek_long_horizon.py) 使用 DeepSeek 起草和校验报告，但 `TaskLedger` 与 `LongHorizonHarness` 保持不变。

```text
DeepSeek draft/review function
    → 返回普通 step-output dictionary
    → Host 验证后修改 durable task state
    → 另一个 Worker 仍可从 Ledger 恢复
```

模型可以提出 `REVISE: ...`，却不能延长 Lease、标记 Task 完成或移除 Repair Limit。Host 会先解析并验证这项提案，之后才修改状态。

安装可选依赖后，填写账号中实际可用的模型 ID：

```bash
python -m pip install -r stages/13-long-horizon-harness/code/requirements.txt
set "DEEPSEEK_API_KEY=your_key_here"
set "DEEPSEEK_MODEL=your_model_id"
python stages/13-long-horizon-harness/code/deepseek_long_horizon.py
```

PowerShell 请在最后一条命令前设置 `$env:DEEPSEEK_API_KEY="your_key_here"` 与 `$env:DEEPSEEK_MODEL="your_model_id"`。示例会交替使用 Worker ID，并打印 Durable Task Trace 与 Output History。演示结束后临时 SQLite 文件会被删除；生产系统应使用受管理的持久化存储与 Artifact Storage。

## 7. 把这条边界带入 Capstone

Harness 是组合前面知识，而不是替代它们：

```text
提交 durable task
    → Stage 13 Ledger 分配临时 Lease
    → bounded Agent Runtime 使用 Stage 03–10 的机制
    → Stage 12 Workspace 承载一次工作会话
    → outputs 与 artifacts 被持久化
    → 另一个 Worker 可以 rehydrate 并继续
```

课程中的边界始终一致：模型提出一个 Work Unit 的结果；Host 验证 Owner、Budget、Permission、状态迁移以及对外可见的 Artifact。

[Stage 14：Capstone Enterprise Agent](../14-capstone-enterprise-agent/README.zh-CN.md) 会据此组合 Support Agent 实际需要的机制。
