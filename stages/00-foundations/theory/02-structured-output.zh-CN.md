# 02 — 当自然语言要交给程序：Structured Output

> Language: [English](02-structured-output.md) | 简体中文

上一章我们已经能完成一次真正的 LLM 调用：

```text
Python 程序
    ↓
OpenAI Responses API
    ↓
模型
    ↓
自然语言回答
```

如果答案最后只是展示给人看，这已经够用了。

但 Agent 不只是“聊天”。它经常需要让模型的结果继续进入代码逻辑：路由、计划、风险判断、参数提取、评估……这时自然语言突然变成了一个麻烦。

所以这一章解决的问题不是“怎样让模型更会写 JSON”，而是：

> **怎样把概率模型的输出，变成程序可以稳定消费的数据接口？**

---

## 1. 先看一个很真实的失败方式

继续我们的旅行助手。

用户说：

> 我 2026 年 10 月 3 日去东京，预算大约 8000 元，还想查一下天气。

如果只是普通问答：

```python
response = client.responses.create(
    model="gpt-5.6-luna",
    input=(
        "请从这句话里提取城市、日期、预算和是否需要天气："
        "我 2026 年 10 月 3 日去东京，预算大约 8000 元，还想查一下天气。"
    ),
)

print(response.output_text)
```

模型可能回答：

```text
城市是东京，日期是 2026 年 10 月 3 日，预算约 8000 元，用户需要查询天气。
```

这对人非常清楚，但程序接下来怎么办？

你可能会想到：

```python
if "东京" in text:
    ...
```

或者正则表达式：

```python
re.search(...)
```

再复杂一点，模型换一种说法：

```text
旅行目的地：Tokyo
出发日期：10/03/2026
预算：约 RMB 8k
天气需求：有
```

你的解析代码就开始变成一场和自然语言措辞的追逐游戏。

经验上，这类设计的问题不是“正则写得还不够聪明”，而是**边界设计错了**。

程序真正需要的是一个结构化对象，就应该直接把这个契约告诉模型和 API。

---

## 2. “请输出 JSON”为什么还不够？

一个常见改进是提示：

```text
请只输出 JSON，不要解释，不要 Markdown。
```

这当然比完全自由的自然语言好，但它仍然只是**语言层面的请求**。

模型可能输出：

```text
当然，结果如下：
{"city": "东京", ...}
```

也可能字段名变成：

```json
{
  "destination": "东京"
}
```

甚至出现：

```json
{
  "budget": "大约八千元"
}
```

当程序真正依赖字段名、类型和必填项时，我们希望约束再强一些。

这就是 Structured Output。

---

## 3. 用 JSON Schema 明确“程序到底要什么”

我们先不看 OpenAI 参数，先像设计普通 API 一样写需求。

程序希望收到：

```json
{
  "city": "东京",
  "travel_date": "2026-10-03",
  "budget_cny": 8000,
  "needs_weather": true
}
```

那么契约可以写成 JSON Schema：

```python
TRIP_SCHEMA = {
    "type": "object",
    "properties": {
        "city": {"type": "string"},
        "travel_date": {"type": "string"},
        "budget_cny": {"type": "number"},
        "needs_weather": {"type": "boolean"},
    },
    "required": [
        "city",
        "travel_date",
        "budget_cny",
        "needs_weather",
    ],
    "additionalProperties": False,
}
```

不要把 JSON Schema 看成“为了 LLM 新学的一套奇怪语法”。

它本质上是在说：

```text
结果必须是 object
city 必须是 string
budget_cny 必须是 number
needs_weather 必须是 boolean
这些字段都必须存在
不要偷偷再加其它字段
```

这和你给普通函数定义参数类型，本质上是在做同一件事：**建立接口契约。**

---

## 4. 完整 OpenAI Structured Output 示例

当前 Responses API 可以通过 `text.format` 使用 JSON Schema 约束输出。

```python
import json
from openai import OpenAI

client = OpenAI()

TRIP_SCHEMA = {
    "type": "object",
    "properties": {
        "city": {"type": "string"},
        "travel_date": {"type": "string"},
        "budget_cny": {"type": "number"},
        "needs_weather": {"type": "boolean"},
    },
    "required": [
        "city",
        "travel_date",
        "budget_cny",
        "needs_weather",
    ],
    "additionalProperties": False,
}

response = client.responses.create(
    model="gpt-5.6-luna",
    instructions=(
        "从用户的旅行描述中提取信息。"
        "日期统一输出为 YYYY-MM-DD。"
        "不要猜测用户没有提供的信息。"
    ),
    input=(
        "我 2026 年 10 月 3 日去东京，预算大约 8000 元，"
        "还想查一下天气。"
    ),
    text={
        "format": {
            "type": "json_schema",
            "name": "trip_request",
            "strict": True,
            "schema": TRIP_SCHEMA,
        }
    },
)

data = json.loads(response.output_text)
print(data)
print(type(data["needs_weather"]))
```

对应可运行文件：

[`../code/structured_output_demo.py`](../code/structured_output_demo.py)

### 预期输出

```text
{'city': '东京', 'travel_date': '2026-10-03', 'budget_cny': 8000, 'needs_weather': True}
<class 'bool'>
```

实际字符串细节可能略有变化，但输出必须符合我们定义的结构。

这就是关键区别：我们不再希望程序去“猜模型想表达什么格式”，而是提前声明格式契约。

---

## 5. 逐行看 `text.format` 在做什么

最值得理解的是：

```python
text={
    "format": {
        "type": "json_schema",
        "name": "trip_request",
        "strict": True,
        "schema": TRIP_SCHEMA,
    }
}
```

### `type="json_schema"`

告诉 API：这不是普通自由文本，而是结构化 JSON 输出。

### `name="trip_request"`

给这份结构一个稳定名字，便于 API 和开发者识别。

### `strict=True`

要求模型输出遵循支持的严格 Schema 约束。

### `schema=TRIP_SCHEMA`

真正定义字段、类型和必填项。

所以 Structured Output 的职责主要是：

```text
约束输出的 shape / syntax
```

而不是：

```text
保证每一个值在现实世界都一定正确
```

这一点非常重要。

---

## 6. Schema 正确，不代表语义一定正确

假设模型返回：

```json
{
  "city": "大阪",
  "travel_date": "2026-10-03",
  "budget_cny": 8000,
  "needs_weather": true
}
```

从 Schema 看：完全合法。

但用户明明说的是东京。

因此：

```text
Structured Output
    ↓
保证“长得像正确的数据结构”

不保证
    ↓
“里面每一个事实都正确”
```

这和传统程序也很像：

```python
age: int = 999
```

类型是 `int`，但业务上显然可能不合理。

所以真正的 Runtime 往往还要继续做：

```text
Schema validation
    +
业务规则 validation
    +
权限 / 安全 validation
```

Stage 07 会把这条线展开得更完整。

---

## 7. Structured Output 解决的是“表达”，不是“行动”

这里非常容易和下一章的 Tool Calling 混淆。

### Structured Output

问题是：

> 模型的结果应该以什么结构交给程序？

例如：

```json
{
  "route": "weather",
  "confidence": 0.96
}
```

模型只是给出一份数据。

### Tool Calling

问题变成：

> 模型是否建议应用去执行某个外部动作？

例如：

```text
get_weather(city="东京")
```

这已经不是单纯“输出格式好不好看”，而是在提出一个**行动请求**。

可以这样记：

```text
Structured Output
    = 给程序一份结构化结论

Tool Calling
    = 给 Runtime 一份结构化行动提案
```

ToolCall 自己通常也是结构化数据，但它的语义已经完全不同。

---

## 8. 为什么 Agent 特别依赖 Structured Output？

一个普通聊天机器人偶尔格式不漂亮，可能只是 UI 难看一点。

Agent 的模型输出却经常处在程序控制边界上。

例如：

```text
用户请求
   ↓
模型路由
   ↓
route = "search"
   ↓
程序启动检索
```

或者：

```text
模型生成计划
   ↓
steps = [...]
   ↓
程序逐步执行
```

再或者：

```text
模型评估风险
   ↓
risk = "high"
   ↓
程序进入审批流程
```

如果这些关键字段都藏在一段自由文本里，再靠关键词解析，整个系统会非常脆弱。

所以越接近**程序决策边界**，越应该明确数据契约。

---

## 9. 什么时候反而不需要 Structured Output？

不要走到另一个极端，觉得“专业系统就应该所有输出都是 JSON”。

如果最终目标就是让人阅读：

```text
解释概念
写一封邮件
总结文章
生成报告正文
```

自然语言通常更合适。

可以用一个简单判断：

> **下一位消费者是谁？**

如果下一位消费者是人：

```text
优先自然语言
```

如果下一位消费者是代码：

```text
优先明确结构
```

这条判断比“JSON 看起来更工程化”有用得多。

---

## 10. 从这一章自然走向 Tool Calling

现在旅行助手已经能把：

```text
“我去东京，还想查天气”
```

稳定地转换成：

```json
{
  "city": "东京",
  "needs_weather": true,
  ...
}
```

但新的问题马上出现：

> **知道用户“需要天气”，和真正“获得天气”，是一回事吗？**

当然不是。

模型可以判断：

```text
needs_weather = true
```

但真实天气可能需要访问一个 API、数据库或本地函数。

于是我们进入 Stage 00 最核心的一章：

> 模型到底怎样“调用”一个 Python Tool？

答案会比“LLM 调函数”这五个字更有意思。

---

## 本章小结

你现在应该能把 Structured Output 解释成：

> **在模型和确定性程序之间建立明确的数据契约，让程序不再依赖对自由文本的脆弱解析。**

同时记住：

```text
Schema 正确 != 事实正确
Structured Output != Tool Calling
自然语言不是坏东西，只是不适合所有软件边界
```

下一章，我们让模型第一次提出一个真正的外部动作。

---

## 官方参考

- OpenAI Responses / Structured Output format：<https://developers.openai.com/api/reference/resources/responses>
- OpenAI Structured Outputs 说明：<https://openai.com/index/introducing-structured-outputs-in-the-api/>
