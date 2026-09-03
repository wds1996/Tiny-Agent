# 05 — 每一次调用都有代价：Context、Token、Cost 与 Latency

> Language: [English](05-context-tokens-cost-latency.md) | 简体中文

前四章里，我们关注的主要是“模型能不能完成任务”。

现在把旅行助手真正放进循环：

```text
用户问题
   ↓
模型决定查天气
   ↓
Tool 返回天气
   ↓
模型决定做温度换算
   ↓
Tool 返回结果
   ↓
模型生成最终回答
```

你会发现一个很现实的问题：**一次用户请求，可能已经对应了三次模型调用。**

如果每一轮都携带大量历史、Tool schema、文档和指令，那么“多加一点 Context”就不再只是多几行文字，而是会在整个循环中反复付出成本。

所以这一章想建立的核心直觉是：

> **Context、Token、模型调用次数和延迟，都是 Runtime 需要管理的有限资源。**

---

## 1. Context 不是“模型知道的一切”

先统一一个最重要的词。

在本课程里，**Context（上下文）**指的是：

> 当前这一次模型推理实际能够看到的输入信息。

它可能包括：

```text
应用指令
当前用户任务
对话历史
Tool schema
Tool 执行结果
检索证据
Memory 中选出来的内容
few-shot 示例
工作区进度摘要
```

注意“选出来的”三个字。

假设你的系统拥有：

```text
数据库：100 万条订单
向量库：10 万篇文档
硬盘：20 GB 文件
Memory：过去半年用户偏好
```

这些属于应用**可用的数据宇宙**。

它们不等于模型当前的 Context。

```text
Storage / State 中存在
!=
当前模型看见
```

只有 Runtime 真正把某部分数据放进当前请求，它才成为这次推理的 Context。

这个区别以后会非常重要：

```text
Context != State
Context != Memory
Context != RAG corpus
Context != Checkpoint
```

---

## 2. Token 是什么？为什么不直接按字数算？

模型不是按“汉字数”或“英文单词数”直接计算输入长度，而是把文本编码成 Token。

一个 Token 可能对应：

```text
一个完整词
一个词的一部分
一个标点
一个汉字或若干字符片段
```

具体切分取决于模型的 tokenizer。

因此不要在工程里写：

```python
estimated_tokens = len(text.split())
```

然后把它当精确值。

在真正请求后，最可信的计量来源之一是 provider 返回的 usage metadata。

---

## 3. 直接看看 OpenAI 返回了多少 Token

```python
from openai import OpenAI

client = OpenAI()

response = client.responses.create(
    model="gpt-5.6-luna",
    instructions="用一句话回答，保持简洁。",
    input="为什么 Agent 的 Context 需要由 Runtime 管理？",
)

print(response.output_text)
print("input_tokens =", response.usage.input_tokens)
print("output_tokens =", response.usage.output_tokens)
print("total_tokens =", response.usage.total_tokens)
```

### 示例输出

Token 数会随模型版本、输入格式和实际输出变化，下面只是模拟一个合理的量级：

```text
Runtime 需要管理 Context，因为模型只能基于当前收到的信息推理，而无关或过量信息会增加成本、延迟和干扰。
input_tokens = 42
output_tokens = 31
total_tokens = 73
```

关键不是记住 `42`。

关键是看到：**一次调用真的有可观测的输入和输出 Token 使用量。**

等 Agent 一次任务调用模型 5 次、10 次，这些量就会累积。

---

## 4. Context window 是容量上限，不是装满目标

模型有有限的 Context window。

可以先用一个简化公式理解：

```text
输入 Context
+ 模型输出 / 推理所需空间
<= 模型允许的范围
```

初学者常见的错误直觉是：

> “模型支持很长 Context，那我全塞进去不就好了？”

这就像买了一个 30 kg 的行李箱，然后认为出门三天必须装满 30 kg 才不浪费。

容量大的真正意义是：

> **当任务确实需要更多信息时，你有余量。**

它不意味着无关内容突然变得有价值。

---

## 5. 为什么要提前给输出和后续执行留空间？

假设我们用一个教学数字：

```text
最大 Context / 使用预算      32,000
预留最终输出                  4,000
预留后续 Tool / Runtime       2,000
-----------------------------------
计划输入预算                 26,000
```

于是：

```python
max_context = 32_000
reserve_output = 4_000
reserve_runtime = 2_000

available_input = (
    max_context
    - reserve_output
    - reserve_runtime
)

print(available_input)  # 26000
```

完整教学示例：

[`../code/context_budget_basics.py`](../code/context_budget_basics.py)

为什么要预留？

因为一个 Agent request 不是只考虑“现在能不能塞进去”。

它还可能需要：

```text
模型生成回答
Tool 返回结果
再做一轮模型推理
生成更长最终答案
```

如果第一轮把所有空间都占满，后面的执行路径会非常被动。

这里的 32K/4K/2K 是教学数字，不是某个模型的固定规格。真正生产系统应该读取当前模型和 API 的实际限制。

---

## 6. Agent 为什么会让成本成倍累积？

普通聊天可能是：

```text
1 个用户问题
→ 1 次模型调用
```

Agent 可能是：

```text
route         1 次
plan          1 次
Tool loop     3 次
review        1 次
rewrite       1 次
----------------
              7 次模型调用
```

假设每轮都携带额外 10,000 Token 的历史和文档，那么这 10,000 Token 可能不是付一次，而是被重复带入多轮。

粗略看：

```text
额外 Context × 模型调用次数
```

就能理解为什么 Agent 的成本优化经常不是“换个便宜模型”这么简单。

减少无用 Context、减少不必要模型轮次、缩小 Tool 暴露面，都可能影响成本。

---

## 7. Cost 应该看“完成一个任务花多少”，而不只是“一次调用多少钱”

一次模型运行的总成本可能来自：

```text
模型输入 Token
+ 模型输出 Token
+ Tool / 外部 API
+ 检索 / 向量数据库
+ Sandbox / Compute
+ Retry
```

因此只比较：

```text
model A 单次便宜
model B 单次贵
```

可能得到错误结论。

例如：

```text
便宜模型：每次 $0.2，但经常失败并重试 4 次
较强模型：每次 $0.5，通常一次完成
```

真正更有意义的指标是：

> **cost per successful task（每个成功任务的成本）**

Stage 08 会正式建立评估指标体系，现在先建立这个意识。

---

## 8. Latency 也不是只看模型响应时间

一个 Agent 的端到端延迟可能包含：

```text
排队
模型推理
检索
Tool 网络请求
数据库
Sandbox 启动
Retry
人类审批
其它 Agent
```

例如：

```text
模型            2s
天气 API         1s
模型            2s
另一个 API       3s
------------------
大约            8s + overhead
```

如果步骤有依赖关系，就只能串行等待。

如果几个工作彼此独立，才可能并发：

```text
             ┌─ search A 1.2s ─┐
planner 2s ──┼─ search B 1.0s ─┼─ synthesize 2s
             └─ search C 1.4s ─┘
```

这时搜索部分更接近最慢分支，而不是三个时间直接相加。

但是并发也不是免费午餐。

大量并发可能带来：

```text
rate limit
数据库连接耗尽
内存上涨
下游排队
失败同时爆发
```

所以后面 Stage 10 还会学习 bounded concurrency 和 backpressure。

---

## 9. Context 越大，质量不一定越高

这是最值得反直觉理解的一点。

假设模型 Context 足够大，可以一次塞入：

```text
全部对话历史
全部 Memory
全部检索文档
所有 Tool
所有 Skill
全部工作区文件
```

技术上“装得下”，不代表模型会更聪明。

额外内容可能带来：

```text
无关信息竞争注意力
旧指令和新要求冲突
重复事实
过时 Memory
低质量证据
更大的 prompt-injection 攻击面
更高成本
更长延迟
```

所以：

```python
context = all_history + all_memory + all_docs + all_tools
```

通常不是 Context Engineering，而是 Context 倾倒。

更好的思路是：

```text
应用拥有很多信息
       ↓
当前这一步真正需要什么？
       ↓
选择高信号内容
       ↓
构造本轮 Context
```

Stage 06A 会把“选择、压缩、优先级、来源和信任”正式做成一套机制。

---

## 10. Prompt caching 能解决一切吗？

不能。

缓存重复的稳定前缀，确实可能减少某些请求的延迟或成本；当前 OpenAI 模型也提供 prompt caching 相关能力。

但缓存不会把无关信息变成有用信息。

即使一段 Context 更便宜：

```text
它仍可能占据上下文容量
仍可能干扰模型判断
仍可能扩大不可信文本影响范围
```

所以通常应该先问：

```text
这段内容需要发送吗？
```

然后再问：

```text
如果需要，怎样让稳定前缀更容易复用 / 缓存？
```

不要反过来。

---

## 11. 一个研究 Agent 为什么很容易“Context 失控”？

假设一个研究 Agent 每次搜索取回 20 个 chunk，共搜索 4 次。

初学者可能这样写：

```text
第一次：带 20 个 chunk
第二次：带前 20 + 新 20
第三次：带 60
第四次：带 80
最后写作：再带全部 80
```

然后又加入：

```text
完整聊天历史
全部 Tool schema
几段 Memory
规划过程
```

系统会越来越慢，也越来越难判断到底哪些信息真正影响答案。

更合理的流程可能是：

```text
广泛检索候选
   ↓
过滤 / rerank / 去重
   ↓
选择真正需要的证据
   ↓
压缩旧进度
   ↓
只暴露当前需要的 Tool / Skill
   ↓
生成答案
```

有时让 Agent 更强的方式，不是给它更多，而是**帮它少看一点无关内容。**

---

## 12. 你应该开始记录哪些指标？

Stage 00 不要求你搭监控系统，但从现在开始应该知道哪些数字有意义：

```text
任务成功率
每个任务调用模型次数
每个任务输入 / 输出 Token
Tool 调用次数
p50 / p95 延迟
Retry 次数
每个成功任务成本
Context 被截断 / 丢弃的比例
```

这些指标以后会进入 Stage 08 的 Evaluation 与 Observability。

现在只需要形成一个习惯：

> **不要只看“模型这次回答得不错”，还要看完成这个任务用了多少资源、走了多少步。**

---

## 13. 为什么下一章要讲 Instructions 和 Context Construction？

这一章建立了一个事实：

```text
Context 是有限资源
```

那么下一步就不能再问：

> “我还有哪些内容可以塞进 prompt？”

而应该问：

> **“这一轮到底需要哪些内容？哪些是规则，哪些是用户任务，哪些是证据，哪些只是可选背景？”**

于是我们从“Prompt Engineering”走向一个更结构化的问题：

```text
应用怎样构造一次模型请求？
```

下一章会把：

```text
Instructions
Task
Evidence
Memory
Tool schemas
Examples
```

逐层分开。

---

## 本章小结

请记住四个区别：

```text
应用拥有的数据 != 当前 Context
Context window 容量 != 应该使用的 Context
单次调用成本 != 完整任务成本
并发 != 无限资源
```

Agent 进入循环以后，Token、Context、调用次数和延迟都会成为架构的一部分。

---

## 官方参考

- OpenAI Responses API usage：<https://developers.openai.com/api/reference/resources/responses>
- OpenAI model guidance / prompt caching：<https://developers.openai.com/api/docs/guides/latest-model>
