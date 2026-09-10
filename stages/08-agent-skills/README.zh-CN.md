# Stage 08：需要时再加载操作手册——Agent Skills

> Language: [English](README.md) | **简体中文**

[Stage 07：Context Engineering](../07-context-engineering/README.zh-CN.md) 解决了一个问题：
模型这一轮应该看到什么，而不是把系统拥有的所有信息都塞进 Context。

可复用的操作流程也会造成同样的问题。发布检查、代码审查、数据库迁移和事故复盘都可能
有自己的操作手册。若把所有手册永久写进 System Prompt，每一种任务都会为其他所有流程
支付 token 成本，也会让模型在无关说明中分散注意力。

这一章采用一个更自然的做法：

> **先告诉 Agent 有哪些可用流程；只有任务真正需要某个流程时，才加载它的完整说明。**

全文都使用同一个 `release-check` Skill。读完后，你应当能回答：它解决什么问题、何时
加载、谁决定能否执行，以及如何把它接入后续 Agent Runtime。

---

## 1. Skill 给 Agent 增加了什么

Skill 是一份可复用的**操作指导**。它描述面对某类任务应该怎样工作，本身不执行任务。

例如发布检查可以指导 Agent：

```text
确认目标版本和分支
运行确定性的测试
检查生成文件和临时文件
需要时读取发布检查表
发现失败后先报告，再建议下一步
```

它和前面章节的概念分工不同：

| 组件 | 它主要回答的问题 |
| --- | --- |
| Workflow | 程序应运行怎样的固定控制流？ |
| Tool | 系统能执行什么动作？ |
| MCP | 远程能力和资源如何通过协议暴露？ |
| Memory | 哪些经过选择的信息应跨时间保留？ |
| Context Engineering | 这一轮模型应接收什么？ |
| Skill | 面对这类任务，应遵循什么可复用流程？ |

如果步骤和分支完全确定，应该优先写成 Workflow。Skill 适用于“方法相对稳定，但具体
执行需要结合任务判断”的情况。Skill 也可以要求 Agent 在高影响节点进入应用程序拥有的
Workflow；它不会替代这个 Workflow。

---

## 2. Skill 是一个小型、可版本管理的包

本章采用以 `SKILL.md` 为入口的目录：

```text
release-check/
├── SKILL.md
└── references/
    └── checklist.md
```

`SKILL.md` 是必需的入口文件。一个实际的 Skill 包还可以在它旁边放置可选材料：

```text
release-check/
├── SKILL.md                 必需：身份信息和主要流程
├── references/              可选：按需读取的详细文档
├── scripts/                 可选：确定性的辅助脚本
└── assets/                  可选：模板、示例或其他任务文件
```

先约定这里几个术语的含义：

- **Frontmatter** 是 `SKILL.md` 开头、两行 `---` 之间的简短 YAML 风格头部。
- **Discovery（发现）** 会扫描 Skill 目录并读取这个头部，得到供 Router 判断的小型 Metadata
  列表。
- **Activation（激活）** 才会读取某个被选中 Skill 的 Markdown 正文。
- **Resource（资源）** 是这个 Skill 包目录中的额外文件。
- **Host（宿主应用）** 是拥有 Agent 的应用程序。它决定哪些 Tool、脚本、文件、凭据和审批
  在当前任务中真正可用。

这些部分的职责和加载时机不同：

| 部分 | 放什么 | 什么时候读取或使用 |
| --- | --- | --- |
| `SKILL.md` 中的 Frontmatter | 名称和描述 | Discovery |
| `SKILL.md` 中的 Markdown 正文 | 目标、步骤和判断点 | Activation |
| `references/` | 长检查表、政策和边缘情况 | 某一步确实需要时 |
| `scripts/` | 可重复的确定性工作 | Host 允许执行后 |
| `assets/` | 模板、示例文件或媒体 | 任务需要该产物时 |

本章教学 Skill 只有 Reference，因为这已经足够演示生命周期。没有 `scripts/` 或 `assets/`
不代表 Skill 不完整；它们只是让主流程保持聚焦的可选组织方式。

下面是完整的教学 Skill：

```markdown
---
name: release-check
description: Use when preparing a software release and you need a repeatable pre-release verification procedure.
---

# Release Check

Before proposing a release:

1. Identify the target version and branch.
2. Run the project's deterministic tests.
3. Check that generated or temporary files are not included.
4. Review the release-specific checklist in `references/checklist.md`.
5. Report failures before suggesting a release action.

Do not publish or deploy anything merely because this skill was activated. The host application still owns execution and approval.
```

主流程在第 4 步引用了独立 Resource，而不是把所有发布细节都塞进正文。下面就是实际的
[`references/checklist.md`](code/skills/release-check/references/checklist.md)：

```markdown
# Release Checklist

- Version number is intentional.
- Tests relevant to the changed area pass.
- Documentation links resolve.
- No credentials, caches, or temporary artifacts are included.
- High-impact deployment actions require the application's normal approval path.
```

这份检查表只会在 Agent 走到第 4 步后才有用。把它独立存放，意味着一个仅做 Discovery 的
任务无需读取它。

Frontmatter 让系统在没有加载完整正文前就能认识这个 Skill：

- `name` 是稳定标识，会用于代码、日志和资源路径。
- `description` 同时说明“它做什么”和“什么时候应该选它”。

目录名与 `name` 应保持一致。本例目录叫 `release-check`，Frontmatter 里的 `name` 也叫
`release-check`。这会让资源路径、缓存和运行记录都有唯一而稳定的身份。

---

## 3. Progressive Disclosure：Skills 为什么能改善 Context

假设仓库里有一百个 Skill，每个都有很长的 Instructions。若启动时把全部正文读进来，
我们又回到了 Stage 07 想解决的 Context 膨胀问题。

正确的加载过程分成三层：

```text
所有 Skill 目录
        ↓ discover
name + description
        ↓ activate 匹配的 Skill
完整 SKILL.md Instructions
        ↓ 在某一步真正需要时读取
具体 reference、script 或 asset
```

Discovery 像菜单：先知道有哪些流程。Activation 像打开一份菜谱：只读被选中的步骤。
Resource 则是菜谱中的附录：走到相关步骤时才读取细节。

这不是只画在图里的想法。[`skills.py`](code/skills.py) 的 `discover()` 调用
`read_frontmatter()`，它逐行读取并在遇到结尾 `---` 时停止，不会调用 `read_text()` 把整个
文件读入。`SkillMetadata` 只有 `name`、`description` 和 `path`；Activation 才会调用
`parse_skill_file()`，返回包含完整正文的 `ActivatedSkill`。代码结构本身保证了“发现”和
“加载”是两件事。

---

## 4. 用一个小 Catalog 看完整生命周期

本章的 Catalog 故意没有模型、向量数据库或框架。先把生命周期看清楚，后续章节再把它
与路由和 Runtime Policy 结合。

下面是一个离线的模拟程序，入口在 [`code/demo.py`](code/demo.py)：

```python
from pathlib import Path

from skills import SkillCatalog


def main() -> None:
    root = Path(__file__).with_name("skills")
    catalog = SkillCatalog(root)

    for skill in catalog.discover():
        print("discovered:", skill.name, "->", skill.description)

    active = catalog.activate("release-check")
    print("\nactivated instructions:\n", active.instructions)

    reference = catalog.read_resource(
        "release-check",
        "references/checklist.md",
    )
    print("\non-demand reference:\n", reference)


if __name__ == "__main__":
    main()
```

按顺序理解这三步：

1. `discover()` 只读取 Metadata，调用方可以先判断哪个 Skill 与任务相关，而不把所有
   操作手册放进 Context。
2. `activate("release-check")` 才读取被选中的 `SKILL.md` 正文。
3. `read_resource(...)` 只在流程走到相应步骤时读取检查表。

Catalog 自身不做语义路由。在真实 Agent 中，Router 或模型可以根据 Discovery 得到的
Metadata 选择 Skill；Catalog 的职责是让这个选择过程轻量、可观察且可验证。可运行的 DeepSeek
示例通过 Tool Call 表达选择：模型请求 `activate_skill(name)`，Host 验证名称后把被选中的
`SKILL.md` 作为 Tool Result 返回。

基于大模型的实现位于 [`deepseek_skills.py`](code/deepseek_skills.py)，下表列出文件中真实存在的函数及其职责：

| 运行时步骤 | 实际代码 |
| --- | --- |
| 通过 Tool Schema 公布 `name` 与 `description` | `build_skill_tool(candidates)` |
| 发送第一次模型请求 | `main()` 中的 `request_completion(..., tools=skill_tools, tool_choice="auto")` |
| 验证模型请求的名称并加载 `SKILL.md` | `activate_requested_skill(...)` |
| 将被选中的 Instructions 放入对话 | `activation_result_message(...)` |
| 提供并验证按需读取 Reference 的能力 | `build_reference_tool(...)` 与 `read_requested_reference(...)` |
| 在 Tool Result 后继续对话 | `main()` 中第二次，以及需要时第三次的 `request_completion(...)` |

所以真实的运行轨迹是：

```text
用户任务
  → 模型可能调用 activate_skill(name)
  → Host 验证名称并返回 SKILL.md
  → 模型可能调用 read_skill_reference(path)
  → Host 验证路径并返回该 Reference
  → 模型写出最终回复
```

关键是顺序：模型先通过 Tool 定义看到简短 Metadata；它只会通过 Tool Result 接收一个被选中的
流程；Host 独立批准每一个外部动作。

[`code/deepseek_skills.py`](code/deepseek_skills.py) 把这条连接落实成了一个可运行的 DeepSeek
示例。它遵循正常的 Tool Calling 对话：

1. 第一次模型回复可以调用 `activate_skill(name)`；Tool Schema 只公开 Discovery 得到的名称
   与描述。
2. Host 验证参数、激活指定 Skill，并以 Tool Result 返回其 Instructions。
3. 若 Instructions 指向 Reference，模型可以调用 `read_skill_reference(path)`；Host 验证后
   只返回该文件。
4. 模型随后生成发布检查建议。示例没有能运行测试、发布或部署的 Tool。

消息顺序遵循官方 [DeepSeek Tool Calls 指南](https://api-docs.deepseek.com/guides/tool_calls/)：先追加
模型的 Tool Call，再追加带相同 `tool_call_id` 的 `tool` 消息，最后让模型继续回复。

默认任务是一次发布请求。可用 `--task "..."` 换成其他任务；与发布无关的任务应使模型返回
普通回复，而不是调用 Skill 激活 Tool。

---

## 5. 细节放在 Resource，读取必须有边界

Skill 正文应该帮助 Agent 决定下一步。只在特定条件下需要的大段细节，应放入 Resource，
而不是让每次 Activation 都携带它。

例如 `references/checklist.md` 对发布检查有用，对数据库迁移任务则完全无关。把它单独
存放，才能保持“Metadata → Instructions → Resource”的按需加载顺序。

读取 Resource 时仍然需要边界。教学 Catalog 会解析请求路径，并拒绝这种试图逃出 Skill
目录的路径：

```text
../../secret.txt
```

下面是 `SkillCatalog` 中真实存在的方法；保留缩进是为了表明它属于类，而不是一个可以单独复制
运行的函数。

```python
    def read_resource(self, skill_name: str, relative_path: str) -> str:
        skill_root = (self.root / skill_name).resolve()
        target = (skill_root / relative_path).resolve()
        if target != skill_root and skill_root not in target.parents:
            raise ValueError("resource path escapes skill directory")
        if not target.is_file():
            raise FileNotFoundError(relative_path)
        return target.read_text(encoding="utf-8")
```

这样 Catalog 不会变成一个任意文件读取器。它还不是完整 Sandbox；文件权限、凭据、进程
隔离和网络访问仍是 Host 的责任。

---

## 6. Skill 指导工作，Host 控制执行

激活发布检查 Skill 不会发布版本。Skill 可以提到某个脚本或 Tool，但那只是“下一步可能
需要什么能力”的说明，不是授权。

```text
Skill procedure
    ↓ 提出下一步
Host / Runtime policy
    ↓ 允许或拒绝能力
Tool 或 script
    ↓ 仅在被允许时执行动作
```

这就是为什么本章 Catalog 只读取资源，不会因为 Skill 目录里出现脚本就执行它。执行环境、
文件和网络权限、凭据、审批与授权都属于 Host。

同一条边界也解释了 Skill 与 MCP 的关系：Skill 可以说明何时需要 GitHub Tool；MCP 可以
通过协议暴露这个 Tool；Host 仍决定当前 Agent 是否真的可以调用它。

Skill 也不是 Memory。Memory 可能保存“用户偏好中文”；Skill 保存的是“如何做发布检查”
这类由团队维护的流程。普通对话不能悄悄改写系统的操作手册。

---

## 7. 如何写出一个好的 Skill

一个好 Skill 不只是一段文本，它有清晰的内部结构：

```text
frontmatter  → 让系统发现并识别这个 Skill
body         → 激活后告诉 Agent 怎样推进任务
resources    → 存放只在部分情形有用的细节
scripts      → 可选地打包确定性的辅助工作
assets       → 可选地打包可复用的任务产物
```

前两项是最小要求。Resource、Script 和 Asset 只有在它们能让流程更清楚或更可复用时才
需要加入。

### Frontmatter：让正确的任务找到这个 Skill

`name` 为这个包提供稳定身份。`description` 是 Discovery 阶段可见的短文本，此时 Agent
尚未加载正文。它必须同时写出任务类型和触发条件。对比：

```text
弱：   Helps with software.
好：   Use when preparing a software release and you need a repeatable pre-release verification procedure.
```

弱的描述没有指出任务，也没有说明何时选它。好的描述让 Router 或模型知道：它用于
*发布前验证*，而不是泛泛的软件问题。

### Body：让下一步足够明确

Markdown 正文只会在 Activation 后读取。它应写清目标、有顺序的动作、真正有意义的判断点，
以及何时需要读取额外 Resource。教学 Skill 的正文因此包含：确认版本、运行测试、检查
产物、读取检查表，以及在建议发布前报告失败。

“认真一点”是质量愿望；“测试失败时，先报告失败，不建议发布”才是一条带判断边界的操作。

### 可选材料：有用，但不会自动获得执行权

很长的发布矩阵适合放进 `references/`，正文只在流程走到该阶段时指向它。未来可以加入
`scripts/verify_release.py` 来封装确定性检查，但 Skill 正文仍应说明它的输入、输出和失败
含义。`assets/` 可以放 Release Notes 模板。无论这些文件是否与 `SKILL.md` 放在一起，
都不会因此自动获得执行权或权限。

本章解析器只处理示例所需的简单标量 Frontmatter 字段。生产 Client 应使用成熟的 YAML
解析器并验证格式，而不是把这个教学解析器扩展成自制 YAML 实现。

---

## 8. 运行本章

离线示例只使用 Python 标准库：

```bash
python stages/08-agent-skills/code/demo.py
python stages/08-agent-skills/code/checks.py
```

观察 Demo 的顺序：先显示 Metadata，再显示完整 Instructions，最后读取按需检查表。检查
覆盖 Metadata-only Discovery、Activation 时加载正文、目录与名称一致性、合法名称，以及
Resource 路径不能逃出 Skill 目录。

若要运行真实模型示例，先安装可选依赖，并设置与前面章节相同的 DeepSeek 环境变量。环境
变量必须设置在运行 Python 的同一个终端中。

Windows 命令提示符（CMD）：

```bat
python -m pip install -r stages/08-agent-skills/code/requirements.txt
set "DEEPSEEK_API_KEY=your_key_here"
set "DEEPSEEK_MODEL=your_available_deepseek_model"
python stages/08-agent-skills/code/deepseek_skills.py
```

PowerShell：

```powershell
python -m pip install -r stages/08-agent-skills/code/requirements.txt
$env:DEEPSEEK_API_KEY="your_key_here"
$env:DEEPSEEK_MODEL="your_available_deepseek_model"
python stages/08-agent-skills/code/deepseek_skills.py
```

普通输出会展示已发现的 Metadata、用户任务、模型发起的 Skill Tool Call、Host 的激活结果和
基于流程的回复。传入 `--show-model-conversation` 可查看被加载的完整 Tool Result；只应使用
非敏感的演示数据。

---

## 9. 下一章 Reliability 和 Safety

Skills 为 Agent 增加了可复用的工作方式。再加上 Tool、MCP、Memory、检索和人工审批，
Runtime 也拥有了更多失败方式：重试可能重复副作用，远程调用可能超时，流程可能请求不该
获得的能力。

[Stage 09：Reliability, Safety, and Guardrails](../09-reliability-safety/README.zh-CN.md)
会把这些风险变成 Runtime 可以检查和执行的规则。
