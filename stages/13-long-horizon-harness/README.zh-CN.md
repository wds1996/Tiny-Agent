# Stage 13：报告写到一半，进程没了怎么办？——长任务执行与恢复

> Language: [English](README.md) | **简体中文**

[上一章](../12-agent-workspace-sandbox/README.zh-CN.md)给 Agent 准备了一张工作台：文件放在哪里，哪些命令允许执行，什么结果可以交付，都有了边界。现在产品同事小林交来一个任务：“帮我写一份客服助手试点报告。先起草，检查有没有遗漏，不合格就修改，最后交一份正式文档。”这件事可能跨越多次模型调用，也可能跨越几个工作会话。工作台有了，但负责干活的程序不一定能从头陪到尾。

我们就从一次不巧的重启开始。报告刚起草好，执行进程退出了；新的进程启动后，只收到一句“继续刚才的任务”。继续什么？草稿在哪里？上次是还没检查，还是检查过但不合格？把这句话发给模型，并不能把丢掉的变量叫回来。我们需要让接手者从保存下来的事实继续，而不是考验它的想象力。

这里把领取并执行工作的进程叫作 **Worker**。它是运行 Python 的进程，不是大模型；某个步骤可以调用模型，也可以只是普通函数。**长任务执行框架（Long-Horizon Harness）** 是围绕这些工作建立的运行支撑，包括交接记录、执行资格、恢复输入、结果验收和产物保留。本章实现其中一条可检查的主线：一份报告如何在进程更换、内容返工之后仍然正确交付。它不是给模型加一条“请一直努力”的提示词。

## 1. 先问清楚，怎样才算把报告做完了

小林给出的材料很少：试点计划涉及 20 名客服；助手可以建议回复，但不能执行退款；目前还没有试点结果。报告必须包含 `Background`（背景）、`Risks`（风险）和 `Recommendation`（建议）三部分，也不能编造“效率提升了 30%”之类尚未发生的成绩。先明确这些要求很重要，否则程序即使恢复了运行，也可能沿着错误的目标继续忙碌。

一个直觉上的实现是先调用起草函数，再检查草稿，通过后生成文档。下面先只看这个顺序：

```python
draft = write_report(requirements)
review = check_report(requirements, draft)
artifact = render_report(draft)
```

这段顺序没有展示不通过时的处理，暂时也没有保存任何进度。假如第一行已经返回，第二行还没执行，进程就退出了，那么 `draft` 变量也随之消失。反过来，如果只是模型网络请求失败，而进程还活着，变量可能还在。我们不能把这两类失败混成一句“再试一次”，因为恢复时能够依赖的信息不同。

Stage 06 已经讲过用持久化检查点保存执行状态。本章不是推翻这个办法，而是在它上面再加几个问题：谁有权接手这份状态？两个执行者同时来怎么办？已经失去执行资格的人，还能不能提交结果？另外，报告内容不合格时，哪些结果需要保留，哪些判断必须作废？先记住眼前的任务，遇到这些问题时我们再逐个加规则。

## 2. 给接手者留一张真正有用的任务单

假设我们请另一位同事继续检查草稿。合理的交接不是发一句“你看着办”，而是留下任务要求、已有草稿，以及下一步该做什么。程序需要的也是这种交接记录。我们给整份报告一个固定编号 `report-001`；起草、检查、定稿则分别是其中一个有边界的工作步骤，也称 **Work Unit**。

这里为什么按“起草、检查、定稿”划分，而不是把整份报告当一步？因为一个步骤尚未提交就失败，恢复者只能重做这段尚未被接受的工作；步骤越大，重复计算的代价通常越高。不过，也没有必要把每生成一句话都变成一次交接，那会增加保存与调度的负担。合适的步骤应该有清楚的输入、可检验的输出，而且重做成本可以接受。起草和校验刚好是这份报告的自然边界。

一份任务会经历多个步骤，但换了执行者，任务编号不能跟着换。否则第二个进程只会创建一份新报告，并没有恢复原来的报告。起草成功之后，任务记录里与交接有关的部分应该类似这样：

```python
{
    "task_id": "report-001",
    "status": "queued",
    "step_index": 1,
    "inputs": {
        "request": "Assess a pilot AI assistant for support staff; do not invent pilot results.",
        "sections": ["Background", "Risks", "Recommendation"],
        "facts": ["The proposed pilot includes 20 support staff."]
    },
    "progress": {"draft": {"Background": "...", "Recommendation": "..."}}
}
```

这只是相关字段的示意，实际输入还保存了不能退款、尚无试点结果两条事实。`inputs` 是创建任务时确定的要求和材料；`progress` 是执行后得到的草稿、反馈等信息。`step_index=1` 表示下一步执行步骤列表中的第二项，也就是 `verify`，并不是“已经完成了 1%”。`queued` 表示这一步正在等待领取。

我们把保存这张任务单的组件叫作 **任务账本（Ledger）**。在 [`code/ledger.py`](code/ledger.py) 中，它使用 SQLite 文件。它不是模型的长期记忆，也不只是日志：程序会依据它决定下一步是否允许执行。自然语言总结可以帮助人理解，但不能替代这里明确的步骤位置、状态和数据。

先实际交接一次。以下终端命令都从仓库根目录运行，离线部分只需要 Python 3.10 及以上版本：

```bash
python stages/13-long-horizon-harness/code/worker.py create --db report.db --task-id report-001
python stages/13-long-horizon-harness/code/worker.py work --db report.db --task-id report-001 --worker-id alice
python stages/13-long-horizon-harness/code/worker.py inspect --db report.db --task-id report-001
```

第一条命令创建任务后就结束了。第二条命令在一个新的 Python 进程里执行一次起草，保存交接记录，然后也结束。第三条命令又启动一个新进程，只读取账本。你会看到草稿还在，下一步已经变成 `step_index=1`。这时可以关闭终端，稍后回到同一个仓库目录，使用同一个 `--db` 和 `--task-id` 再执行 `work`。下一位 Worker 会检查已有草稿，而不是凭空重新创建任务。

`worker.py` 不会在退出时删除数据库。重复 `create` 同一个任务编号会报错，避免把已完成的工作重置。重新做实验时可以选择另一个任务编号或数据库文件；恢复现有任务时则不要重新创建。这里有一个不可省略的前提：数据库文件必须仍然存在并且可访问。进程退出不等于数据库丢失，但如果文件也被删除，账本不会自己从空气里长回来。

现在我们看到了一次成功交接。不过，“保存了草稿”与“登记下一步去检查”到底是不是同一件事？这个问题决定了下一次故障会不会留下半张任务单。

## 3. 写完草稿，不等于已经完成交接

设想一个粗心的实现先保存草稿结果，随后才更新任务位置。在这两次保存之间发生故障，接手者可能看到一份新草稿，却仍被指示去起草。反过来，先推进步骤、再保存结果也不行：接手者会被安排去检查一份根本不存在的草稿。故障偏偏很擅长挑我们认为“就差一行”的地方发生。

本章选择一个明确的完成条件：**步骤结果、当前进度和下一步位置必须在同一个数据库事务里提交。** 定稿时，报告正文也在这笔事务里保存。这样，对之后读取账本的进程而言，这次交接要么整体生效，要么整体没有生效。这个性质叫事务的原子性，作用范围是这一笔数据库事务，不是程序调用过的所有外部系统。[SQLite 的原子提交说明](https://www.sqlite.org/atomiccommit.html)解释了这一边界。

先看代码如何建立事务范围。下面是账本连接管理中的主体，`write=True` 用于需要修改账本的操作：

```python
conn = sqlite3.connect(self.path, isolation_level=None, timeout=1.0)
conn.row_factory = sqlite3.Row
try:
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA synchronous=FULL")
    conn.execute("BEGIN IMMEDIATE" if write else "BEGIN")
    yield conn
    conn.commit()
except BaseException:
    conn.rollback()
    raise
finally:
    conn.close()
```

`yield conn` 把连接交给 `with` 内的业务代码；业务代码正常结束才提交，异常逃出则回滚，最后无论如何关闭连接。`isolation_level=None` 在这里配合显式 `BEGIN` 使用，避免把事务开始时机藏在隐式行为里。连接的生命周期和事务的生命周期是两件事，因此代码明确执行 `close()`，不能把“事务提交了”理解成“连接也关闭了”。相关行为可对照 [Python 的 sqlite3 文档](https://docs.python.org/3/library/sqlite3.html)。

`commit_step()` 就在这一范围里插入步骤历史、合并进度，并更新任务位置。事务提交成功后，任务重新排队或结束；调用方拿到返回结果前，提交已经完成。若进程是在提交后、打印成功消息前退出，数据库记录仍然有效。接手者应该读账本，而不是因为终端里没出现“成功”就把工作全部重做。

注意，起草报告本身不在这笔事务里。如果一次模型请求要等半分钟，我们不能一直占着数据库写锁陪它思考。执行是较长的一段，交接是很短的一段；下一节会把“谁在执行”也记下来，让这两段分开后仍然有秩序。

## 4. 两位同事同时接单，不能靠礼貌避让

现在小林觉得报告积压太多，启动了两个 Worker。它们可能几乎同时读取到 `report-001` 正在排队。如果程序只是先读状态，稍后再把状态写成 `running`，两个人都可能认为自己成功领到了工作。这是典型的“看一眼没问题，真正动手时条件已经变了”。

所以**检查是否可领取，以及把任务登记给领取者，也必须在同一个短事务中完成**。SQLite 同时只允许一个写事务；`BEGIN IMMEDIATE` 在开始时就申请写事务。一个领取者完成检查与登记以后，另一个才有机会依据新的状态判断，而不是沿用早先看到的排队状态。写锁无法及时取得时也可能报忙，本章让异常显式返回，不假装领取成功。[事务文档](https://www.sqlite.org/lang_transaction.html)给出了准确语义。

一次成功领取会做这样的更新：

```python
conn.execute("""
    UPDATE tasks SET status='running', lease_owner=?, lease_token=?,
        lease_until=?, claim_count=claim_count+1 WHERE task_id=?
""", (worker_id, uuid4().hex, now + lease_seconds, task_id))
```

`lease_owner` 记执行者的名字；`lease_token` 是这一次领取独有的凭证；`lease_until` 是有效期限；`claim_count` 记录任务已经被成功领取了几次。先别急着把后面三个字段背下来，我们马上就会用到它们。重要的是：领取事务完成后，写锁立即释放，Worker 才开始起草或检查。其他任务不需要等这一份报告写完才能登记。

这种分工让一次调用非常清楚：领取一个步骤，读取它需要的输入，执行，提交交接。我们并不让某个 Worker 从头到尾“占有这份报告”。它完成当前步骤后可以退出，另一个进程可以接着做。可是，如果领取者还没提交就失联了，总不能让它的名字永久霸占任务单。期限正是为这个问题准备的。

## 5. 失联以后可以接手，但旧结果不能回来抢位置

假设 Alice 在时间 100 领取了校验工作，获得 5 秒执行资格。账本把有效期记到 105。在 104 时，Bob 不可以接手；到 **105，也就是到期的这一刻**，本章规定资格失效，Bob 可以尝试领取。不需要额外等到 106，边界条件就是 `lease_until <= now`。

这种有期限的资格就是 **Lease（租约）**。租约过期不是对进程死亡的证明：Alice 可能崩溃了，也可能只是暂停太久。系统只是在说：“我不能无限期等你，因此之后的提交不再接受你原来的资格。”它解决的是任务怎样摆脱失联者，不会远程把旧进程变没。

因此，领取时检查一次还不够，**提交结果和续期时都要重新检查**。账本会在写事务中读回当前记录，比较这次领取的 Owner、Token、步骤和修订轮次，并用当时的时间检查到期条件。关键判断包括：

```python
current.lease_owner != claim.lease_owner
current.lease_token != claim.lease_token
current.step_index != claim.step_index
current.repair_count != claim.repair_count
current.lease_until <= self.clock()
```

这些条件中的任一个成立，或者任务已不处于 `running`，都会拒绝提交。完整判断还处理了到期字段为空的情况。这里比较的是**提交时账本里的当前值**，不是领取时那个 Python 对象自己声称的有效期。时钟也不能冻结在步骤开始之前，否则一个执行了半天的调用，结束时仍可能以为现在是早上十点整。

为什么光比较 `worker_id` 不够？因为一个程序重启以后可能仍然叫 `alice`。旧进程迟到，新进程已经重新领取，如果名字相同，就分不清两次资格。每次领取生成不同的 `lease_token`，旧结果即使顶着同一个名字，也拿不出新票号。它只是本章可信 Worker 之间的并发校验凭证，不是用户身份认证，更不是跨外部系统自动生效的权限令牌。

现在失联者不会永久卡住报告，迟到者也不能覆盖接手者的进度。但还有一种正常情况：Alice 没有失联，只是模型起草比较慢。固定等 5 秒就宣布她的资格作废，显然也不合适。

## 6. 活着而且还在工作，就定期续租

长步骤需要在有效期内续期。这个动作叫 **heartbeat（心跳）**：Worker 定期向账本申请延长当前租约，而账本仍然核对它持有的是不是有效资格。过期之后不能拿旧凭证补签，必须重新走领取流程。

本章在执行步骤时启动一个辅助线程。主线程可以等待模型响应，辅助线程约每隔租约时长的三分之一续一次租；每次续期使用独立的短连接，不跨线程共用 SQLite 连接。核心循环如下：

```python
while not self.stop.wait(self.lease_seconds / 3):
    try:
        self.check()
        self.ledger.heartbeat(self.claim, lease_seconds=self.lease_seconds)
    except Exception as exc:
        self.error = exc
        return
```

`Event.wait()` 既让线程等待一小段时间，也允许主线程在步骤结束时把它唤醒退出。续租失败会被记录下来，此后即使模型返回了看起来很好的报告，也不能提交。退出续租范围时会等待线程收尾，然后再尝试交接；账本在交接事务里仍会进行最后的资格检查。线程只是帮助及时续期，不是绕过账本检查的第二条路。

不过，心跳只能说明这段代码还能续租，不能证明报告在取得进展。一个永远卡住的外部请求，也可能配着一个认真打卡的心跳线程。为此，`LeaseKeeper` 还有独立的单步骤时限：默认 120 秒。到达时限后停止续期，迟到的结果被拒绝，而不是因为“我一直在续租”就无限延长工作。

本章用墙上时间 `time.time()` 保存租约期限，便于同机其他进程读取；用单调时钟 `time.monotonic()` 计算本次执行的已耗时间。两者用途不同。这里仍假定可信进程共享同机存储，时钟和文件系统工作正常；它不是跨机器时钟故障下的完整分布式租约方案。

还要说清楚这个时限没有做什么：它**不能强杀任意阻塞的 Python 函数，也不能取消已经发送到模型服务的请求**。函数迟迟不返回时，主线程仍可能等待；停止续租后，接手者有可能和旧请求在外部系统中重叠执行。需要硬隔离和进程终止时，应继续使用上一章讨论的执行环境边界。不要把“禁止提交迟到结果”误读成“世界上不会再有迟到的工作”。

## 7. 程序没崩，但报告不合格：这是返工，不是故障重试

回到那份报告。第一次离线起草会故意漏掉 `Risks`。校验步骤拿着最初的要求和当前草稿一比较，发现风险这一部分不存在，于是给出“Missing required sections: Risks”。这是一次**成功完成的检查**，只是检查结论要求修改；它和网络断开、进程崩溃没有同样的含义。

先让步骤返回一个清楚的结果对象。业务事实放在 `data`，需要回到前一步时另外给出 `restart_step`：

```python
@dataclass(frozen=True)
class StepResult:
    data: dict[str, Any]
    restart_step: int | None = None
    artifact: str | None = None
```

三部分各有用途。草稿和反馈进入后续进度，重启位置只用来请求这一次转移，定稿正文则作为产物保存。这样就不需要把 `needs_repair=True` 混进业务数据，让下一轮不断误以为还有一条旧的返工命令没处理。

校验函数先判断缺少哪些章节，再形成反馈。只看这条本地规则：

```python
missing = [section for section in inputs["sections"] if section not in draft]
if missing:
    verdict = {"ok": False, "feedback": "Missing required sections: " + ", ".join(missing)}
```

之后由应用把“不通过”转换成返回起草步骤的请求：

```python
return StepResult(data, restart_step=None if verdict["ok"] else 0)
```

模型以后可以负责判断内容是否符合任务，但不能自行选择跳到哪一个步骤。这里去哪里返工是应用已经写好的规则。账本还要检查目标步骤是否有效、返工次数是否仍有余额，最后才真正修改任务状态。

账本中的 `repair_count` 从 0 增加到 1，表示现在进入第一轮返工；它不是进程重启次数。原来的草稿和不通过的校验结果保留在历史中，新一轮的草稿另存一条。下一次起草读到明确反馈后，会补上风险部分，第二次校验才会通过。离线校验只检查这个可观察的教学条件，并不声称能够判断任意报告的事实质量。

这里还需要防止一种隐蔽错误：旧草稿通过了，后来又生成新草稿，却把旧的 `verified=True` 一起带过去。新的起草结果会清空旧审核记录；校验时还保存当前草稿的摘要值，定稿时核对正在发布的是否仍是被审核的同一份内容。摘要相同说明内容未变，不说明审核一定正确，也不提供用户授权。

如果达到 `max_repairs` 仍要求返工，任务会标成 `failed`，而不是继续写。为了限制另一条路径——进程不断崩溃、始终没机会增加返工次数——我们还持久化 `max_claims`。每次成功领取都消耗一次，正常步骤和故障后的重新领取都计算在内；额度耗尽后，下一次符合领取条件的尝试会把任务置为失败。没有 Worker 来领取时，账本不会主动巡逻更新状态。每个步骤的时间限制、整个任务的领取限制和内容返工限制，分别回答不同问题。

这些规则齐了以后，再看执行入口就不会像读一排陌生的方法名。`LongHorizonHarness.work_once()` 的主体只是把刚才已经理解的三件事接起来：领取、带着保存的输入执行、提交交接。

```python
claim = self.ledger.claim(task_id, worker_id=worker_id,
                          workflow=self.workflow, lease_seconds=self.lease_seconds)
if claim is None:
    return None
with LeaseKeeper(self.ledger, claim, lease_seconds=self.lease_seconds,
                 max_unit_seconds=self.max_unit_seconds):
    output = self.steps[claim.step_index](
        deepcopy(claim.inputs), deepcopy(claim.progress)
    )
advanced = self.ledger.commit_step(claim, output)
```

`claim is None` 表示这次没有领到可执行的工作，并不必然表示整份报告已经完成，也可能是另一个 Worker 的租约还有效。步骤接收任务要求与进度的副本，返回 `StepResult`；调用期间不持有数据库事务，只有提交时重新进入短事务。`deepcopy` 防止普通步骤意外修改共享的嵌套对象，它不是防恶意代码的沙箱。到这里，账本负责保存与资格校验，业务函数负责报告内容，执行入口负责把它们按顺序连接。

## 8. 现在真的让两个进程退出，看看接手者读到了什么

至此，报告有了任务单、短事务、有限执行资格和返工规则。我们不靠“理论上应该能恢复”结束这一节，而是让程序实际在两个不同位置退出。运行：

```bash
python stages/13-long-horizon-harness/code/demo.py
```

这个演示会启动多个独立 Python 子进程，不是在一个循环中给同一个对象换名字。Alice 起草后成功提交，再故意以非零退出码结束；接下来的 Bob 执行了校验，却在提交之前退出。两次退出都由教学程序里的 `os._exit(23)` 明确触发，退出的是本次启动的子进程，不是你的终端或其他程序。

Alice 退出后，账本里已有草稿，任务排队等待校验，所以接手者不应重写草稿。Bob 退出后，校验结果没有提交，任务仍是 `running`；演示等待它的租约到期，再启动另一个进程重新校验。此时既不能假装校验通过，也不能凭一条打印信息把流程往前推。

最后会出现如下交接顺序。实际输出还包含进程编号，编号随运行变化：

| 已提交的步骤 | 修订轮次 | 交接之后 |
| --- | --- | --- |
| 起草 | 0 | 等待校验，草稿缺少 Risks |
| 校验 | 0 | 保存具体反馈，回到起草，返工数变成 1 |
| 再次起草 | 1 | 等待校验，新草稿补上 Risks |
| 再次校验 | 1 | 当前草稿通过，等待定稿 |
| 定稿 | 1 | 报告与完成状态一起保存 |

为什么历史里只有五条，但 `claim_count` 是六？因为 Bob 那次也领取并执行了工作，却没提交结果。**步骤历史记录的是被账本接受的结果，不是所有运行尝试的完整日志。** 如果要审计所有启动、异常和网络调用，还需要 Stage 10 所讲的事件与追踪记录，不能把这五条历史冒充完整监控。

自动演示的外层程序使用临时目录，全部展示结束后会清理它。需要保留报告来手动实验时，用前面的 `worker.py` 命令。还可以在一个新的任务上执行：

```bash
python stages/13-long-horizon-harness/code/worker.py work --db report.db --task-id report-001 --crash after-compute --lease-seconds 2
```

这条命令只允许对离线任务注入故障，预期返回非零退出码。等租约到期再执行普通 `work`，就能观察未提交的步骤被重新执行。若刚才手动实验的任务已经完成，请先用新编号创建任务；已完成的报告不会因为再运行一次命令就被重新领取。

还有一个边界值得强调：数据库是记录，不是自动接班的人。`worker.py work` 每次只做一步；命令结束后，不会有隐藏的后台进程继续工作。演示是由外层程序启动后续 Worker。实际应用同样需要调度者或操作者继续发起领取，持久化本身并不保证任务最终有人来执行。

## 9. 交付的是报告，不是旧工作台上的一个文件名

报告通过检查后，还剩最后一个容易掉坑的地方。假如账本只保存 `"artifact": "/tmp/alice/report.md"`，Alice 的临时目录一清理，这个路径就只是一个非常有历史感的字符串。上一章的工作台可以被销毁，准备交付的产物却必须有明确的保存位置和生命周期。

本章报告很小，因此选择把最终 Markdown 正文放在同一个 SQLite 数据库的 `artifacts` 表中。`commit_step()` 在保存定稿结果的同一事务里保存正文与 SHA-256 摘要，再把任务标为完成。进度中留下的只是引用：

```python
progress["artifact_ref"] = f"sqlite:artifacts/{task.task_id}"
```

这个字符串是本章的内部引用约定，不是可以直接用浏览器访问的网址。读取产物时，账本按任务编号查表，并核对内容摘要。这样，新的进程即使完全没有旧 Workspace，也能取回正式报告；任务要求和当前草稿同样可以从账本读回，重新写入新工作区。恢复会话依赖这些具体材料，而不是“请继续”的一句话。

完成手动实验的全部步骤后，可以导出文档：

```bash
python stages/13-long-horizon-harness/code/worker.py export --db report.db --task-id report-001 --output report-final.md
```

目标路径由操作者给出，不接受模型返回的任意保存位置；文件已存在时拒绝覆盖。数据库中的正文仍然保留，因此导出失败不等于任务结果丢失。这个额外文件是一份可以重新导出的副本，不是恢复必须依赖的唯一文件。

如果产物大到不适合数据库，需要独立的持久化文件或对象存储。这时应先完成上传并确认内容，再提交稳定引用，不能声称两个存储之间自动拥有一笔事务。未被引用的上传如何清理、引用过期如何处理、谁有权下载，都需要明确规则。本文的小型报告把正文保存在同库中，正是为了把已经实现的原子边界讲清楚，而不是假装已经写好通用文件存储平台。

## 10. 能恢复，不等于外部动作只发生一次

目前我们恢复的是起草和检查。重新计算一次草稿最多浪费时间，换成模型请求还可能多花一次调用费用。但如果某一步变成“把报告邮件发给主管”，情况就不同了：邮件已经发出去，进程还没把成功写入账本就退出。接手者看不到成功记录，再发一次，主管就会收到两封。

SQLite 只能原子地处理它自己的写入，不能撤回一封已发出去的邮件；租约 Token 也只能约束本账本接受谁的结果，不会自动让邮件服务拒绝旧 Worker。因此本章既不保证所有函数只运行一次，也不保证外部副作用恰好一次。前面的演示甚至故意让校验运行两次，只有第二次结果被接受。

真正发送退款、邮件等操作时，要回到 Stage 06、09 的边界：外部服务支持幂等键时，按同一个业务动作使用稳定键，并检查相同键是否绑定相同参数；不支持时，需要完成查询、对账、人工介入或适当的补偿。**一次领取的 Token 不能当作这个稳定键**，因为恢复后的 Token 会变化，而我们正是要识别“这是同一个业务动作的再次尝试”。

还应先确认操作是否适合重试。网络超时不能证明服务没有执行；验证错误也不会因为机械重复就自然消失。本章对步骤异常不自动宣布返工或成功：异常向外报告，停止续租，账本保留原位置，之后是否重试由新的领取与总额度约束。更精细的错误分类、退避和人工停止策略可以沿用已经学过的可靠性机制，但不能把它们说成此处已经全部实现。

## 11. 换成 DeepSeek：换的是起草与校验，不是交接规则

现在再接真实模型，问题就清楚多了。我们不要求模型记住上一个进程的人生经历，而是为每次调用重新准备任务要求、允许使用的事实、已有草稿和具体反馈。这正好承接 Stage 07 的上下文选择：账本保存的内容很多，模型只看到当前步骤需要的部分。

[`code/deepseek_long_horizon.py`](code/deepseek_long_horizon.py) 中，起草请求的业务输入是这样组织的：

```python
payload = {
    "request": inputs["request"],
    "facts": inputs["facts"],
    "sections": inputs["sections"],
    "previous_draft": progress.get("draft"),
    "feedback": progress.get("feedback", ""),
}
```

这里没有 `lease_token`，也没有修改预算的入口。新进程重新打开账本后，拿到这些保存的数据就能重新组织请求。模型编号也在创建任务时保存，密钥则从当前进程的环境变量读取，不写进账本。保存模型编号并不等于冻结服务商模型权重，但至少避免了换一个 Worker 就无意改用另一个配置。

调用使用 DeepSeek 官方提供的 OpenAI 兼容 Chat Completions 接口。草稿返回以章节名为键的 JSON 对象，校验返回布尔 `ok` 与文字 `feedback`。请求的核心是：

```python
response = self.client.chat.completions.create(
    model=model,
    messages=[{"role": "system", "content": instructions},
              {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
    response_format={"type": "json_object"},
    max_tokens=1600,
)
```

JSON 模式不是业务校验器。应用仍拒绝空响应、被长度上限截断的响应、非对象结果，以及把 `true` 写成字符串 `"true"` 的审核判断。校验结果只允许两个字段，模型夹带的 `restart_step` 不会被当成控制命令接受。即使模型说通过，本地规则发现缺少 `Risks`，仍然要求补齐。格式和必需章节可以确定性检查；报告是否真正全面、事实解释是否正确，仍可能需要更好的评估或人工审核。不能让一个模型给另一个模型打了勾，就宣布内容绝对可靠。[DeepSeek JSON Output 文档](https://api-docs.deepseek.com/guides/json_mode/)也明确要求提示中说明 JSON 格式，并注意空结果与输出长度。

慢调用的续期由前面讲过的 `LeaseKeeper` 负责。客户端设置 `timeout=45.0`、`max_retries=0`，关闭 SDK 的自动重试，避免实际请求次数藏在一次步骤调用里面。网络超时配置不是杀死整个函数的硬时限，120 秒步骤时限也仍是协作式约束；失去资格后返回的结果会被丢弃，而已经产生的请求费用不能撤销。

安装这一条在线路径所需的依赖：

```bash
python -m pip install -r stages/13-long-horizon-harness/code/requirements.txt
```

Linux / macOS 的 Bash 或 Zsh 中设置：

```bash
export DEEPSEEK_API_KEY="your_key_here"
export DEEPSEEK_MODEL="your_available_model_id"
```

Windows PowerShell 的对应写法是：

```powershell
$env:DEEPSEEK_API_KEY="your_key_here"
$env:DEEPSEEK_MODEL="your_available_model_id"
```

Windows CMD 则使用 `set "DEEPSEEK_API_KEY=your_key_here"` 和 `set "DEEPSEEK_MODEL=your_available_model_id"`。模型编号应从自己的账号与[当前官方文档](https://api-docs.deepseek.com/)确认，不把占位文本原样当作模型名发送。

接着创建一份独立的在线任务，每次执行一个步骤：

```bash
python stages/13-long-horizon-harness/code/deepseek_long_horizon.py create --db online-report.db --task-id live-001
python stages/13-long-horizon-harness/code/deepseek_long_horizon.py work --db online-report.db --task-id live-001
python stages/13-long-horizon-harness/code/deepseek_long_horizon.py inspect --db online-report.db --task-id live-001
```

重复执行 `work`，直到观察到 `completed` 或 `failed`；不要每次重新 `create`。可以在步骤之间退出并换一个终端，只要数据库路径相同，并重新提供密钥即可。新 Worker 根据保存的任务类型选择在线步骤，模型配置也从原任务读回。在线结果不保证恰好返工一次：可能首次通过，也可能在返工额度内仍然失败。失败信息和历史留在数据库中，便于检查。真实请求需要网络和可用额度；离线检查不会发起这些付费调用。

从编排角度看，这仍是固定的“起草—检查—定稿”工作流，模型在步骤内参与写作和判断。长任务并不强制采用完全自主的规划；一个步骤也可以容纳前面学过的有界 Agent 循环。持久化和交接保障服务于业务流程，不会因为外围叫作 Harness，就让普通函数自动变成 Agent。

## 12. 用故障位置检验自己是不是真的懂了

回头看小林的任务，最重要的变化并不是多了几个类。开始时，所有希望都寄托在一个进程持续活着；现在，只要数据库仍可访问，接手者可以区分“已经提交的工作”和“尚无可信结果的工作”，并通过新的执行资格继续推进。

可以用三个问题检查理解。第一，草稿提交以后、终端还没打印成功就退出，为什么下一步仍然是校验？因为打印不是完成条件，事务提交才是。第二，同名 Worker 接手以后，旧进程回来为什么仍被拒绝？因为资格绑定这次领取的 Token，而不是只认名字。第三，数据库里有五条结果历史，为什么不代表函数只运行了五次？因为崩溃前尚未提交的那次计算，不在已接受结果中。

运行边界检查：

```bash
python stages/13-long-horizon-harness/code/checks.py
```

除了正常交付，检查还会真的结束子进程，并在交接事务中途触发退出或数据库异常，确认不会出现“历史写进去了、进度却只更新一半”。并发领取、同名旧凭证、到期后提交、后台续租、续租失败、不同返工轮次、领取额度、草稿被改动后的定稿拒绝，以及伪客户端的模型输出校验，也分别被检查。这里验证的是执行规则，不是给在线模型的报告质量背书。

最后把适用范围收紧。本章的 SQLite 账本面向同一台主机上的可信进程，不提供多租户身份认证、跨机器调度、高可用存储或外部副作用的恰好一次执行。工作流版本随任务保存，Worker 不认识这个版本就拒绝接手；改变步骤顺序或含义时，应显式迁移或使用新版本，不能让旧 `step_index` 悄悄指向另一件事。数据库结构同样带版本检查，旧结构会报错而不是自动清空；做新实验应使用新的数据库路径，已有任务的迁移需要单独设计。

真实长时程 Agent 还可能需要恢复代码版本、重建环境、重新验证已有产物，以及选择下一段可完成的目标。[Anthropic 关于长时程 Agent 的实践](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)讨论了这些更广的运行支撑。本章先把其中的交接与恢复做实：保存可继续的事实，在边界处验收结果，而不是无限续写对话。

当一份报告可以解释清楚“谁在做、做到哪、为什么返工、交付的是什么”，把这些机制带进业务就有了依据。[下一章](../14-capstone-enterprise-agent/README.zh-CN.md)会回到客服 Agent，组合那个业务真正需要的能力。
