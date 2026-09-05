# Stage 12：给 Agent 一张工作台，但别顺手把整台电脑钥匙也给它——Workspace 与 Sandbox

> Language: [English](README.md) | **简体中文**

Stage 11 结束时，我们已经能让多个 Agent 分工。但真实任务很快会从“大家聊一聊”变成：把文件改一下、生成报告、运行测试、执行脚本、把结果保存成 Artifact。Stage 08 的 Skill 甚至允许目录里带 Script。

到这里，一个不能再拖的问题出现了：

> **Agent 如果真的能读写文件、运行程序，它究竟能碰到这台机器的多少东西？**

最危险的答案是：“反正都是 Python，直接 `subprocess.run()` 吧。”

这就像给实习生一张临时办公桌，然后顺手把机房、财务室和 CEO 抽屉的钥匙串一起挂在桌角。

Stage 12 要做两件事。第一，建立 **Workspace**：让一次 Run 有明确的文件边界和 Artifact 区域。第二，建立一个**受限 Command Runner**，用它讨论执行目录、可执行程序、环境变量、Timeout 和输出上限。

但必须先说清楚：

> **本章的标准库 Subprocess Runner 不是安全 Sandbox。**

它是用来理解 Sandbox 需要哪些边界，而不是用几行 Python 宣布自己已经隔离了恶意代码。

---

## 1. 为什么 Agent 需要 Workspace？

普通聊天程序的主要状态可能都在 Message 里。长一点的 Agent 任务却经常有输入文件、中间草稿、下载资料、生成代码、测试结果和最终 Artifact。

如果所有东西都散在当前进程工作目录，很快就回答不了：哪些文件属于这次 Run？下一个 Run 能不能看到它们？用户能下载哪一个？Agent 可以修改仓库里的什么？清理时哪些可以删？

Workspace 的第一层价值，就是把“一次任务的工作区”变成明确对象。

---

## 2. 一次 Run 一个 Root，是一个很好的起点

本章创建：

```python
workspace = AgentWorkspace.create(
    "/tmp/runs/run-001"
)
```

之后所有文件都相对这个 Root：

```text
run-001/
├── input.txt
├── work/
│   └── check.py
└── artifacts/
    └── result.txt
```

这不代表所有生产系统都必须用本地目录。Workspace 完全可以映射到对象存储、远程 Sandbox 或持久卷。

但抽象应该先存在：

> **Agent 操作的是自己的 Workspace，不是“这台机器随便哪个 Path”。**

---

## 3. Path Traversal：`../` 是一只很小但很有战斗力的字符串

假设你提供：

```python
workspace.read_text(path)
```

如果 `path` 可以是 `../../../../etc/passwd`，那所谓 Workspace Root 就只是墙上贴的一张“请勿越界”海报。

所以本章所有路径都经过：

```python
target = (root / relative).resolve()
```

然后检查真实目标是否仍在 Root 内。绝对路径也直接拒绝。

```text
notes/a.txt
    -> allowed

../secret.txt
    -> rejected

/etc/passwd
    -> rejected
```

这叫 Path Confinement。它不是整个 Sandbox，但它是文件边界最基本的一层。

---

## 4. Symlink 为什么让路径问题更有意思？

你可能会想：“我禁止 `..` 不就行了？”

不够。

因为 Workspace 里可以出现 Symlink：

```text
workspace/link -> /etc
```

然后用户读取 `link/passwd`，字符串里根本没有 `..`。

这也是为什么本章先 `resolve()`，再检查真实目标是否仍在 Root 内。文件系统边界最好基于 Canonical Path，而不是字符串长相。

---

## 5. Artifact 和临时工作文件最好不是一个概念

Agent 做任务时可能产生一大堆中间文件，例如下载页、Scratch Script、Notes 和 Debug JSON。用户真正关心的也许只有 `artifacts/report.pdf`。

所以推荐在 Workspace 内至少区分：

```text
work/
artifacts/
```

`work/` 是 Agent 干活的地方，`artifacts/` 是准备交付、保存或导出的结果。

这和 Stage 14 的长时任务会再次连接：Artifact 应该能脱离模型 Context 和当前进程继续存在。

---

## 6. 现在才轮到 Command Runner

文件边界有了以后，我们才谈执行。

本章 Runner 接受：

```python
runner.run(
    [python, "work/check.py"],
    timeout_seconds=2,
)
```

注意是参数数组，不是 `shell=True`。

`["python", "check.py"]` 和 `"python check.py; rm -rf ..."` 属于完全不同的解析边界。默认 `shell=False` 可以少一层 Shell 字符串解释。

这并不意味着命令因此“安全”，但少给一个解释器通常是好事。

---

## 7. Executable Allowlist：不是所有程序都值得提供

本章创建 Runner 时声明：

```python
CommandRunner(
    workspace,
    allowed_executables={"python3"},
)
```

如果模型尝试 `sh`、`curl`、`ssh`，不在 Allowlist 就拒绝。

这和 Stage 09 的 Tool Permission 是同一个思路：

```text
机器上安装了
!=
Agent 有权执行
```

当然，允许 Python 本身已经是一项很强的能力。Python 可以读文件、开网络、启动子进程，所以 Executable Allowlist 只是能力面的一层，不是完整隔离。

---

## 8. `cwd` 很重要

Runner 强制：

```python
cwd=workspace.root
```

这样 Script 使用相对路径时自然落在当前 Run Workspace。

如果不固定 CWD，同一份 Script 在不同启动位置可能读写完全不同的文件。可重复执行需要明确工作目录。

---

## 9. 环境变量不要默认整包继承

你的服务进程可能有：

```text
DATABASE_URL
OPENAI_API_KEY
GITHUB_TOKEN
AWS_SECRET_ACCESS_KEY
```

如果 `subprocess.run()` 默认继承全部 Environment，那么刚获得脚本执行能力的 Agent 子进程可能顺便获得服务进程所有 Credential。

本章 Runner 从很小的 Environment 开始：

```python
env = {
    "PATH": ...,
    "PYTHONIOENCODING": "utf-8",
}
```

需要额外值时显式传入。

原则是：

> **Credential 不是“运行环境的一部分”，而是需要明确授予的 Capability。**

---

## 10. Timeout 这次比 Stage 09 更强，但仍不是完美终止

Stage 09 的 Python Handler 使用 Cooperative Deadline，因为在线程里很难安全杀死任意工作。

Stage 12 进入了 Subprocess 边界。`subprocess.run(..., timeout=...)` 可以在超时后终止直接子进程，这比“我不等线程了”更强。

但仍然别宣布“现在所有子孙进程都会被完美清理”。复杂 Process Tree、Daemon、外部服务副作用仍然需要更系统的 Process Group、Container 或 Sandbox 生命周期管理。

准确说法是：

> **独立进程给了我们比普通函数更清晰的终止边界，但还不是完整安全隔离。**

---

## 11. Output 也需要 Budget

一个程序可以打印一千万个字符。如果 Runtime 把完整 stdout 塞回模型 Context，你刚刚用一行代码创造了自己的 Context DDoS。

所以 Runner 有：

```python
max_output_chars
```

超出后追加 `...[truncated]`。

这和 Stage 07 的 Context Budget 是同一类问题：

> **任何会进入模型或持久化系统的数据流，都需要上限。**

---

## 12. Workspace 不是 Security Sandbox

这是本章最需要严谨的一点。

我们的 Runner 做了 Path Confinement、Executable Allowlist、Controlled CWD、Reduced Environment、Timeout、Output Limit 和 `shell=False`。

很好。

但允许执行 Python 时，代码仍然可能 `import socket`、`import subprocess` 或直接调用操作系统能力。如果 OS 权限允许，它仍然可能访问 Workspace 外的资源。

所以：

```text
bounded subprocess wrapper
!=
security sandbox
```

真正更强的隔离通常还需要独立 OS 用户、Namespace、Container/VM、Filesystem Mount Policy、Network Policy、Syscall Controls、Resource Limits 和 Credential Isolation。

具体技术会因部署环境变化。这章的价值是让你知道一个 Sandbox 需要回答哪些问题，而不是背某个云产品名字。

---

## 13. Container 也不是“完美 Sandbox”同义词

Container 能提供很有价值的 Filesystem View、Process Namespace、Resource Limit 和 Network Configuration。

但安全强度取决于配置、Runtime、Kernel、Mount、Capability 和 Credential。

例如把 `/var/run/docker.sock` 直接挂进 Container，很多“隔离感”会立刻变得很哲学。

所以：

> **Container 是隔离工具，不是自动安全证明。**

同样的原则也适用于托管 Sandbox 产品：要看它真正隔离什么。

---

## 14. Network 应该是显式策略

有些 Agent 任务需要网络，有些完全不需要。

如果一个只做本地代码格式检查的 Script 默认可以访问互联网，攻击面被无意义地放大。

真正 Sandbox 常会有 `network = off` 或 Destination Allowlist。

本章标准库 Runner 没有能力可靠实现 OS 级 Network Isolation，所以不会伪造一个 `network=False` 参数然后假装它真的管用了。

这就是技术严谨性：

> 没实现的隔离，不要写成配置项 cosplay。

---

## 15. Skill Script 到这里才终于有执行位置

Stage 08 我们故意没有执行 Skill 中的任意 Script。

现在可以把关系接起来：

```text
Skill
    ↓ procedure says run script
Host Policy
    ↓ decides whether script is allowed
Workspace
    ↓ provides bounded files
Runner / Sandbox
    ↓ executes under environment policy
Artifact
    ↓ result
```

Skill 自己仍然不拥有执行权。它只是程序性指导和资源包。

---

## 16. Workspace 和 Durable State 也不是一回事

一个临时 Workspace 可以随着 Compute 消失。Checkpoint 和 Task Ledger 则应该保存在 Durable Store。

所以：

```text
Workspace
    -> current compute's working files

Checkpoint
    -> resumable execution state

Artifact Store
    -> durable outputs worth keeping
```

有些系统会把 Workspace 本身做成持久卷，那只是实现选择，语义仍然值得分开。

Stage 14 会处理“Worker 消失以后怎么根据 Durable State 重建工作环境”。

---

## 17. Cleanup 也是生命周期的一部分

创建临时 Workspace 很容易，清理很容易被忘。

如果每个 Run 都留下下载文件、依赖缓存、模型生成脚本和大日志，磁盘迟早会用一种非常直接的方式提醒你生命周期设计不完整。

所以 Workspace 应该有：

```text
create
use
export artifacts
cleanup
```

哪些 Artifact 需要长期保留，应该由应用明确决定。

---

## 18. 运行完整代码

```bash
python stages/12-agent-workspace-sandbox/code/demo.py
python stages/12-agent-workspace-sandbox/code/checks.py
```

Demo 会在临时 Workspace 里创建 Input 和 Script，用受限 Runner 执行，再生成 `artifacts/result.txt`。

检查覆盖相对路径、`../` Escape、Absolute Path、Executable Allowlist、CWD、Timeout、Output Truncation，以及服务进程的额外环境变量不会自动传进子进程。

---

## 19. 下一章为什么是 Production Service？

到这里，我们的 Agent 已经不只是 Notebook Demo。它有 Durable State、External Tools、Memory、Context、Skills、Guardrails、Eval、Multi-Agent、Workspace 和 Subprocess。

真正部署时，一个更现实的问题出现了：

> **多个用户同时发请求怎么办？**

谁创建 Run？Request、Thread、Run、User、Tenant 怎么区分？任务太长不能一直占着 HTTP 连接怎么办？如何 Backpressure？进程重启以后 Run Status 去哪找？服务什么时候算 Ready？

所以下一章 Stage 13，我们把 Agent 从“程序”变成“服务”。真正麻烦，也从这里开始变得很像普通分布式系统工程。
