# Stage 00 — 从一次 LLM 调用开始理解 Agent

> Language: [English](README.md) | 简体中文

Stage 00 不急着教你“怎么创建一个 Agent”。

我们先回答一个更基础、也更容易被教程跳过的问题：

> **当你写下 `client.responses.create(...)` 时，程序、模型和外部世界之间究竟发生了什么？**

如果这个边界没有弄清楚，后面学 Tool Calling、Memory、RAG、LangGraph、MCP 时，很容易把框架 API 背得很熟，却始终不知道哪一部分是模型在做，哪一部分其实是你的程序在做。

所以这一阶段只有一个目标：把 Agent 最底层的几块积木真正看懂。

---

## 这一阶段会一直用同一个例子

为了避免每一章换一个场景、知识点彼此断开，Stage 00 会围绕一个不断升级的“小型旅行助手”展开。

最开始，它只是一个普通 LLM：

```text
用户：我要去东京旅行，18°C 大概是什么体感？
模型：给出自然语言回答
```

接着，我们会发现自然语言不方便程序继续处理，于是引入 Structured Output：

```text
用户请求
   ↓
模型输出结构化旅行信息
{city, date, budget, needs_weather}
```

然后我们会发现模型并不知道真实天气，于是引入 Tool Calling：

```text
模型提出：get_weather(city="东京")
          ↓
Python Runtime 真正执行 Tool
          ↓
把 Tool 结果交回模型
          ↓
模型继续回答
```

到这里，你已经能看到一个 Agent loop 的雏形了。

后面三章再继续追问：

- 应该选哪个模型完成不同任务？
- 每轮调用的 Context、Token、成本和延迟怎么累积？
- 当信息越来越多时，究竟应该把什么放进下一次模型请求？

这样 Stage 01 的 ReAct Runtime 就不会凭空出现，而是从 Stage 00 的问题自然长出来。

---

## Stage 00 的知识主线

我建议不要把下面六章理解成六个独立知识点，而是理解成六个连续出现的问题。

```text
01  我怎样真正调用一次 LLM？
        ↓
02  如果程序要读取模型结果，怎样避免解析自然语言？
        ↓
03  如果模型需要外部能力，Tool 到底是谁执行的？
        ↓
04  不同模型和推理配置应该怎样选择？
        ↓
05  多轮调用后，Token / Context / 成本 / 延迟为什么会成为架构问题？
        ↓
06  信息越来越多，下一轮模型究竟应该看到什么？
        ↓
Stage 01：把这些步骤正式抽象成 Agent Runtime
```

前 3 章解决的是：

> **模型如何与程序交互？**

后 3 章解决的是：

> **程序应该怎样管理模型调用？**

这是 Stage 00 最重要的两条线。

---

## 推荐学习顺序

### 第一步：先让模型真正回答你

阅读：

1. [`theory/01-llm-api-and-messages.zh-CN.md`](theory/01-llm-api-and-messages.zh-CN.md)

然后运行：

```bash
python stages/00-foundations/code/first_openai_call.py
```

这一章不要背 API。你只需要真正理解：

```text
你的 Python 程序
    ↓ 构造请求
OpenAI Responses API
    ↓
模型推理
    ↓ 返回 Response
你的 Python 程序继续处理
```

### 第二步：让模型输出程序能稳定处理的数据

阅读：

2. [`theory/02-structured-output.zh-CN.md`](theory/02-structured-output.zh-CN.md)

运行：

```bash
python stages/00-foundations/code/structured_output_demo.py
```

这里会第一次出现一个非常重要的工程思想：

> **给人看的结果可以是自然语言；给程序做下一步决策的数据，最好有明确结构。**

### 第三步：让模型申请使用外部能力

阅读：

3. [`theory/03-function-calling.zh-CN.md`](theory/03-function-calling.zh-CN.md)

运行：

```bash
python stages/00-foundations/code/minimal_tool_loop.py
```

这一章是 Stage 00 的核心。请务必能够解释：

```text
Tool schema != Python function
ToolCall proposal != Tool execution
模型生成 arguments != 参数已经安全
Tool 执行完 != 模型自动知道结果
```

### 第四步：理解“选模型”也是应用设计

阅读：

4. [`theory/04-model-capabilities-and-reasoning.zh-CN.md`](theory/04-model-capabilities-and-reasoning.zh-CN.md)

这一章不要求你记住某个模型排行榜，而是学会按任务角色选择模型和推理强度。

### 第五步：开始把每次模型调用当成资源消耗

阅读：

5. [`theory/05-context-tokens-cost-latency.zh-CN.md`](theory/05-context-tokens-cost-latency.zh-CN.md)

运行：

```bash
python stages/00-foundations/code/context_budget_basics.py
```

你会看到：Agent 一旦进入循环，同一份 Context 可能被反复发送，因此“多塞一点内容”会同时影响成本、延迟和模型注意力。

### 第六步：学会构造一次真正有边界的模型请求

阅读：

6. [`theory/06-instructions-prompts-and-context-construction.zh-CN.md`](theory/06-instructions-prompts-and-context-construction.zh-CN.md)

最后完成：

7. [`exercises/review-questions.zh-CN.md`](exercises/review-questions.zh-CN.md)

---

## 先把 OpenAI 环境准备好

Stage 00 的真实 LLM 示例统一使用当前 OpenAI **Responses API**。这样读者不用一会儿学 Chat Completions、一会儿又换另一套调用方式。

安装项目和 OpenAI 依赖：

```bash
python -m pip install -e ".[openai]"
```

配置 API Key：

```bash
export OPENAI_API_KEY="你的 API Key"
```

Windows PowerShell：

```powershell
$env:OPENAI_API_KEY="你的 API Key"
```

示例默认使用一个当前可用的 GPT-5.6 系列模型，并允许通过环境变量覆盖：

```bash
export OPENAI_MODEL="gpt-5.6-luna"
```

模型名称会随着 provider 更新而变化，所以不要把某个 model ID 当成课程知识本身。真正应该记住的是请求结构和 Runtime 边界。

OpenAI 当前模型与 Responses API 文档：

- https://developers.openai.com/api/docs/guides/latest-model
- https://developers.openai.com/api/reference/resources/responses

---

## Stage 00 最重要的心智模型

整个 Tiny-Agent 后面十几个阶段，其实都在不断扩展下面这张图：

```text
               Application / Runtime
┌───────────────────────────────────────────┐
│ 选择模型                                  │
│ 构造 instructions                         │
│ 选择 Context                              │
│ 暴露 Tool schema                          │
│ 校验模型输出                              │
│ 判断权限                                  │
│ 执行真实 Python / API                     │
│ 保存状态                                  │
│ 控制成本、步骤和停止条件                   │
└───────────────────────────────────────────┘
                       │
                       │ request
                       ▼
                 ┌───────────┐
                 │    LLM    │
                 │           │
                 │ 根据收到的 │
                 │ Context   │
                 │ 生成下一步 │
                 └───────────┘
                       │
                       │ text / structured data / ToolCall
                       ▼
               Application / Runtime
```

可以把模型想成一个非常强的“语义决策引擎”，但不要把它想成整个程序。

它可以说：

> “我建议调用 `get_weather(city="东京")`。”

但真正决定：

- 这个 Tool 是否存在；
- 参数是否合法；
- 当前用户有没有权限；
- 是否需要审批；
- Python 函数是否真的执行；
- 结果怎样保存和送回下一轮；

的是应用 Runtime。

因此从 Stage 00 开始一直记住一句话：

> **模型负责提出下一步；应用负责决定这一步能不能、应不应该、以及怎样真正发生。**

---

## 学完这一阶段，你应该能自己讲出什么？

不要用“我看完了六篇 Markdown”作为完成标准。

真正的完成标准是：你能不用看笔记，给别人讲清楚下面这条链路：

```text
用户输入
    ↓
应用选择 instructions / Context / Tools
    ↓
调用 OpenAI Responses API
    ↓
模型输出文本 / Structured Output / ToolCall
    ↓
应用解析并校验
    ↓
如果是 ToolCall：Runtime 执行真实函数
    ↓
将 Tool 结果作为 function_call_output 交回模型
    ↓
模型继续决策或生成最终回答
```

然后再回答三个问题：

1. 为什么“模型支持 Tool Calling”不等于“模型拥有这个 Tool 的权限”？
2. 为什么“支持超长 Context”不等于“应该把所有信息都塞进去”？
3. 为什么一次 Function Calling 还不能称为完整的生产级 Agent？

如果这三个问题你能讲明白，Stage 01 就已经有了牢固地基。
