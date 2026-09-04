# Advanced — Tool / Agent-Computer Interface Design：Tool 写得不好，Runtime 再正确也救不了

> Language: [English](tool-interface-design.md) | 简体中文

前面几章一直强调 Runtime boundary。

但还有一个经常被忽视的问题：

> **模型到底是通过什么界面理解“自己能做什么”的？**

答案就是 Tool interface。

很多 Agent 失败，不是 Runtime loop 写错了，也不是模型能力不够，而是 Tool 对模型来说实在太难用了。

可以把它理解成：

```text
Tool schema
=
Agent 使用计算机能力时看到的“操作界面”
```

一个接口写得含糊，就像给人一个没有标签、没有说明书、按钮全长一样的控制台，然后怪他“操作能力不行”。

这一节专门讲怎么把 Tool 设计成模型真正容易正确使用的接口。

---

## 1. 先看一个很差的 Tool

```python
Tool(
    name="do_task",
    description="Do a task.",
    parameters={
        "type": "object",
        "properties": {
            "action": {"type": "string"},
            "payload": {"type": "string"},
        },
        "required": ["action", "payload"],
    },
    handler=do_task,
)
```

Python 可能完全能执行它。

但模型看到的是：

```text
do_task
action: string
payload: string
```

模型必须自己猜：

```text
action 能写哪些值？
payload 是 JSON 还是自然语言？
查天气应该怎么编码？
发送邮件是不是也用这个 Tool？
失败后返回什么？
```

这实际上把大量应用规则又偷偷扔回给模型了。

---

## 2. 好 Tool 先解决“什么时候应该用我”

旅行助手里，如果 Tool 是：

```python
name="weather"
description="Weather tool."
```

虽然不是错，但信息太少。

更好的描述是：

```python
Tool(
    name="get_mock_weather",
    description=(
        "Return the course's deterministic mock weather for one city. "
        "Use it only when the task asks for the course mock weather. "
        "It does not provide live weather data."
    ),
    ...
)
```

这段 description 同时回答：

```text
它做什么？
什么时候应该用？
什么时候不应该用？
它的数据边界是什么？
```

Tool selection 本质上也是一个语言理解问题。

如果接口描述不清，模型选错 Tool 很正常。

---

## 3. Tool name 应该像稳定的能力名，而不是内部实现名

推荐：

```text
get_weather
search_papers
read_document_chunk
create_report_draft
```

不推荐：

```text
do_task_2
api_v4_call
handle_request
execute_misc
```

为什么？

因为模型会把 Tool name 当成语义线索的一部分。

一个好的名字应该让人和模型都能大概猜到能力边界。

---

## 4. Schema 要把“应用已经知道的约束”写进去

假设单位只允许：

```text
celsius
fahrenheit
```

不要写：

```python
{"units": {"type": "string"}}
```

然后祈祷模型不要输出：

```text
"华氏"
"F"
"fahrenheit please"
"kelvin"
```

既然应用已经知道合法集合，就直接写：

```python
{
    "units": {
        "type": "string",
        "enum": ["celsius", "fahrenheit"],
    }
}
```

同样，能写：

```text
required
enum
minimum / maximum
additionalProperties=False
```

的地方，就不要用一坨 free-form string 让模型自己编码规则。

经验上：

> **确定性约束应该尽量由 schema / code 表达，而不是只靠 prompt。**

---

## 5. Tool granularity：太细和太粗都不好

### 太细

假设做一次“查询天气”需要：

```text
resolve_city_name
lookup_city_id
build_weather_query
send_weather_http
parse_weather_json
extract_temperature
```

全部暴露给模型。

模型每次查天气都要规划六步。

这会增加：

```text
Tool selection error
Token cost
step count
failure surface
```

这些其实是普通 application implementation detail，不一定值得交给模型。

### 太粗

另一边，如果只给：

```text
shell(command)
http(method, url, headers, body)
```

模型确实“什么都能做”。

同时也获得：

```text
巨大 authority
巨大 ambiguity
巨大 safety surface
```

所以 Tool granularity 更像：

> **给模型一个完成任务所需的最小、语义清楚的 capability。**

旅行助手需要的是：

```text
get_weather(city)
```

而不是：

```text
raw_http_request(...)
```

除非你的场景真的需要模型自己构造 HTTP。

---

## 6. Tool 输出也是未来的 Context

很多人精心设计 Tool 输入，却让 handler 返回：

```text
5 MB raw logs
整个 HTML 页面
数据库 10000 行
完整 stack trace
```

然后全部塞进下一轮模型 Context。

Tool output 应该考虑：

```text
模型下一步真正需要什么？
输出是否有明确结构？
有没有 provenance？
有没有不必要的敏感信息？
体积是否有界？
```

例如：

### 差

```text
HTTP 200 ... [5000 lines] ...
```

### 更好

```json
{
  "city": "Tokyo",
  "temperature_c": 18.0,
  "condition": "cloudy",
  "source": "course_mock"
}
```

这会直接影响下一轮模型的理解质量、Token 成本和可审计性。

所以：

> **Tool output 是 Context Engineering 的上游。**

---

## 7. 不要让 Tool description 代替 authorization

你可以在 description 里写：

```text
Only use this Tool for administrators.
```

这有助于模型选择。

但它不是 permission system。

因为：

```text
模型遵守 description
```

仍然只是概率行为。

真正授权必须由 Runtime / policy 做确定性判断。

记住：

```text
模型可见
!=
模型被授权执行
```

这条原则后面在 MCP、Agent Skills、HITL、Safety 都会反复出现。

---

## 8. 多个相似 Tool 会怎样让模型犯难？

假设你暴露：

```text
search
web_search
internet_search
search_web
browser_search
```

五个 Tool description 又差不多。

你实际上创造了一个没有必要的分类问题：

```text
“这五个到底选哪个？”
```

如果能力真的相同，应该合并。

如果能力不同，就要把边界写得足够明确，例如：

```text
search_papers
  -> scholarly metadata only

search_web
  -> public web pages

search_internal_docs
  -> company-indexed documents only
```

Tool set 本身也是模型的 decision space。

**决策空间越大，不代表 Agent 越聪明。**

---

## 9. Dynamic exposure：不要每次都给模型看所有 Tool

大型系统可能有几百个能力。

每一轮都暴露全部 Tool 会带来：

```text
Context 增大
Tool selection 更难
无关 capability 干扰
攻击面扩大
```

所以后面的 Context Engineering 会讨论：

```text
先根据 task / domain 选择相关 Tool subset
        ↓
再把 subset 暴露给模型
```

但再次强调：

```text
exposure selection
!=
authorization
```

即使某 Tool 被暴露，Runtime 仍要做真正的权限判断。

---

## 10. Tool interface 应该怎样评估？

不要只凭：

> “这个 description 看起来挺清楚。”

建立一组任务：

```text
需要 Tool A 的题
需要 Tool B 的题
不需要任何 Tool 的题
参数容易混淆的题
Tool 会失败的题
```

然后测：

```text
Tool selection accuracy
argument accuracy
unnecessary Tool calls
recovery after failure
step count
Token / Context cost
```

例如旅行助手可以有：

| Task | Expected |
|---|---|
| “查课程东京模拟天气” | `get_mock_weather` |
| “18°C 等于多少°F” | `celsius_to_fahrenheit` |
| “东京是日本首都吗？” | no Tool |
| “查实时东京天气” | 不应把 mock Tool 当 live weather |

这比“跑一次 demo 成功了”更能说明 Tool interface 是否设计合理。

---

## 11. 一个经验丰富的 Tool designer 会问什么？

不是只问：

```text
函数能不能调用？
```

而会问：

```text
模型知道什么时候该用它吗？
模型知道什么时候不该用它吗？
参数约束能不能用 schema 表达？
这个 capability 粒度是否刚好？
输出会不会污染下一轮 Context？
Tool 之间有没有不必要的重叠？
权限是否由 Runtime 真正执行？
能不能用 dataset 评估这个接口？
```

这就是为什么 Tool Calling 不只是“给 Python function 套 JSON Schema”。

它更接近一个 **Agent-Computer Interface（ACI）设计问题**。

Runtime 决定 Agent 能不能安全地执行；Tool interface 很大程度决定模型能不能正确地使用这些能力。