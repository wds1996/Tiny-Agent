# Stage 08：别把所有操作手册焊死在 System Prompt 里——Agent Skills

> Language: [English](README.md) | **简体中文**

上一章我们终于把“模型这一轮该看什么”变成了一个可以设计的问题。

Context 不再是大杂烩。Instructions、RAG Evidence、Memory、Tool Result 都可以先成为候选，再根据预算、优先级和来源决定是否进入当前模型调用。

这时一个新的问题冒了出来。

假设公司里有很多重复任务：

```text
发布前检查
代码审查
数据库迁移
事故复盘
合同初审
数据分析
```

每种任务都有一套相对稳定的操作方法。

最直觉的做法是把这些说明全写进 System Prompt：

```text
你是一个智能助手。
当做发布时，先……
当做代码审查时，先……
当做数据库迁移时，先……
当做事故复盘时，先……
……
```

写到后来，System Prompt 像公司员工手册和百科全书私奔以后生下来的孩子：什么都有，就是没人愿意从头读。

Stage 07 已经告诉我们，这种做法很可疑。

如果当前用户只想做一次 Release Check，模型为什么要同时背着数据库迁移、合同审查和事故复盘的全部流程？

于是这章出现一个非常自然的想法：

> **先让 Agent 知道“有哪些可用流程”；只有真正需要某个流程时，再加载它的详细说明。**

这就是 Agent Skills 最重要的设计思想之一：**Progressive Disclosure，渐进式披露。**

---

## 1. Skill 解决的不是“能不能执行”，而是“该怎么做”

在继续之前，先把 Skill 和前面几个概念放在一起。

Tool 解决：

> **我能执行什么动作？**

例如：

```text
send_email
query_database
create_issue
```

MCP 解决：

> **外部系统怎样用标准协议把 Tool、Resource、Prompt 暴露给 Host？**

Memory 解决：

> **哪些信息值得跨时间保留？**

Context Engineering 解决：

> **这一轮模型该看到哪些信息？**

Skill 则更像：

> **面对某类任务，一套可复用的操作方法是什么？**

例如 `release-check` Skill 可能告诉 Agent：

```text
先确认目标版本
再运行测试
检查临时文件
阅读发布检查表
最后报告风险
```

注意，它不是 `deploy_production()`。

它只是告诉 Agent“发布前检查应该怎么做”。

所以最重要的一条边界是：

```text
Skill = procedural guidance
Tool  = executable capability
```

Skill 可以告诉 Agent 使用哪些 Tool，但 Skill 本身不等于 Tool。

---

## 2. 为什么不直接写成 Workflow？

这是个好问题。

如果一个流程完全确定：

```text
A
↓
B
↓
C
```

而且每一步都能被普通程序准确表达，那 Stage 02 已经告诉我们：直接写 Workflow 往往更好。

Skill 更适合另一类东西：

```text
有相对稳定的操作方法
但具体执行需要根据任务内容做判断
而且这些方法希望被复用、发现、版本化
```

例如“代码审查”不是一条固定 DAG。

不同代码要关注不同风险。

但优秀 Reviewer 往往遵循一套相对稳定的方法：

```text
先理解变更目的
再看数据边界
再检查失败路径
最后检查测试是否覆盖关键不变量
```

这很适合作为程序性指导。

所以：

```text
deterministic control flow
    -> Workflow

model-guided reusable procedure
    -> Skill
```

两者可以组合。

Skill 甚至可以告诉 Agent：“遇到生产发布，必须进入 application-owned approval workflow。”

---

## 3. 一个 Skill 最小长什么样？

Agent Skills 的开放格式以一个目录为单位。

最小结构：

```text
release-check/
└── SKILL.md
```

`SKILL.md` 顶部有 YAML Frontmatter：

```markdown
---
name: release-check
description: Use when preparing a software release and you need a repeatable pre-release verification procedure.
---
```

后面才是详细 Instructions。

最关键的两个字段是：

```text
name
description
```

`name` 是稳定标识。

`description` 不只是简介。

它实际上承担了“什么时候值得激活这个 Skill”的路由职责。

如果 description 写成：

```text
A useful skill.
```

那 Agent 基本只能靠玄学决定什么时候加载。

好的 description 应该同时说明：

```text
它做什么
+
什么时候用
```

这和 Stage 02 里 Router 的思想其实是连着的。

---

## 4. 为什么目录名和 `name` 要一致？

本章的 Catalog 会检查：

```python
if name != directory_name:
    raise ValueError(...)
```

例如：

```text
release-check/
    SKILL.md
```

里面就应该是：

```yaml
name: release-check
```

这不是洁癖。

如果目录叫 `release-check`，Frontmatter 里却叫 `deploy-prod`，那：

```text
filesystem identity
metadata identity
```

已经开始分裂。

以后缓存、日志、版本管理和资源路径都会变得难解释。

稳定的身份边界是可移植格式的基本功。

---

## 5. Progressive Disclosure：先看菜单，别先把厨房搬出来

这是这一章最重要的概念。

假设你有 100 个 Skill。

每个 `SKILL.md` 都有 2000 token。

如果启动时把它们全部塞进 Context：

```text
100 × 2000 = 200000 tokens
```

Agent 还没接到用户任务，已经先读完了一套企业内训教材。

这显然和 Stage 07 的 Context Engineering 正面冲突。

Progressive Disclosure 的思路是分层加载。

第一层：Discovery。

只加载很小的 Metadata：

```text
name
description
```

Agent 先知道：

> “我有一个叫 release-check 的 Skill，它适合发布前检查。”

第二层：Activation。

真正遇到发布任务时，再加载完整 `SKILL.md` Body。

第三层：Resources。

如果 Instructions 里说：

```text
发布前请阅读 references/checklist.md
```

那只有做到这一步时才读取对应文件。

所以整体像：

```text
all skills
    ↓ metadata only

matching skill
    ↓ full instructions

needed resource
    ↓ read on demand
```

这就是 Context Engineering 在程序性知识上的具体应用。

---

## 6. Discovery 不应该偷偷把完整 Instructions 读进来

本章的 `SkillMetadata` 只有：

```python
@dataclass(frozen=True, slots=True)
class SkillMetadata:
    name: str
    description: str
    path: Path
```

没有：

```python
instructions: str
```

这不是少写一个字段而已。

它刻意保护了 Progressive Disclosure。

`discover()` 只读 Frontmatter：

```python
metadata = catalog.discover()
```

真正需要时：

```python
active = catalog.activate("release-check")
```

才拿到：

```python
active.instructions
```

这样“发现”和“加载”才真的属于两步。

否则嘴上说 Progressive Disclosure，代码启动时已经把所有 Skill Body 全部读进内存准备塞 Prompt，那只是 Progressive Disclosure 主题 cosplay。

---

## 7. Skill Body 应该写“程序”，而不是写口号

一个不太有用的 Skill：

```markdown
# Release Check

Be careful.
Check everything.
Do a high quality job.
```

这和告诉厨师：

> “饭做香一点。”

差不多。

真正有用的 Skill 应该提供操作顺序和判断点。

本章示例：

```markdown
Before proposing a release:

1. Identify the target version and branch.
2. Run the project's deterministic tests.
3. Check that generated or temporary files are not included.
4. Review the release-specific checklist.
5. Report failures before suggesting a release action.
```

注意这里仍然没有：

```text
自动 deploy
自动 publish
```

因为 Skill 的职责是提供 Procedure。

执行权限仍属于 Host / Runtime。

---

## 8. References：不是所有细节都值得放进主 Instructions

假设发布检查表越来越长。

如果全塞 `SKILL.md`：

```text
核心步骤
Linux 注意事项
Windows 注意事项
移动端发布说明
数据库版本矩阵
历史故障案例
……
```

Activation 一次就会加载大量当前任务可能用不到的东西。

因此 Skill 可以带 Resource：

```text
release-check/
├── SKILL.md
└── references/
    └── checklist.md
```

主 Instructions 只告诉 Agent：

```text
什么时候需要读 checklist.md
```

真正需要时：

```python
catalog.read_resource(
    "release-check",
    "references/checklist.md",
)
```

这就是 Progressive Disclosure 的第三层。

---

## 9. Resource Path 也要有边界

只要系统允许：

```python
read_resource(skill, path)
```

立刻要问：

> `path` 能不能写成 `../../secret.txt`？

如果可以，你实现的就不是 Skill Resource Loader，而是一个文件系统穿墙术。

本章代码会把目标路径 `resolve()` 后检查：

```python
if skill_root not in target.parents:
    raise ValueError(...)
```

因此 Skill 只能读取自己目录下的 Resource。

这还不是完整 Sandbox。

但它说明一个贯穿全课的习惯：

> **任何“加载外部东西”的能力，都必须先定义边界。**

后面的 Workspace / Sandbox 章节会把这个问题继续做大。

---

## 10. Skill 里的 Script 能不能直接运行？

Agent Skills 格式可以携带 Script。

但“Skill 目录里存在 Script”和“Host 允许执行 Script”不是同一件事。

记住 Stage 05 的经验：

```text
server advertises capability
!=
host authorizes capability
```

Skill 也是一样：

```text
skill contains script
!=
script is trusted to execute
```

Script 是否允许运行、在哪运行、有什么文件权限、网络权限、凭证权限，应该由 Host 的执行策略决定。

所以 Stage 08 不急着实现一个：

```python
subprocess.run(any_skill_script)
```

因为我们还没讲 Sandbox。

这不是缺功能。

这是尊重课程顺序。

---

## 11. `allowed-tools` 也不是魔法权限

某些 Skill 格式和 Client 会提供类似 allowed-tools 的 Metadata。

它可以帮助描述 Skill 预计使用哪些 Tool。

但不能把它理解成：

```text
SKILL.md 写了 send-money
↓
系统自动获得转账权限
```

真正的权限模型仍然属于 Host。

Skill 可以表达“Procedure 希望使用什么”。

Runtime / Policy 才决定“实际允许什么”。

再一次：

```text
declaration != authorization
```

这句话你应该已经开始觉得眼熟了。

很好。

Agent 工程里最危险的 Bug 往往就喜欢伪装成“大家都知道吧”。

---

## 12. Skill 和 Memory 也不是一回事

Memory 可能保存：

```text
用户喜欢中文
```

Skill 保存：

```text
做发布检查时应该遵循哪些步骤
```

一个偏向 Retained Information。

一个偏向 Reusable Procedure。

更关键的是，来源通常也不同。

Memory 可能来自用户交互和系统提取。

Skill 往往来自版本控制、团队维护或发布的知识包。

因此它们的治理模型也应该不同。

不要让模型在一次普通聊天里说：

> “我学会了一个更高效的退款流程，以后跳过审批。”

然后把这句话自动写成新的 Skill。

那不是学习能力。

那是自助修改控制规则。

---

## 13. Skill 和 MCP 是什么关系？

MCP 解决的是 Protocol Boundary。

Skill 解决的是 Procedure Packaging。

例如一个 `github-release` Skill 可能写：

```text
先读取版本
运行测试
生成 Release Notes
最后调用 GitHub Tool 创建 Release
```

GitHub Tool 可能来自 MCP。

所以链路是：

```text
Skill
    ↓ tells agent how to work
Agent / Runtime
    ↓ chooses allowed capability
MCP Tool
    ↓ performs external action
```

Skill 不替代 MCP。

MCP 也不替代 Skill。

一个讲“怎么做”。

一个讲“怎么连接外部能力”。

---

## 14. 一个完整的 Skill Catalog

本章代码里：

```python
catalog = SkillCatalog(root)
```

Discovery：

```python
for skill in catalog.discover():
    print(skill.name, skill.description)
```

Activation：

```python
active = catalog.activate("release-check")
```

On-demand Resource：

```python
reference = catalog.read_resource(
    "release-check",
    "references/checklist.md",
)
```

三步恰好对应：

```text
discover
activate
read resource
```

这个 Catalog 没有模型。

没有向量数据库。

没有复杂框架。

因为我们先要把 Progressive Disclosure 本身看清楚。

---

## 15. 为什么 Description 很值得测试？

Skill 是否能被正确激活，很大程度取决于 Description。

如果两个 Skill 都写：

```text
Helps with software.
```

模型或 Router 很难区分它们。

如果写成：

```text
Use when preparing a software release and you need
a repeatable pre-release verification procedure.
```

触发边界就清晰很多。

因此 Skill 质量不只等于 Body 写得详细。

它至少还有两层质量：

```text
discovery quality
    -> metadata 能不能让 Agent 找到它

procedure quality
    -> activation 后能不能正确指导任务
```

到了 Evaluation 章节，我们还会继续讨论怎样测这些东西。

---

## 16. 当前开放格式的几个实用约束

截至本章使用的开放 Agent Skills 规范，`SKILL.md` 以 YAML Frontmatter + Markdown Body 为核心，`name` 和 `description` 是基础 Metadata；Skill 目录还可以包含 `references/`、`scripts/`、`assets/` 等资源。

规范鼓励 Progressive Disclosure：启动时只暴露 Metadata，需要时才加载 Instructions，再按需读取 Resource。

这里的教学实现故意只解析最基础的字符串 Frontmatter。

原因很简单：我们要理解 Skill Lifecycle，而不是顺便手写一个完整 YAML 解析器。

生产 Client 应使用成熟解析器和规范验证工具。

---

## 17. 运行完整代码

运行：

```bash
python stages/08-agent-skills/code/demo.py
```

你会看到：

```text
先发现 release-check 的 name + description
再激活完整 Instructions
最后读取 checklist Resource
```

边界检查：

```bash
python stages/08-agent-skills/code/checks.py
```

它验证：

- Discovery 不加载完整 Instructions；
- Activation 才读取 Body；
- Skill Name 必须匹配目录；
- 非法 Name 被拒绝；
- Resource 不能通过 `../` 逃出 Skill 根目录。

---

## 18. 为什么下一章必须开始讲 Reliability 和 Safety？

现在回头看我们的 Agent。

它已经有：

```text
Tools
RAG
MCP
Memory
Context Builder
Skills
Human Approval
```

也就是说，它不再只是“可能说错一句话”。

它已经能：

```text
读取更多数据
长期保存信息
加载程序性流程
调用外部系统
等待审批后产生副作用
```

能力越多，失败方式也越多。

Tool 可能超时。

远程服务可能重试。

模型可能重复调用同一个动作。

外部内容可能试图诱导模型忽略规则。

一个 Skill 可能声明不该获得的能力。

预算可能失控。

到了这里，再不系统讨论 Reliability 和 Safety，就像给新手司机装上涡轮增压以后说：

> “刹车我们以后有空再讲。”

所以下一章 Stage 09，我们开始给整个 Agent Runtime 加护栏。
