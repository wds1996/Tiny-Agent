# Advanced — Tool / Agent-Computer Interface 设计

Function Calling 的质量，很大程度取决于 model 实际看到的 interface。

即使 runtime 本身实现得完全正确，如果 Tool：

- 含糊；
- 互相重叠；
- 权限范围太大；
- observation 难以使用；

Agent 仍然可能表现很差。

所以 Tool design 不是“把 Python function 包一下”这么简单，而是一个 **Agent–Computer Interface** 问题。

## 设计维度

### 1. Name

优先选择稳定、具体、语义清晰的 verb / noun：

```text
search_papers
read_document_chunk
create_report_draft
```

避免：

```text
do_task_2
run_stuff
helper
```

model 需要根据 name + description 理解 action space。

### 2. Description

description 应该解释：

- Tool 做什么；
- 什么时候应该使用；
- 关键限制；
- 它**不做什么**。

Tool selection 本身就是 language-understanding problem。

如果两个 Tool 的 description 都写：

```text
"Search for information."
```

那 model 选错并不奇怪；interface 本身没有提供足够可区分信号。

### 3. Schema

当 application 已经知道 valid domain 时，应使用：

- constrained enum；
- ranges；
- required fields；
- explicit object shape。

不要让 model 用 free-form string 自己“编码 policy”。

例如，已知 environment 只有：

```text
staging
production
```

就应该使用 enum，而不是让 model 自己写任意环境名，再由后面某段字符串逻辑猜测。

### 4. Granularity

太细：

```text
每一个 tiny implementation detail 都变成一个 Tool
```

会产生很长 Tool chain，增加：

- model calls；
- latency；
- decision error；
- context cost。

太宽：

```text
shell(command)
http(method, url, headers, body)
```

又会极大扩张 authority / ambiguity。

更合理的目标是：

> **面向真实 task 的 capability，并且只拥有完成任务所需的最低 privilege。**

### 5. Output

Tool output 会成为后续 model context。

所以不要默认返回 5 MB logs。

更好的 observation 应该尽量：

```text
structured
bounded
provenance-rich
```

例如与其把整个 HTTP response body 原封不动扔给 model，不如返回：

```json
{
  "status": "ok",
  "records": [...],
  "source": "internal-catalog",
  "truncated": false
}
```

## Dynamic Exposure

大型系统可能拥有几百个 Tool。

Context Engineering 可以只把当前 task / domain 相关 subset 暴露给 model：

```text
large application Tool universe
        ↓
current route / task
        ↓
small model-visible Tool set
```

但一定要记住：

```text
visible to model
!=
authorized to execute
```

model 看见某个 Tool，只代表它可以提出调用 proposal。

runtime 在收到 ToolCall 后仍要做 permission / approval / policy validation。

## 如何评估 Tool Interface

建立 task dataset，然后测：

- correct Tool selection；
- argument accuracy；
- unnecessary calls；
- error 后的 recovery；
- output token / context cost。

如果 model 经常选错 Tool，不应该第一反应就是：

> 换一个更大的模型。

先检查 Tool interface 是否本身含糊。

一个更强的 model 可以偶尔替你猜中糟糕 interface，但这不意味着 interface 设计正确。

## 最终原则

> **Tool design 是 Agent-computer interface design：不仅要让 Python 能调用，还要让 model 能正确理解、application 能严格验证、runtime 能最小权限执行、observation 能高质量进入下一次 context。**

参考：
https://www.anthropic.com/engineering/writing-tools-for-agents