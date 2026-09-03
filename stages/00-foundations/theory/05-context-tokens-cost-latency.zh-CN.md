# 05 — Context Window、Token、Cost 与 Latency

每一次 model call 都在消耗有限资源。

当 Agent 会反复调用 model 时，token 与 latency 就不再只是“账单细节”，而会直接成为 architecture concern。

Context window 更像一个行李箱，不是一场“证明你能把家里每一双袜子都塞进去”的比赛。

---

## 1. 最基本的 Budget

概念上：

```text
input context
+ model-generated / reasoning / output usage
<= model / API limits
```

不同 provider / model 的精确 accounting 会不同，所以生产 metering 应优先使用 provider tokenizer / usage metadata。

但在架构层，可以先把 capacity 当作明确有限、需要预算的资源。

常见 input contributor：

```text
system / developer instructions
current user task
few-shot examples
conversation history
long-term memory
retrieved evidence
Tool schemas
Tool observations
Skill instructions
workspace / progress notes
```

信息存在 database、checkpoint、vector store 或 file 中，并不等于 model 已经知道它。

只有 application 把它选进当前 request，才成为 model context。

---

## 2. 填满 Window 之前先 Reserve

一个实用公式：

```text
available input
= max context
- output reserve
- runtime / Tool reserve
```

例如：

```text
model context limit       32,000
reserve final output       4,000
reserve Tool continuation  2,000
--------------------------------
input planning budget     26,000
```

Stage 06A 会显式表示：

```python
from tiny_agent import ContextBudget

budget = ContextBudget(
    max_context_tokens=32_000,
    reserve_output_tokens=4_000,
    reserve_runtime_tokens=2_000,
)

assert budget.available_input_tokens == 26_000
```

如果 required instruction 本身已经超过 budget，偷偷删掉 safety rule 并不能叫“context optimization”。

那是 request construction policy 已经坏了。

---

## 3. Cost 会沿 Agent Loop 复利式累积

粗略 run cost：

```text
Σ(model input usage × input price)
+ Σ(model output usage × output price)
+ Tool / API costs
+ retrieval / vector costs
+ sandbox / compute time
```

再考虑 Agent loop：

```text
plan          1 model call
search loop   3 model calls
critic        1 model call
rewrite       1 model call
----------------------------
              6 model calls
```

如果 prompt 每轮都多 10K tokens，并不是只多付一次；它可能在一整个 trajectory 中反复出现。

这也是为什么 Context Engineering、Tool exposure 和 Multi-Agent design 都会产生经济后果。

---

## 4. Latency 是 Critical Path 问题

end-to-end latency 可以来自：

```text
queue wait
model inference
retrieval
Tool / network calls
sandbox startup
retries
human approval
multi-Agent fan-out / fan-in
```

串行组合会直接相加：

```text
model 2s
-> search 1s
-> model 2s
-> API 3s
= roughly 8s + overhead
```

彼此独立的工作有时可以并发：

```text
             +-> search A 1.2s -+
planner 2s --+-> search B 1.0s -+-> synthesize 2s
             +-> search C 1.4s -+
```

只要 concurrency safe 且 bounded，这部分 latency 更接近最慢 branch，而不是简单求和。

但请记住：

> `asyncio.gather()` 是 scheduling primitive，不是一张“现在可以同时发 10,000 个 request”的许可证。

---

## 5. Throughput、Latency、Concurrency 是三件不同的事

```text
latency
    = 一个 run 需要多久

throughput
    = 单位时间系统完成多少工作

concurrency
    = 当前同时 in-flight 的 operation 数量
```

提高 concurrency 可能改善 I/O-bound workload 的 throughput，但也会增加：

- provider rate-limit pressure；
- database connections；
- memory usage；
- downstream queue；
- correlated failure burst。

Stage 10 会引入 bounded service admission，因为：

```text
async != infinite resources
```

---

## 6. Context 很大，也可能让 Quality 下降

即使所有内容都“塞得下”，不必要 context 仍然可能造成：

- attention competition；
- stale constraints；
- contradictory history；
- irrelevant evidence；
- 更大的 prompt-injection surface；
- 更高 latency / cost。

坏 policy：

```python
context = (
    all_history
    + all_memories
    + all_docs
    + all_tools
    + all_skills
)
```

更好的心智模型：

```text
application owns a large state universe
             ↓
current decision requirements
             ↓
small high-signal context
```

Large context 提供的是**容量**，不是免除 selection 的特权。

---

## 7. Cache / Reuse 不会让 Irrelevant Token 自动“免费”

某些 provider / runtime 能 cache repeated prompt prefix，从而降低 latency 或 price。

但仍要注意：

1. cached token 按 API semantics 仍可能占 context / attention capacity；
2. 一个价格更便宜的 irrelevant token，仍然可能干扰 model，或者暴露 untrusted instruction。

更合理的 optimization order：

```text
remove unnecessary context
-> make stable context reusable / cache-friendly
-> measure provider-specific benefit
```

而不是：

```text
cache everything
-> 宣布架构问题已解决
```

---

## 8. 示例：失控的 Research Agent

假设 research Agent 每次 search retrieve 20 chunks，一共做 4 次 search。

初学者把所有 chunk 都拼进后续每一次 model call：

```text
80 chunks
× repeated planning / review turns
= expensive, slow, noisy context
```

更好的设计：

```text
retrieve broad candidates
-> filter / rerank / diversify
-> select evidence
-> compact older progress
-> provide only needed Tool / Skill schemas
-> synthesize
```

model 看到的文字更少，但真正有用的信息反而更集中。

这是 Agent Engineering 一个反复出现的“反直觉”现象：

> 有时候，让 Agent 更 capable 的办法，是少给它一些东西看。

---

## 9. 要测整个 Run

有价值的 metrics：

```text
success rate
input / output tokens per run
model calls per run
Tool calls per run
p50 / p95 latency
queue time
cost per successful run
context truncation / drop rate
```

如果一个更便宜 configuration 经常 fail 并触发 retry，`cost per request` 可能具有误导性。

有条件时更应关注：

```text
cost per successful task
```

---

## 10. 连接 Context Engineering

Stage 00 提供 resource model；Stage 06A 把它变成 policy engine：

```text
ContextBudget
+ ContextItem priority / trust / provenance
+ required vs optional
+ compaction
= context selected for this decision
```

最终要记住：

> **Context window 是有限的 decision-time resource。Token、latency 与 model call 都应该被 application 当作 budget 管理，而不是无限背景资源。**