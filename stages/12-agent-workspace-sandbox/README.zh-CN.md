# Stage 12：给 Agent 一张工作台，但别顺手把整台电脑钥匙也给它——Workspace 与 Sandbox

> Language: [English](README.md) | **简体中文**

Stage 11 解决了多个 Agent 中“谁做什么”。真实任务很快会变成读取资料、修改文件、生成报告、运行测试和执行 Skill Script。此时问题变成：

> **Agent 在做这些事时，究竟能碰到机器上的哪些文件、程序、网络和凭证？**

本章先建立明确的 **Workspace**，再建立受限 Command Runner，最后严格区分“减少意外操作的本地包装器”和“可以运行不可信代码的 Security Sandbox”。

```text
Host chooses a Workspace root
    ↓
Agent reads and writes bounded workspace paths
    ↓
Host chooses registered command aliases
    ↓
Runner bounds cwd, environment, duration, and returned output
    ↓
Artifact is exported; temporary work is cleaned up
```

本章代码只使用标准库。若要逐段复制运行，先执行 `cd stages/12-agent-workspace-sandbox/code`；完整示例命令放在对应知识点后。

---

## 1. 从“谁做”走到“在哪里做”：Workspace 的文件边界

一个短聊天的主要状态在 Message 中。长任务还会有输入文件、下载资料、中间脚本、测试输出和最终报告。若它们散落在服务当前目录，就很难回答：哪些文件属于这次 Run？下个 Run 能否看见？用户可以下载哪一个？清理时删什么？

Workspace 把“一次 Run 的文件工作区”变成明确对象。`root` 是 Host 创建的目录；Agent 只能请求相对于它的路径：

```text
run-001/
├── input.txt
├── work/
│   └── check.py
└── artifacts/
    └── result.txt
```

`work/` 存放中间草稿、下载和测试脚本；`artifacts/` 存放准备交付或导出的结果。这不是目录名的魔法，而是应用的语义约定：只有 Host 明确导出的 Artifact 才应离开本次 Run。

下面代码在 Host 已决定根目录后创建 Workspace。`Path` 是 Python 表示文件路径的对象；根目录不能由模型给出任意绝对路径：

```python
from pathlib import Path
import tempfile

from workspace import AgentWorkspace

with tempfile.TemporaryDirectory() as tmp:
    workspace = AgentWorkspace.create(Path(tmp) / "run-001")
    workspace.write_text("input.txt", "tiny agent workspace")
    workspace.write_text("work/check.py", "print('checked')\n")
    workspace.write_text("artifacts/result.txt", "approved summary\n")

    print(workspace.list_files())
```

`TemporaryDirectory` 会在 `with` 代码块结束时删除这个教学用 Workspace。真实服务可以改用持久化目录或隔离环境，但也应明确何时导出 Artifact、何时清理临时文件。

---

## 2. 文件边界不是字符串检查：Path Traversal 与 Symlink

如果 Agent 可以请求 `../../secret.txt`，Workspace Root 只是墙上的“请勿越界”标志。这个技巧叫 **Path Traversal**：`..` 表示父目录，连续使用能逐层走出工作区。

本章的 `resolve()` 先拒绝绝对路径，再把相对路径与 Root 合并并调用 `Path.resolve()`；`resolve()` 得到的是文件系统实际指向的规范路径。最后检查该路径仍在 Root 内：

```python
from pathlib import Path
import tempfile

from workspace import AgentWorkspace, WorkspaceEscapeError

with tempfile.TemporaryDirectory() as tmp:
    workspace = AgentWorkspace.create(Path(tmp) / "run-001")
    assert workspace.resolve("notes/a.txt").is_relative_to(workspace.root)

    try:
        workspace.write_text("../secret.txt", "no")
    except WorkspaceEscapeError:
        print("path escape rejected")
```

为什么不只检查字符串里有没有 `..`？因为 **Symlink（符号链接）** 可以让一个看似普通的工作区路径指向外部文件：

```text
workspace/outside-link  ->  /somewhere/private.txt
```

读取 `outside-link` 时路径字符串没有 `..`，真实目标却在外面。因此代码检查规范路径，而不是字符串外观。测试会在系统允许创建 Symlink 时验证这一点；某些 Windows 环境没有创建 Symlink 的权限，测试会标记为跳过，而不是把权限限制误报成实现成功。

这份本地 Path Confinement 适合防止普通路径逃逸，却不是对抗同机恶意进程的完整方案：另一个进程仍可能在“检查路径”和“打开文件”之间篡改文件系统。运行不可信代码时，应依赖后文的 OS/虚拟化隔离，而不是把这段路径检查当成全部防线。

---

## 3. Workspace、Artifact、Checkpoint 与 Cleanup 是四件事

这些概念都和“保存东西”有关，却解决不同问题：

| 对象 | 保存什么 | 生命周期 |
| --- | --- | --- |
| Workspace | 当前计算的输入、中间文件和临时脚本 | 通常随 Run 结束清理 |
| Artifact | 值得交付的报告、补丁、测试结果 | 应由应用明确导出和保留 |
| Checkpoint | 继续执行所需的状态 | Stage 06 的 Durable Store |
| Task Ledger | Run 状态、重试和审计记录 | 由服务长期管理 |

把 Workspace 做成持久卷是可能的实现选择，但不要因此混淆语义：Worker 消失后，Checkpoint 告诉系统如何恢复；Artifact 是用户或后续流程要获取的结果；临时工作文件大多数应清理。

完整生命周期是：

```text
create workspace
    ↓
write / execute / inspect
    ↓
export selected artifacts
    ↓
cleanup temporary workspace
```

如果每次 Run 都留下下载文件、缓存、生成脚本和大日志，磁盘会替你发现生命周期设计缺了一步。

---

## 4. 执行命令时，先把“能运行什么”交回 Host

文件能写到哪里解决以后，下一步才是“能执行什么”。不要把一段由模型或脚本拼出的命令字符串直接交给 shell：

```python
# 不要把未验证内容这样交给 shell：它会重新解释整段字符串。
import subprocess

untrusted_argument = "work/check.py && echo unexpected-shell-command"
subprocess.run(f"python {untrusted_argument}", shell=True, check=False)
```

`shell=True` 会让 shell 解释空格、引号、重定向和 `&&` 等语法；如果命令中混入了未验证的内容，边界很难判断。本章的 Runner 接受一个参数列表，并固定 `shell=False`：

```python
from pathlib import Path
import sys
import tempfile

from runner import CommandRunner
from workspace import AgentWorkspace

with tempfile.TemporaryDirectory() as tmp:
    workspace = AgentWorkspace.create(Path(tmp) / "demo-run")
    workspace.write_text("work/check.py", "print('checked')\n")

    runner = CommandRunner(
        workspace,
        allowed_executables={"python": sys.executable},
    )
    result = runner.run(["python", "work/check.py"], timeout_seconds=2)
    print(result.stdout)
```

这里的 `"python"` 不是让模型在 `PATH` 中自行寻找的任意程序，而是 Host 在启动时注册的**命令别名**。Runner 会将它替换为 `sys.executable`，也就是当前 Python 解释器的确定路径。模型即使在 Workspace 中写了一个叫 `python` 的文件，或者请求 `./python`，也不会匹配这个别名。

这是一种很小但很实用的能力设计：Host 提供哪些别名，调用方就只能请求哪些程序；它不能借“命令参数”偷偷改掉可执行文件本身。

Runner 还固定 `cwd=workspace.root`。因此 `work/check.py` 是相对于本次 Run 的工作目录，而不是相对于启动服务的项目根目录。这样既让产物集中，也减少了脚本误读宿主机文件的机会。

## 5. 命令能启动以后，还要限制运行时资源

允许一个已知解释器，并不等于可以把宿主机的完整环境交给它。本章只传入最小环境：`PATH` 和 `PYTHONIOENCODING`，再由 Host 按需通过 `extra_env` 传入额外变量。数据库密码、云凭证和部署令牌不应因为“子进程也许用得到”而默认继承。

三个运行时限制分别解决不同问题：

| 限制 | Runner 的做法 | 它防止什么 |
| --- | --- | --- |
| 超时 | 到达 `timeout_seconds` 后终止直接子进程 | 卡住的命令无限占用 Worker |
| 输出预算 | 同时持续读取 stdout、stderr，只保留各流前 `max_output_chars` 个字符 | 大量日志撑满父进程内存 |
| 输入 | 子进程的 stdin 连接到 `DEVNULL` | 脚本等待人工输入，导致 Run 悬挂 |

“持续读取”很关键。若等子进程结束后才执行 `output[:4000]`，虽然最后展示的文字短了，Python 进程在此之前仍可能已经把几百 MB 日志放进内存。Runner 为 stdout 和 stderr 分别启动读取线程：超过预算后继续丢弃后续内容，避免管道写满，同时在结果末尾标记 `...[truncated]`。

这仍有边界：超时只终止直接启动的进程，不保证清理它派生出的全部子进程，也不能撤销已经写出的文件或已经发出的网络请求。更强的进程组控制和资源配额应由后面的隔离运行环境提供。

此时可以运行完整的本地演示：

```bash
python stages/12-agent-workspace-sandbox/code/demo.py
```

它写入一个固定的教学脚本、通过 `python` 别名运行它，再显式导出一个结果文件。这里没有让模型生成任意代码；该示例关注的是 Host 如何执行已经允许的命令。

---

## 6. Workspace 和 Runner 不是安全 Sandbox

到这里我们已经有了路径检查、命令别名、受限环境、超时和输出预算。这些都是防护层，却不足以把不可信代码安全地放在主机上运行。

| 要隔离的对象 | 本章的 Workspace / Runner 能做什么 | 真正 Sandbox 还需要什么 |
| --- | --- | --- |
| 文件 | 限制本章 API 解析的 Workspace 路径 | 独立文件系统或挂载、只读输入、最小权限 |
| 进程 | 固定入口、限制直接子进程的时间 | 容器/虚拟机、进程组、CPU 和内存配额 |
| 网络 | 本章不提供网络策略 | 默认拒绝出网，或只允许明确的目标 |
| 系统调用与身份 | 无法阻止当前用户权限下的任意 Python 代码 | 低权限身份、seccomp 等 OS 级限制 |
| 清理 | 清理 Workspace 文件 | 隔离实例销毁、可审计的资源回收 |

容器常被用于增加这层隔离，但“用了 Docker”本身不是答案。把 Docker socket 挂进容器，或把宿主机目录以可写方式挂载进去，都会重新扩大权限。网络策略也必须由容器、虚拟机或基础设施实际执行；本章的 `CommandRunner` 没有实现它，所以不能声称它已经阻断网络。

运行离线检查可以看到这些已经实现的边界：

```bash
python stages/12-agent-workspace-sandbox/code/checks.py
```

检查包含路径逃逸、绝对路径、符号链接、未注册的可执行文件、受限环境、超时和流式输出截断。某些 Windows 环境没有创建符号链接的权限；在这种环境中，对应测试会跳过，而不会把“无法创建测试条件”误报为安全通过。

## 7. Skill、模型与执行环境如何接起来

Stage 08 的 Skill 可以告诉 Agent 在某类任务中应检查什么、产出什么；它不是执行权限。一个面向代码任务的生产链路应当是：

```text
Skill procedure
    → Host validates requested action
    → isolated workspace / sandbox executes approved command
    → Host validates and exports selected artifact
```

因此本章不提供“把 DeepSeek 生成的一段任意 Python 直接交给本机 Runner 执行”的示例。那会绕过本节刚说明的隔离边界，也会把 Stage 09 的策略检查变成形式。真实接入 LLM 时，应先在 Sandbox 外由 Host 完成工具选择、参数校验和审批；只有明确允许的命令才进入**已经隔离的**执行环境。模型提出方案，Host 决定是否执行、在哪里执行，以及哪些产物可以离开 Workspace。

## 8. 下一章：把这些边界放进可运行的服务

现在我们有了单个 Run 的文件、进程与产物边界。下一个问题是：当前 Worker 或进程消失后，任务怎样继续？下一章会建立这条恢复链路：[Stage 13：Long-Horizon Harness](../13-long-horizon-harness/README.zh-CN.md)。
