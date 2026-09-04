# 02 — `SKILL.md` 格式与 Progressive Disclosure

> Language: [English](02-skill-format-and-progressive-disclosure.md) | 简体中文

Tiny-Agent 采用开放的 Agent Skills 格式，而不是发明一套只能在本仓库里使用的 skill language。

基本目录故意设计得很朴素：

```text
skill-name/
├── SKILL.md          required
├── scripts/          optional executable helpers
├── references/       optional detailed documentation
└── assets/           optional templates/data/resources
```

这种“无聊的互操作性”往往恰恰是优秀工程。线上出事故时，没有人会因为你们的配置格式“全球独一份”而感到欣慰。

---

## 1. `SKILL.md` = Metadata + Instructions

文件由 YAML frontmatter 开头，后面跟 Markdown：

```markdown
---
name: research-review
description: Review research claims against cited evidence. Use when checking literature reviews, research reports, or citation grounding.
license: MIT
compatibility: Requires access to the relevant evidence text.
metadata:
  owner: tiny-agent
  version: "1"
---

# Research Review Procedure

1. Enumerate claims.
2. Find the evidence cited for each claim.
3. Compare wording strength with evidence strength.
4. Flag unsupported claims.
```

Metadata 服务于 discovery；正文负责教授 procedure。

---

## 2. Name 与 Description 是 Routing Infrastructure

官方格式要求受约束的 `name` 和有意义的 `description`。

为什么 description 如此重要？因为 progressive disclosure 从 metadata 开始。

糟糕：

```text
"Helps with stuff."
```

Router 几乎得不到任何有效信号。

更好：

```text
"Reviews research claims against cited evidence. Use for literature reviews,
research reports, citation verification, or grounding checks."
```

好的 description 既告诉系统**这个 Skill 做什么**，也告诉它**什么时候应该 activate**。

---

## 3. Tiny-Agent 会 Validate Format

实际 `SkillCatalog` discovery 的简化形式：

```python
catalog = SkillCatalog("skills")
skills = catalog.discover()

for skill in skills:
    print(skill.name, skill.description)
```

Parser 会检查：

```text
valid lowercase/hyphen name
name matches directory
non-empty bounded description
frontmatter is a mapping
metadata is a string map
allowed-tools has expected shape
paths remain inside the skill root
```

例如：

```text
skills/review/SKILL.md
name: TotallyDifferentName
```

Tiny-Agent 会直接失败，而不是悄悄生成一个歧义 catalog。

---

## 4. Progressive Disclosure 有三层

一个合理的 Skill 系统不会在启动时把每个已安装 Skill 的全部文件都读进 context：

```text
Level 1: discovery
    name + description metadata

Level 2: activation
    full SKILL.md instructions

Level 3: resource access
    one needed script/reference/asset
```

可以把它想成图书馆：

```text
catalog card      -> metadata
borrow the book   -> activate Skill
open appendix C   -> load reference as needed
```

你不会为了问图书管理员一个问题，先把整栋图书馆复印一遍。

---

## 5. Tiny-Agent 中的 Metadata 与 Activation

启动阶段只加载精简 metadata：

```python
catalog = SkillCatalog("skills")
print(catalog.metadata_prompt())
```

输出类似：

```text
- code-review: Review code changes for correctness and safety.
- research-review: Review research claims against evidence.
```

真正 activation：

```python
skill = catalog.activate("research-review")

print(skill.instructions)
print(skill.references)
print(skill.scripts)
print(skill.assets)
```

References/scripts/assets 只有在 activate 后才枚举。

---

## 6. Reference 应该保持 Focused

糟糕：

```text
SKILL.md = 40,000 tokens of every policy, API manual, example, and historical note
```

更好：

```text
SKILL.md
  -> concise operating procedure
references/
  -> evidence-policy.md
  -> output-format.md
  -> edge-cases.md
```

然后只加载当前真正需要的 reference。

这就是 Stage 07 Context Engineering 在 procedural knowledge 上的延伸。

---

## 7. Script 是 Executable Software

Skill 可能包含：

```text
scripts/check_citations.py
```

这个文件绝不是“另一段 prompt context”，它是代码。

执行第三方 script 前需要考虑：

- source/trust；
- dependency provenance；
- sandbox policy；
- filesystem/network access；
- credential exposure；
- review/signing/version policy。

Stage 12 会提供 controlled compute boundary。

Markdown 目录因为多了几个可执行文件，并不会让 supply-chain 问题消失；它只是让目录标题看起来更整齐了。

---

## 8. `allowed-tools` 不是 Tiny-Agent Authorization

Agent Skills 格式定义了实验性的 `allowed-tools` 字段，不同 implementation 可以有不同解释。

Tiny-Agent 会把它暴露在：

```python
print(skill.descriptor.allowed_tools)
```

但故意**不会**把它转换成 runtime permission：

```text
Skill metadata says Bash(git:*)
          ↓
model may understand intended capability
          ↓
Tiny-Agent policy independently decides what is actually allowed
```

Portable metadata 与 local authorization 是不同层。

---

## 9. Safe File Discovery

第三方 Skill resource 会引入 path boundary 问题。

Tiny-Agent 会 resolve 每一个 discovered file，并验证最终路径仍然位于 Skill root 内，从而阻止 traversal/symlink escape，例如：

```text
../../.ssh/id_rsa
```

通用原则：

> 一个“看起来是相对路径”的字符串并不可信，必须先 resolve，再确认目标仍在允许的 root 下。

Stage 12 会把同一原则用于 Agent workspace。

---

## 10. 完整设计示例

`data-analysis` Skill：

```text
data-analysis/
├── SKILL.md
├── references/
│   ├── statistical-checks.md
│   └── chart-guidelines.md
├── scripts/
│   └── validate_csv.py
└── assets/
    └── report-template.md
```

Runtime flow：

```text
user asks to analyze CSV
-> metadata router selects data-analysis
-> load SKILL.md
-> read statistical-checks only if needed
-> sandbox validate_csv.py if execution is authorized
-> use report-template at final artifact step
```

这是 context 和 compute 两个层面的 progressive disclosure。

---

## 完成检查

你应该能够：

1. 编写合法的 `SKILL.md` metadata；
2. 解释为什么 description quality 会影响 routing；
3. 区分 discovery、activation 和 resource loading；
4. 解释为什么 scripts 会产生 supply-chain/execution boundary；
5. 解释为什么 `allowed-tools` 绝不能自动等价于 authorization；
6. 校验路径并把 resource access 限制在 Skill root 内。
