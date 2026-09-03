# 04 — 不同模型不是“同一种 LLM”：能力、推理强度与模型选择

> Language: [English](04-model-capabilities-and-reasoning.md) | 简体中文

前面三章，我们一直默认一件事：

```text
“选一个模型，然后调用它。”
```

但真正开始做 Agent 后，你很快会发现：**不同步骤对模型的要求并不一样。**

旅行助手里至少可能出现这些任务：

```text
判断用户是不是在问天气
提取城市和日期
决定下一步该调用哪个 Tool
根据多条信息规划旅行路线
最后写一段自然的旅行建议
```

如果所有任务都不加区分地使用“最强、最贵、推理最多”的模型，系统通常能跑，但不一定是好的工程设计。

这一章想教你的不是“哪个模型排行榜第一”，而是一个更耐用的思路：

> **先看任务需要什么能力，再选择能满足目标的模型和推理配置。**

---

## 1. 先把“模型”理解成一组能力，而不是一个名字

当你写：

```python
model="gpt-5.6-luna"
```

不要只把它看成一个字符串。

这个 model ID 背后代表一组实际能力和约束，例如：

```text
推理能力
Tool Calling
Structured Output
多模态输入
上下文窗口
输出上限
延迟
吞吐量
价格
可配置推理强度
```

不同模型可能在这些维度上差异很大。

因此“这个模型比那个模型强吗？”通常问得太粗。

更有用的问题是：

> **对我现在这个步骤，它够不够好？**

---

## 2. Agent 里的不同角色，本来就可能需要不同模型

假设旅行助手慢慢变复杂：

```text
用户请求
   ↓
意图分类
   ↓
旅行计划
   ↓
Tool / 检索
   ↓
最终回答
```

不同步骤的需求可能完全不同。

### 意图分类

任务可能只是：

```text
WEATHER
TRANSPORT
HOTEL
OTHER
```

重点是：

```text
快
便宜
Structured Output 稳定
```

这里不一定需要最高推理强度。

### 旅行计划

如果用户要求：

> 三天东京行程，考虑博物馆闭馆时间、交通距离、老人同行、预算和下雨备选。

这已经是多约束规划。

重点可能变成：

```text
推理质量
约束满足
计划一致性
```

### 最终写作

最后一步可能更关心：

```text
表达自然
信息完整
不要丢掉 Tool 已确认的事实
```

所以模型选择本质上是：

```text
任务角色
   ↓
需要的能力
   ↓
候选模型 / 配置
   ↓
实际评估
```

而不是：

```text
“我最喜欢哪个模型品牌？”
```

---

## 3. 当前 GPT-5.6 系列可以怎样理解？

截至本课程当前版本，OpenAI 的 GPT-5.6 系列提供不同定位的模型，例如：

```text
gpt-5.6-luna   -> 更偏高吞吐、效率型工作负载
gpt-5.6-terra  -> 智能与成本之间的平衡
gpt-5.6-sol    -> 旗舰能力，质量优先
```

这些名字和定位属于**会变化的 provider 细节**。

所以正确学习方式不是背：

> “分类必须用 luna，规划必须用 sol。”

而是学会写出这种需求：

```text
意图分类：低延迟 + Structured Output + 足够准确
复杂规划：推理质量优先，允许更高延迟
批量抽取：吞吐量和单位成本优先
```

然后用当前模型目录去映射。

模型目录以后换名字，你的架构思路仍然成立。

---

## 4. 推理强度不是“智商滑块”

当前 GPT-5.6 系列可以通过 `reasoning.effort` 调整推理预算。

例如：

```python
from openai import OpenAI

client = OpenAI()

response = client.responses.create(
    model="gpt-5.6-terra",
    input=(
        "为一位行动不便的老人设计东京两日行程。"
        "要求减少步行、每天最多三个景点，并考虑雨天备选。"
    ),
    reasoning={"effort": "medium"},
    text={"verbosity": "low"},
)

print(response.output_text)
```

### 预期输出

具体内容每次会不同，但一个合理答案应该明显体现：

```text
Day 1
- 上午：浅草寺……
- 下午：……
- 雨天替代：……

Day 2
- ……

并说明减少步行的交通安排。
```

这里 `reasoning.effort="medium"` 的意思不是：

> 把模型“智商调到中等”。

更准确地理解是：

> **允许模型在这次请求中使用一个不同的内部推理预算。**

它可能影响：

```text
质量
延迟
Token 使用
成本
```

是否值得增加推理强度，应该通过任务评估来决定，而不是凭感觉。

---

## 5. 为什么简单任务不应该默认开最高推理？

假设你只想判断：

> 用户的问题是否需要查询天气？

输出只有：

```json
{"needs_weather": true}
```

如果这个任务本身已经能稳定做到 99%+，继续把推理强度拉高，可能只是：

```text
更慢
更贵
质量几乎不变
```

这就像为了判断“门是开还是关”，请一个专家委员会讨论十分钟。

反过来，如果是：

```text
20 条约束
多步计划
证据互相冲突
需要权衡取舍
```

更强模型或更高推理预算可能非常值得。

所以经验上我更推荐：

```text
先做最低成本的可用 baseline
        ↓
找到它真正失败的任务
        ↓
提高模型 / reasoning effort
        ↓
比较质量、延迟、成本
        ↓
只在有收益的地方升级
```

而不是一开始就把所有步骤拉满。

---

## 6. 一个简单的模型选择策略

Stage 00 不需要做复杂的“智能模型路由器”。

先用确定性配置就很好：

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelConfig:
    model: str
    reasoning_effort: str


MODEL_BY_ROLE = {
    "extract": ModelConfig(
        model="gpt-5.6-luna",
        reasoning_effort="low",
    ),
    "plan": ModelConfig(
        model="gpt-5.6-terra",
        reasoning_effort="medium",
    ),
    "hard_reasoning": ModelConfig(
        model="gpt-5.6-sol",
        reasoning_effort="high",
    ),
}
```

注意这里最重要的不是三个名字。

重要的是：

```text
模型选择由应用控制
```

而不是让用户随便传入：

```python
model = user_input["model"]
```

也不是让模型自己输出任意 provider model ID，然后程序照单全收。

如果未来需要动态路由，更安全的方式是：

```text
模型只选择一个受限类别
FAST | BALANCED | HARD
        ↓
应用映射到批准的 model config
```

这和 Tool Calling 的原则完全一致：

> **模型可以提议，应用拥有最终配置权。**

---

## 7. Model capability 和 Runtime capability 必须分开

这一点和上一章直接相连。

例如：

```text
模型支持 Function Calling
!=
模型能访问你的数据库
```

模型能够生成：

```text
query_database(...)
```

前提仍然是应用把这个 Tool 暴露给它。

同样：

```text
模型支持 vision
!=
模型自动看见你的桌面

模型支持 computer use
!=
模型被允许操作生产控制台

模型支持很大的 Context
!=
程序应该把所有数据库内容都发送过去
```

模型能力回答：

> 模型接口能理解或产生什么？

Runtime 能力回答：

> 当前应用实际开放了什么、允许什么、执行什么？

把两者混在一起，是 Agent 系统里非常危险的错误。

---

## 8. 模型升级为什么应该像代码升级一样测试？

假设你把模型从 A 换成 B。

即使 API 完全兼容，行为也可能变化：

```text
更喜欢调用 Tool
更少调用 Tool
Structured Output 的语义准确率变化
计划变长
回答更啰嗦
拒绝率变化
Token 使用变化
延迟变化
```

因此：

```text
“新模型更强”
```

不等于：

```text
“我们的 Agent 一定更好”
```

真正应该比较的是你的任务指标。

例如：

| 配置 | 路由准确率 | 任务成功率 | p95 延迟 | 平均 Token | 成功任务成本 |
|---|---:|---:|---:|---:|---:|
| baseline | 96% | 83% | 1.2s | 900 | X |
| candidate | 97% | 89% | 2.0s | 1450 | Y |

然后问：

> 多出来的质量值不值得多出来的成本和延迟？

Stage 08 会系统学习 Evaluation；Stage 00 只需要先建立这个习惯。

---

## 9. 不要依赖模型展示“完整思维过程”来判断它是否可靠

推理模型可能有内部 reasoning，但工程上不要把“能不能看到完整 chain-of-thought”当成正确性保障。

真正应该检查的是：

```text
最终答案是否正确？
结构化字段是否正确？
Tool 选择是否合理？
证据是否支持结论？
成本和延迟是否可接受？
```

换句话说：

> **评价可观察的行为，而不是迷信内部思考看起来有多长。**

如果需要调试，可以使用 API 提供的可观察信息、reasoning summary（适用时）、Tool trajectory、trace 和 evaluator，但不要把隐藏推理当成 Runtime 接口。

---

## 10. 这一章和下一章怎样连起来？

现在我们已经知道：一次 Agent 任务可能经过多个模型调用，而且不同调用的配置可能不同。

那么成本问题就从：

```text
“一次 API 调用多少钱？”
```

升级成：

```text
“一个完整任务会调用多少次模型？”
“每一次携带多少 Context？”
“Tool loop 会不会把同一份历史反复发送？”
“高 reasoning effort 会增加多少延迟和 Token？”
```

于是下一章自然出现：

> **Context、Token、成本和延迟，为什么不是财务统计，而是 Agent 架构的一部分？**

---

## 本章小结

一个有经验的 Agent 工程师通常不会问：

> “哪个模型最强？”

而会问：

> **这个步骤需要哪些能力？哪一个经过评估的模型配置，能在质量、延迟和成本约束下完成它？**

记住：

```text
模型能力 != Runtime 权限
更高 reasoning effort != 永远更好
新模型 != 自动带来更好的 Agent
模型选择 = 应用策略
```

---

## 官方参考

- OpenAI 当前 model guidance：<https://developers.openai.com/api/docs/guides/latest-model>
- OpenAI Responses API：<https://developers.openai.com/api/reference/resources/responses>
