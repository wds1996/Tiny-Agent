# Stage 00 练习与自测

> Language: [English](review-questions.md) | 简体中文

这份练习不是让你背定义。

Stage 00 真正需要检查的是：当一段 Agent 代码摆在你面前时，你能不能准确指出**模型做了什么、Runtime 做了什么、数据从哪里来、下一轮为什么能继续**。

建议先关闭理论文档，再完成下面的题目。不会的地方再回去查，比顺着正文一路点头更有效。

---

## 第一部分：请尝试“讲给别人听”

### 1. 从一次 LLM 调用开始

不要引用课文原句，用自己的话回答：

1. `client = OpenAI()` 创建的是模型吗？它真正负责什么？
2. `instructions` 和当前用户 `input` 为什么不应该被理解成完全相同的东西？
3. `response.output_text` 为什么方便，但 Agent Runtime 不能只依赖它？
4. 两个完全独立的 API 请求之间，为什么不能默认模型天然保留上一轮事实？
5. `previous_response_id` 解决了什么问题？它为什么仍然不等于“长期记忆”？
6. Python 内存里已经存在的数据，什么时候才真正成为模型 Context？

如果你能把这六个问题讲清楚，说明第一章不是只看懂了代码语法。

### 2. Structured Output

现在解释下面三个“不等于”：

```text
“请输出 JSON” != Structured Output
Schema 合法 != 事实正确
Structured Output != Tool Calling
```

然后回答：

1. 为什么程序不应该靠正则表达式长期解析关键控制信息？
2. JSON Schema 在模型边界上解决的主要是什么问题？
3. 如果 `city` 字段类型正确，但模型把“东京”抽取成“大阪”，哪一层出了问题？
4. 什么场景下自然语言比 Structured Output 更合适？

### 3. Tool Calling

请不看文档，在纸上画出：

```text
用户 -> 模型 -> ToolCall -> Runtime -> Python Tool -> Tool Result -> 模型 -> 最终答案
```

并在每一条箭头旁写“谁负责”。

然后回答：

1. Tool schema 和 Python handler 为什么要分开？
2. `strict=True` 能否替代权限检查？为什么？
3. `call_id` 用来解决什么关联问题？
4. 为什么 Tool 已经在 Python 中执行完，模型仍然需要收到 `function_call_output`？
5. 如果模型请求一个 registry 中不存在的 Tool，应该由谁拒绝？
6. “模型支持 Function Calling”和“模型有权删除数据库”之间差了哪些 Runtime 边界？

### 4. 模型选择

给下面四种任务分别说明你最关心的模型属性，不要求指定具体 model ID：

- 从一句话提取 4 个字段；
- 根据 15 条约束制定计划；
- 批量处理 10 万条短文本分类；
- 识别一张截图中的错误提示。

然后解释：

```text
更高 reasoning effort != 永远更好
模型能力 != Runtime 权限
更新模型 != Agent 自动变好
```

### 5. Context / Token / Cost / Latency

回答：

1. 数据库里有一百万行数据，为什么不等于模型拥有一百万行 Context？
2. Context window 很大时，为什么仍然需要筛选？
3. 为什么“单次调用便宜”不等于“完整 Agent 任务便宜”？
4. 并发为什么可以降低部分 wall-clock latency，却不能无限增加？
5. 如果一个 Agent 每轮都携带 20K Token 历史并调用模型 8 次，你首先会检查什么？

### 6. Instructions 与 Context Construction

给下面内容分类：

```text
“回答必须使用中文”
“用户本轮想去东京”
“网页说浅草寺早晨更少人”
“用户过去喜欢少走路”
“get_weather 的 JSON Schema”
“退款超过 500 元必须审批”
```

分别判断它更适合属于：

```text
Instructions
Task
Evidence
Memory
Tool schema
Runtime policy
```

然后说明为什么“退款超过 500 元必须审批”不能只写在 Prompt 中。

---

# 第二部分：真正动手改代码

## 实验 1 — 第一次 OpenAI 调用不要只复制

打开：

[`../code/first_openai_call.py`](../code/first_openai_call.py)

完成三个修改：

1. 把系统指令改成“用类比给初学者解释”；
2. 第一轮告诉模型一个你自己的项目名称；
3. 第二轮用 `previous_response_id` 问模型项目叫什么。

然后删除 `previous_response_id` 再运行一次，观察差别。

你应该能够解释：**差别来自请求上下文，而不是模型突然失忆。**

---

## 实验 2 — 故意破坏 Structured Output

运行：

[`../code/structured_output_demo.py`](../code/structured_output_demo.py)

然后做两个实验。

### A. Prompt-only JSON

暂时移除 `text.format`，只在 `instructions` 中写：

```text
请返回 JSON。
```

连续调用几次，观察输出是否始终满足你原来的字段和类型约束。

### B. 修改 Schema

新增：

```json
"travel_style": {
  "type": "string",
  "enum": ["budget", "balanced", "comfort"]
}
```

同时修改输入，使用户明确表达旅行风格。

验收标准不是“程序不报错”，而是你能解释：

> Schema 负责结构；指令和输入负责让字段具有正确语义。

---

## 实验 3 — 给 Tool loop 增加一个真实的新能力

打开：

[`../code/minimal_tool_loop.py`](../code/minimal_tool_loop.py)

新增一个没有副作用的 Tool，例如：

```python
convert_cny_to_jpy(amount_cny: float, rate: float) -> dict
```

你需要同时修改：

```text
1. Tool schema
2. Python handler
3. execute_tool registry / dispatch
```

然后让用户问：

> 东京示例天气是多少？换算成华氏度；另外 8000 元按给定汇率大约是多少日元？

观察模型是否会产生多轮 ToolCall。

你应该能够指出：新增 Tool 时，“模型看到的接口”和“Runtime 真正执行的代码”分别改了哪里。

---

## 实验 4 — 故意请求未知 Tool

不用真的依赖模型随机犯错。

在 `execute_tool()` 旁边写一个最小测试：

```python
execute_tool("delete_everything", {})
```

确认 Runtime 拒绝未知 Tool。

然后思考：如果模型真的生成这个名字，为什么不能让 Runtime 去“猜它是不是想调用另一个类似函数”？

这里要建立的是 default-deny 直觉：**没有注册，不执行。**

---

## 实验 5 — 看一次真实 usage

写一个小脚本，分别发送：

```text
A. 只有一个短问题
B. 同一个问题 + 一大段无关背景
```

打印：

```python
response.usage.input_tokens
response.usage.output_tokens
response.usage.total_tokens
```

不要追求固定 Token 数。

记录并解释：

- 为什么 B 的输入 Token 更多？
- 答案是否真的更好？
- 如果这个 Context 在 6 轮 Agent loop 中重复，会发生什么？

---

## 实验 6 — 比较 reasoning effort，而不是凭感觉争论

挑一个确实需要多约束推理的问题，例如：

> 为行动不便的老人安排两天东京行程，每天最多三个地点，减少步行，并准备雨天替代方案。

使用同一个模型分别测试两个 reasoning effort。

记录：

```text
是否满足全部约束
大致响应时间
usage
最终答案质量
```

不要问“哪个看起来更聪明”。

问：

> **增加推理预算是否在这个具体任务上产生了值得的收益？**

这就是最小版 evaluation 思维。

---

# 第三部分：Stage 00 小项目

完成一个不依赖 Agent 框架的 **Mini Travel Assistant**。

你可以直接在一个新脚本里完成，不要求抽象得很漂亮。

系统至少应支持：

```text
用户自然语言旅行请求
        ↓
Structured Output 提取 city / date / budget / needs_weather
        ↓
如果需要天气，模型可以请求 get_weather Tool
        ↓
Runtime 校验并执行本地 Tool
        ↓
Tool result 以 function_call_output 返回模型
        ↓
模型生成最终旅行建议
```

额外要求：

- 所有 LLM 调用使用 OpenAI Responses API；
- Tool 执行必须发生在 Python Runtime，而不是假装模型执行；
- 至少设置一个最大 Tool loop 步数；
- 未知 Tool 必须拒绝；
- 最终打印本次运行的 Token usage 或调用次数；
- 代码注释中写清楚哪些是模型责任，哪些是 Runtime 责任。

完成后，你应该能从头到尾给另一个人讲一遍程序，而不是只说“这里调用 OpenAI，反正它就会做”。

---

# 第四部分：面试式问题

这些问题不要求背统一答案，但应该能在 1–2 分钟内讲清楚。

1. **Function Calling 本身算不算 Agent？为什么？**
2. **Structured Output 和 Tool Calling 的根本区别是什么？**
3. **如果模型输出 `delete_database()`，Runtime 为什么不能因为“模型选择了它”就直接执行？**
4. **`previous_response_id`、conversation history、checkpoint 和 long-term memory 是一回事吗？**
5. **为什么 provider-specific Response object 最终通常要在 Runtime 中被归一化？**
6. **模型支持 1M Context 时，为什么工程上仍然需要 Context Engineering？**
7. **什么时候你会为 Agent 的不同步骤使用不同模型？**
8. **为什么 cost per successful task 比单次模型价格更有意义？**
9. **Prompt 中的安全规则为什么不能替代确定性的 authorization？**
10. **Stage 00 的 Tool loop 还缺哪些能力，才会变成更完整的 Agent Runtime？**

如果这十个问题能稳定讲清楚，你已经准备好进入 Stage 01。
